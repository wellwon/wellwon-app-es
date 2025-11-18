# app/infra/saga/saga_manager.py
# =============================================================================
# File: app/infra/saga/saga_manager.py
# Description: Enhanced Saga Manager with centralized config and ProjectionRebuilder support
# UPDATED: Added bidirectional reference support for context restoration
# =============================================================================

from __future__ import annotations

import asyncio
import logging
import uuid
import json
import time
from typing import Dict, Any, List, Optional, Type, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from app.infra.event_bus.event_bus import EventBus
from app.infra.persistence.redis_client import safe_set, safe_get, safe_delete

# Import centralized saga config
from app.config.saga_config import saga_config

# Type checking imports
if TYPE_CHECKING:
    from app.services.infrastructure.saga_service import SagaService

log = logging.getLogger("wellwon.saga_manager")


class SagaStatus(Enum):
    """Saga execution status"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Represents a single step in a saga"""
    name: str
    execute: Callable[..., Awaitable[Any]]
    compensate: Callable[..., Awaitable[Any]]
    timeout_seconds: int = 30
    retry_count: int = 3
    # OPTIMIZED: Add retry delay configuration
    retry_delay_base: float = 0.5  # Start with 500ms instead of 2s
    retry_delay_max: float = 2.0  # Max 2s instead of longer delays


@dataclass
class CompensationRecord:
    """Record of a compensation that needs to be executed"""
    step_name: str
    compensate_func: Callable[..., Awaitable[Any]]
    context: Dict[str, Any]
    executed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class SagaState:
    """State of a running saga with enhanced Event Store tracking"""
    saga_id: uuid.UUID
    saga_type: str
    status: SagaStatus
    current_step: int
    total_steps: int
    started_at: datetime
    timeout_at: datetime
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    compensations: List[CompensationRecord] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # Enhanced Event Store tracking
    event_store_enabled: bool = False
    causation_chain: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None

    # OPTIMIZED: Track performance metrics
    step_timings: Dict[str, float] = field(default_factory=dict)

    # FIXED: Add step results storage
    step_results: Dict[str, Any] = field(default_factory=dict)

    # FIXED: Add current_step_name property
    @property
    def current_step_name(self) -> Optional[str]:
        """Get the name of the current step"""
        if hasattr(self, '_current_step_name'):
            return self._current_step_name
        return f"step_{self.current_step}" if self.current_step >= 0 else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with Event Store context"""
        # Filter out non-serializable objects from context
        serializable_context = {}
        for key, value in self.context.items():
            # Skip service objects and buses that can't be serialized
            if key in ['event_bus', 'event_store', 'saga_manager', 'command_bus', 'query_bus',
                       'interaction_service', 'auth_service', '_cleanup_conflict_key', '_cleanup_saga_id',
                       '_unlock_aggregate', 'virtual_broker_service', 'projection_rebuilder']:
                continue
            # Handle different types
            if isinstance(value, (str, int, float, bool, type(None))):
                serializable_context[key] = value
            elif isinstance(value, uuid.UUID):
                serializable_context[key] = str(value)
            elif isinstance(value, datetime):
                serializable_context[key] = value.isoformat()
            elif isinstance(value, list):
                serializable_list = []
                for item in value:
                    if isinstance(item, uuid.UUID):
                        serializable_list.append(str(item))
                    elif isinstance(item, datetime):
                        serializable_list.append(item.isoformat())
                    elif isinstance(item, (str, int, float, bool, dict, list, type(None))):
                        serializable_list.append(item)
                serializable_context[key] = serializable_list
            elif isinstance(value, dict):
                serializable_dict = {}
                for k, v in value.items():
                    if isinstance(v, uuid.UUID):
                        serializable_dict[k] = str(v)
                    elif isinstance(v, datetime):
                        serializable_dict[k] = v.isoformat()
                    elif isinstance(v, (str, int, float, bool, dict, list, type(None))):
                        serializable_dict[k] = v
                serializable_context[key] = serializable_dict

        return {
            "saga_id": str(self.saga_id),
            "saga_type": self.saga_type,
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "started_at": self.started_at.isoformat(),
            "timeout_at": self.timeout_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "context": serializable_context,
            "compensations": [
                {
                    "step_name": c.step_name,
                    "executed_at": c.executed_at.isoformat() if c.executed_at else None,
                    "error": c.error
                }
                for c in self.compensations
            ],
            "errors": self.errors,
            "event_store_enabled": self.event_store_enabled,
            "causation_chain": self.causation_chain,
            "correlation_id": self.correlation_id,
            "step_timings": self.step_timings,
            "step_results": self.step_results,  # FIXED: Include step results
            "current_step_name": self.current_step_name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SagaState:
        """Recreate from stored dictionary"""
        state = cls(
            saga_id=uuid.UUID(data["saga_id"]),
            saga_type=data["saga_type"],
            status=SagaStatus(data["status"]),
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            started_at=datetime.fromisoformat(data["started_at"]),
            timeout_at=datetime.fromisoformat(data["timeout_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            context=data.get("context", {}),
            compensations=[],  # These need to be rebuilt
            errors=data.get("errors", []),
            event_store_enabled=data.get("event_store_enabled", False),
            causation_chain=data.get("causation_chain", []),
            correlation_id=data.get("correlation_id"),
            step_timings=data.get("step_timings", {}),
            step_results=data.get("step_results", {})  # FIXED: Restore step results
        )

        # Set current step name if available
        if data.get("current_step_name"):
            state._current_step_name = data["current_step_name"]

        return state


class BaseSaga(ABC):
    """
    Base class for implementing sagas - SERVER CONTEXT ONLY.
    Enhanced with Event Store awareness.
    """

    def __init__(self, saga_id: Optional[uuid.UUID] = None):
        self.saga_id = saga_id or uuid.uuid4()
        self.context: Dict[str, Any] = {}
        # OPTIMIZED: Track if this is a fast-track saga
        self._fast_track = False

    @abstractmethod
    def define_steps(self) -> List[SagaStep]:
        """Define the steps of this saga"""
        pass

    @abstractmethod
    def get_timeout(self) -> timedelta:
        """Get the overall timeout for this saga"""
        pass

    def get_saga_type(self) -> str:
        """Get the type name of this saga"""
        return self.__class__.__name__

    def enable_fast_track(self) -> None:
        """OPTIMIZED: Enable fast-track mode for this saga"""
        self._fast_track = True

    def is_fast_track(self) -> bool:
        """OPTIMIZED: Check if this is a fast-track saga"""
        return self._fast_track


class SagaManager:
    """
    Enhanced Saga Manager with centralized config and ProjectionRebuilder support.
    Manages saga execution, compensation, and recovery - SERVER CONTEXT ONLY.
    UPDATED: Added bidirectional reference support for context restoration.
    """

    def __init__(
            self,
            event_bus: EventBus,
            redis_prefix: str = "saga:",
            enable_monitoring: bool = True
    ):
        self.event_bus = event_bus
        self.redis_prefix = redis_prefix
        self.enable_monitoring = enable_monitoring

        # CQRS buses - REQUIRED in server context
        self._command_bus = None
        self._query_bus = None

        # Event Store integration
        self._event_store = None

        # UPDATED: Add reference to parent service for ProjectionRebuilder access
        self._parent_service: Optional['SagaService'] = None

        # Internal state
        self._active_sagas: Dict[uuid.UUID, SagaState] = {}
        self._saga_registry: Dict[str, Type[BaseSaga]] = {}
        self._timeout_monitors: Dict[uuid.UUID, asyncio.Task] = {}

        # Track initialization state
        self._initialized = False

        # OPTIMIZED: Performance tracking
        self._performance_metrics = {
            "total_sagas": 0,
            "average_execution_time": 0.0,
            "step_execution_times": {}
        }

    def set_parent_service(self, service: 'SagaService') -> None:
        """Set reference to parent SagaService for context restoration"""
        self._parent_service = service
        log.info("Parent SagaService reference set for context restoration")

    def set_command_bus(self, command_bus: Any) -> None:
        """Set the command bus - REQUIRED for saga orchestration"""
        if not command_bus:
            raise ValueError("Command bus is required for saga orchestration in server context")

        self._command_bus = command_bus
        log.info("Command bus injected into Saga Manager (SERVER CONTEXT)")
        self._check_initialization()

    def set_query_bus(self, query_bus: Any) -> None:
        """Set the query bus - REQUIRED for data access"""
        if not query_bus:
            raise ValueError("Query bus is required for data access in server context")

        self._query_bus = query_bus
        log.info("Query bus injected into Saga Manager (SERVER CONTEXT)")
        self._check_initialization()

    def set_event_store(self, event_store: Any) -> None:
        """Set Event Store for enhanced saga tracking"""
        self._event_store = event_store
        log.info("Event Store injected into Saga Manager for causation tracking")

    def _check_initialization(self) -> None:
        """Check if saga manager is fully initialized"""
        if self._command_bus and self._query_bus:
            self._initialized = True
            log.info("Saga Manager fully initialized with all required dependencies")

    def is_initialized(self) -> bool:
        """Check if saga manager is ready to execute sagas"""
        return self._initialized

    @property
    def command_bus(self):
        """Get command bus with validation"""
        if not self._command_bus:
            raise RuntimeError(
                "Command bus not available in Saga Manager. "
                "Sagas can ONLY run in server context with command bus access."
            )
        return self._command_bus

    @property
    def query_bus(self):
        """Get query bus with validation"""
        if not self._query_bus:
            raise RuntimeError(
                "Query bus not available in Saga Manager. "
                "Sagas can ONLY run in server context with query bus access."
            )
        return self._query_bus

    @property
    def event_store(self):
        """Get Event Store (optional but recommended)"""
        return self._event_store

    def register_saga(self, saga_class: Type[BaseSaga]) -> None:
        """Register a saga type - SERVER CONTEXT ONLY"""
        saga_type = saga_class.__name__
        self._saga_registry[saga_type] = saga_class
        log.info(f"Registered saga type: {saga_type} (SERVER CONTEXT)")

    def _get_saga_key(self, saga_id: uuid.UUID) -> str:
        """Get Redis key for saga state"""
        return f"{self.redis_prefix}{saga_id}"

    async def _restore_context_references(self, state: SagaState) -> None:
        """Restore non-serializable references to saga context after loading from Redis"""
        # Always restore CQRS buses - they are required
        if not state.context.get('command_bus'):
            state.context['command_bus'] = self._command_bus
        if not state.context.get('query_bus'):
            state.context['query_bus'] = self._query_bus
        if not state.context.get('event_bus'):
            state.context['event_bus'] = self.event_bus
        if not state.context.get('saga_manager'):
            state.context['saga_manager'] = self
        if self._event_store and not state.context.get('event_store'):
            state.context['event_store'] = self._event_store

        # UPDATED: Restore ProjectionRebuilder from parent service
        if self._parent_service and hasattr(self._parent_service, 'projection_rebuilder'):
            if self._parent_service.projection_rebuilder and not state.context.get('projection_rebuilder'):
                state.context['projection_rebuilder'] = self._parent_service.projection_rebuilder
                log.debug(f"Restored ProjectionRebuilder for saga {state.saga_id}")

        # Validate restored context
        if not state.context.get('command_bus'):
            raise RuntimeError("Failed to restore command bus to saga context")
        if not state.context.get('query_bus'):
            raise RuntimeError("Failed to restore query bus to saga context")

    async def _save_saga_state(self, state: SagaState) -> None:
        """OPTIMIZED: Persist saga state to Redis with reduced I/O"""
        key = self._get_saga_key(state.saga_id)
        data = json.dumps(state.to_dict())

        # Calculate TTL based on timeout + buffer
        ttl_seconds = int((state.timeout_at - datetime.now(timezone.utc)).total_seconds()) + 3600

        # Always save synchronously to ensure state is persisted
        await safe_set(key, data, ttl_seconds=max(ttl_seconds, 60))

    async def _load_saga_state(self, saga_id: uuid.UUID) -> Optional[SagaState]:
        """Load saga state from Redis and restore context"""
        key = self._get_saga_key(saga_id)
        data = await safe_get(key)

        if not data:
            return None

        state = SagaState.from_dict(json.loads(data))

        # ALWAYS restore non-serializable references
        await self._restore_context_references(state)

        return state

    async def _cleanup_aggregate_lock(self, state: SagaState) -> None:
        """FIXED: Clean up aggregate lock when saga completes"""
        conflict_key = state.context.get('conflict_key')
        saga_id = str(state.saga_id)

        if conflict_key:
            log.info(f"Cleaning up aggregate lock for {conflict_key} (saga {saga_id})")

            redis_key = f"saga_aggregate_lock:{conflict_key}"

            # Check if we own the lock
            existing = await safe_get(redis_key)
            if existing:
                try:
                    # Parse lock data - handle both JSON and eval formats
                    if isinstance(existing, str):
                        # Try JSON first
                        try:
                            import json
                            lock_data = json.loads(existing)
                        except:
                            # Fall back to eval for old format
                            try:
                                lock_data = eval(existing)
                            except:
                                log.error(f"Failed to parse lock data: {existing}")
                                # Force delete if we can't parse
                                await safe_delete(redis_key)
                                return
                    else:
                        lock_data = existing

                    if lock_data.get('saga_id') == saga_id:
                        await safe_delete(redis_key)
                        log.info(f"Released aggregate lock for {conflict_key}")
                    else:
                        log.warning(
                            f"Lock for {conflict_key} owned by different saga: "
                            f"{lock_data.get('saga_id')} (we are {saga_id})"
                        )
                except Exception as e:
                    log.error(f"Error releasing aggregate lock: {e}")
                    # Try to force delete if it's our lock
                    await safe_delete(redis_key)

            # Also check for unlock callback in context
            unlock_callback = state.context.get('_unlock_aggregate')
            if unlock_callback and callable(unlock_callback):
                try:
                    # Handle both sync and async callbacks
                    if asyncio.iscoroutinefunction(unlock_callback):
                        await unlock_callback()
                    else:
                        unlock_callback()
                    log.info(f"Executed unlock callback for {conflict_key}")
                except Exception as e:
                    log.error(f"Error executing unlock callback: {e}")

    async def start_saga(
            self,
            saga: BaseSaga,
            initial_context: Optional[Dict[str, Any]] = None
    ) -> uuid.UUID:
        """
        OPTIMIZED: Start a new saga execution with reduced initialization overhead
        """
        # Validate server context requirements FIRST
        if not self._initialized:
            raise RuntimeError(
                "Saga Manager not properly initialized. "
                "Both command_bus and query_bus must be set before starting sagas."
            )

        if not self._command_bus:
            raise RuntimeError(
                "Cannot start saga without command bus. "
                "Call set_command_bus() before starting any sagas."
            )

        if not self._query_bus:
            raise RuntimeError(
                "Cannot start saga without query bus. "
                "Call set_query_bus() before starting any sagas."
            )

        saga_start_time = time.time()

        # CRITICAL FIX (Nov 16, 2025): Build context BEFORE define_steps()
        # Bug: define_steps() was called before saga.context was set, causing Virtual Broker
        # detection to fail (broker_id was empty). This made VB sagas skip wait_for_event_propagation,
        # resulting in snapshots sent before accounts were projected to PostgreSQL.
        context = initial_context or {}

        # FIXED: Ensure CQRS buses are always available
        if 'command_bus' not in context or not context['command_bus']:
            context['command_bus'] = self._command_bus
        if 'query_bus' not in context or not context['query_bus']:
            context['query_bus'] = self._query_bus
        if 'event_bus' not in context or not context['event_bus']:
            context['event_bus'] = self.event_bus

        # Inject Event Store if available
        if self._event_store:
            context['event_store'] = self._event_store
            log.info(f"Event Store context injected for saga {saga.saga_id}")

        # Enhanced causation tracking
        causation_id = str(saga.saga_id)
        correlation_id = context.get('correlation_id', str(uuid.uuid4()))

        context['causation_id'] = causation_id
        context['correlation_id'] = correlation_id
        context['saga_manager'] = self  # For nested sagas

        # OPTIMIZED: Check for fast-track sagas
        if context.get('trigger_description', '').lower().find('virtual') != -1:
            saga.enable_fast_track()
            log.info(f"Fast-track enabled for saga {saga.saga_id}")

        # Final validation before starting
        if not context.get('command_bus'):
            raise RuntimeError("Command bus is None - cannot start saga")
        if not context.get('query_bus'):
            raise RuntimeError("Query bus is None - cannot start saga")

        # CRITICAL FIX: Assign context to saga BEFORE defining steps
        # This allows define_steps() to access context and detect broker type correctly
        saga.context = context

        # NOW define steps (can access self.context with broker_id)
        steps = saga.define_steps()
        timeout = saga.get_timeout()

        log.info(f"Starting saga {saga.saga_id} with full CQRS + Event Store context in SERVER")

        state = SagaState(
            saga_id=saga.saga_id,
            saga_type=saga.get_saga_type(),
            status=SagaStatus.STARTED,
            current_step=0,
            total_steps=len(steps),
            started_at=datetime.now(timezone.utc),
            timeout_at=datetime.now(timezone.utc) + timeout,
            context=context,
            event_store_enabled=self._event_store is not None,
            causation_chain=[causation_id],
            correlation_id=correlation_id
        )

        self._active_sagas[saga.saga_id] = state
        await self._save_saga_state(state)

        # OPTIMIZED: Publish saga started event asynchronously
        asyncio.create_task(self._publish_saga_event("SagaStarted", state))

        # OPTIMIZED: Start timeout monitor with reduced overhead
        if not saga.is_fast_track():
            monitor_task = asyncio.create_task(
                self._monitor_saga_timeout(saga.saga_id)
            )
            self._timeout_monitors[saga.saga_id] = monitor_task

        # Start execution
        asyncio.create_task(self._execute_saga(saga, state, steps))

        # Track performance
        self._performance_metrics["total_sagas"] += 1

        log.info(
            f"Started saga {saga.saga_id} of type {saga.get_saga_type()} "
            f"in {(time.time() - saga_start_time) * 1000:.2f}ms"
        )

        return saga.saga_id

    async def _execute_saga(
            self,
            saga: BaseSaga,
            state: SagaState,
            steps: List[SagaStep]
    ) -> None:
        """OPTIMIZED: Execute saga steps with reduced delays and better performance"""
        try:
            state.status = SagaStatus.IN_PROGRESS
            await self._save_saga_state(state)

            for i, step in enumerate(steps):
                if state.status != SagaStatus.IN_PROGRESS:
                    break

                state.current_step = i
                state._current_step_name = step.name  # FIXED: Set current step name
                step_start_time = time.time()

                # FIXED: Always reload state to ensure we have latest context
                reloaded_state = await self._load_saga_state(state.saga_id)
                if reloaded_state:
                    # Preserve local runtime state
                    reloaded_state._current_step_name = step.name
                    state = reloaded_state

                await self._save_saga_state(state)

                # Execute step with enhanced context validation
                success = False
                last_error = None

                # Use config for retry count
                retry_count = step.retry_count or saga_config.default_retry_count

                for attempt in range(retry_count):
                    try:
                        log.info(
                            f"⚡ Executing saga step {step.name} (attempt {attempt + 1}/{retry_count}) [SERVER]")

                        # Enhanced context validation
                        if not self._validate_step_context(state.context, step.name):
                            raise RuntimeError(f"Invalid CQRS + Event Store context for step {step.name}")

                        # Add causation tracking to step context
                        step_context = dict(state.context)
                        step_context['step_name'] = step.name
                        step_context['step_attempt'] = attempt + 1
                        step_context['causation_chain'] = state.causation_chain + [f"step:{step.name}"]

                        # OPTIMIZED: Reduced timeout for fast-track sagas
                        timeout_seconds = step.timeout_seconds
                        if saga.is_fast_track():
                            timeout_seconds = min(timeout_seconds, 10)  # Max 10s for fast-track

                        # Execute with timeout
                        result = await asyncio.wait_for(
                            step.execute(**step_context),
                            timeout=timeout_seconds
                        )

                        # FIXED: Store step result in dedicated step_results
                        state.step_results[step.name] = result

                        # Also store in context for backward compatibility
                        state.context[f"{step.name}_result"] = result

                        # Update context with result data if it's a dict
                        if isinstance(result, dict):
                            # Only update non-service keys
                            for key, value in result.items():
                                if key not in ['command_bus', 'query_bus', 'event_bus', 'event_store', 'saga_manager']:
                                    state.context[key] = value

                            # Track Event Store operations
                            if result.get('causation_id'):
                                state.causation_chain.append(f"result:{result['causation_id']}")

                        # Record compensation
                        compensation = CompensationRecord(
                            step_name=step.name,
                            compensate_func=step.compensate,
                            context=dict(step_context)  # Snapshot enhanced context
                        )
                        state.compensations.append(compensation)

                        # FIXED: Track step timing as float
                        step_execution_time = time.time() - step_start_time
                        state.step_timings[step.name] = float(step_execution_time)

                        # FIXED: Always save state synchronously to ensure context is persisted
                        await self._save_saga_state(state)

                        success = True
                        log.info(
                            f"Successfully completed saga step {step.name} [SERVER] "
                            f"in {step_execution_time * 1000:.2f}ms"
                        )
                        break

                    except asyncio.TimeoutError:
                        last_error = f"Step {step.name} timed out after {timeout_seconds}s"
                        log.error(f"{last_error}")

                    except Exception as e:
                        last_error = str(e)
                        log.error(f"Error in saga step {step.name}: {e}", exc_info=True)

                        if attempt < retry_count - 1:
                            # Use config for retry delays
                            retry_delay_seconds = saga_config.default_retry_delay_seconds
                            if saga.is_fast_track():
                                # Faster retries for virtual brokers
                                retry_delay_seconds = min(retry_delay_seconds, 0.5)

                            log.info(f"Retrying step {step.name} in {retry_delay_seconds}s")
                            await asyncio.sleep(retry_delay_seconds)

                if not success:
                    # Step failed - start compensation
                    state.errors.append({
                        "step": step.name,
                        "error": last_error,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "causation_chain": state.causation_chain
                    })

                    await self._compensate_saga(state, f"Step {step.name} failed: {last_error}")
                    return

            # All steps completed successfully
            state.status = SagaStatus.COMPLETED
            state.completed_at = datetime.now(timezone.utc)

            # Calculate total execution time
            total_execution_time = (state.completed_at - state.started_at).total_seconds()

            # Update performance metrics - FIXED: Ensure float
            current_avg = self._performance_metrics["average_execution_time"]
            total_count = self._performance_metrics["total_sagas"]
            new_avg = ((current_avg * (total_count - 1)) + total_execution_time) / total_count
            self._performance_metrics["average_execution_time"] = float(new_avg)

            await self._save_saga_state(state)

            # OPTIMIZED: Async event publishing
            asyncio.create_task(self._publish_saga_event("SagaCompleted", state))

            log.info(
                f"Saga {state.saga_id} completed successfully [SERVER] "
                f"in {total_execution_time:.2f}s"
            )

        except Exception as e:
            log.error(f"Unexpected error in saga execution: {e}", exc_info=True)
            await self._compensate_saga(state, f"Unexpected error: {str(e)}")

        finally:
            # Cleanup aggregate lock if exists
            await self._cleanup_aggregate_lock(state)

            # Cleanup
            self._active_sagas.pop(state.saga_id, None)

            # Cancel timeout monitor
            monitor = self._timeout_monitors.pop(state.saga_id, None)
            if monitor and not monitor.done():
                monitor.cancel()

    def _validate_step_context(self, context: Dict[str, Any], step_name: str) -> bool:
        """FIXED: Enhanced step context validation with better error messages"""
        # Command and Query buses are REQUIRED in server context
        if 'command_bus' not in context or context['command_bus'] is None:
            log.error(
                f"Step {step_name} missing REQUIRED command_bus in SERVER CONTEXT. "
                f"Context keys: {list(context.keys())}"
            )
            return False

        if 'query_bus' not in context or context['query_bus'] is None:
            log.error(
                f"Step {step_name} missing REQUIRED query_bus in SERVER CONTEXT. "
                f"Context keys: {list(context.keys())}"
            )
            return False

        # Event bus is always required
        if 'event_bus' not in context or context['event_bus'] is None:
            log.error(f"Step {step_name} missing required event_bus")
            return False

        # Event Store is optional but recommended
        if 'event_store' in context and context['event_store'] is not None:
            log.debug(f"Step {step_name} has Event Store context for causation tracking")
        else:
            log.debug(f"Step {step_name} running without Event Store context")

        # Causation tracking is required
        if 'causation_id' not in context:
            log.warning(f"Step {step_name} missing causation_id")

        log.debug(f"Step {step_name} validated with full CQRS context in SERVER")
        return True

    async def _compensate_saga(
            self,
            state: SagaState,
            reason: str
    ) -> None:
        """Execute compensating transactions with Event Store tracking"""
        log.warning(f"Starting compensation for saga {state.saga_id}: {reason} [SERVER]")

        # Track compensation start time
        compensation_start_time = datetime.now(timezone.utc)

        state.status = SagaStatus.COMPENSATING
        await self._save_saga_state(state)

        await self._publish_saga_event("SagaCompensationStarted", state, {"reason": reason})

        # Execute compensations in reverse order
        compensation_errors = []

        for compensation in reversed(state.compensations):
            if compensation.executed_at:
                continue  # Already compensated

            try:
                log.info(f"Executing compensation for step {compensation.step_name} [SERVER]")

                # FIXED: Ensure context has required services
                compensation_context = dict(compensation.context)

                # Restore service references
                if not compensation_context.get('command_bus'):
                    compensation_context['command_bus'] = self._command_bus
                if not compensation_context.get('query_bus'):
                    compensation_context['query_bus'] = self._query_bus
                if not compensation_context.get('event_bus'):
                    compensation_context['event_bus'] = self.event_bus

                # Add Event Store context if available
                if self._event_store:
                    compensation_context['event_store'] = self._event_store
                    compensation_context['compensation_saga_id'] = str(state.saga_id)

                await compensation.compensate_func(**compensation_context)

                compensation.executed_at = datetime.now(timezone.utc)
                await self._save_saga_state(state)

                log.info(f"Compensation completed for step {compensation.step_name}")

            except Exception as e:
                error_msg = f"Compensation failed for {compensation.step_name}: {str(e)}"
                log.error(f"{error_msg}", exc_info=True)

                compensation.error = str(e)
                compensation_errors.append({
                    "step": compensation.step_name,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "causation_chain": state.causation_chain
                })

        # Update final status
        if compensation_errors:
            state.status = SagaStatus.FAILED
            state.errors.extend(compensation_errors)

            # Send to manual intervention queue
            await self._send_to_manual_intervention(state, compensation_errors)
        else:
            state.status = SagaStatus.COMPENSATED

        state.completed_at = datetime.now(timezone.utc)
        await self._save_saga_state(state)

        # Clean up aggregate lock (CRITICAL: Always run even if compensation fails)
        # DEADLOCK FIX (Nov 16, 2025): Ensure lock cleanup never fails and blocks reconnection
        try:
            await self._cleanup_aggregate_lock(state)
        except Exception as e:
            log.error(f"Error cleaning up aggregate lock (non-fatal): {e}", exc_info=True)

        # FIXED: Calculate compensation duration as int milliseconds
        compensation_duration_ms = int(
            (datetime.now(timezone.utc) - compensation_start_time).total_seconds() * 1000
        )

        # Publish with duration
        await self._publish_saga_event(
            "SagaCompensationCompleted",
            state,
            {"compensation_duration_ms": compensation_duration_ms}
        )

        log.info(f"🏁 Compensation completed for saga {state.saga_id} in {compensation_duration_ms}ms")

    async def _monitor_saga_timeout(self, saga_id: uuid.UUID) -> None:
        """OPTIMIZED: Monitor saga for timeout with reduced overhead"""
        try:
            state = await self._load_saga_state(saga_id)
            if not state:
                return

            # Calculate time until timeout
            time_until_timeout = (state.timeout_at - datetime.now(timezone.utc)).total_seconds()

            if time_until_timeout > 0:
                # OPTIMIZED: Check periodically instead of sleeping full duration
                check_interval = min(5.0, time_until_timeout / 4.0)

                while time_until_timeout > 0:
                    await asyncio.sleep(min(check_interval, time_until_timeout))

                    # Reload state to check if saga completed
                    state = await self._load_saga_state(saga_id)
                    if not state or state.status not in (SagaStatus.STARTED, SagaStatus.IN_PROGRESS):
                        return

                    time_until_timeout = (state.timeout_at - datetime.now(timezone.utc)).total_seconds()

            # Check if saga is still active
            state = await self._load_saga_state(saga_id)
            if state and state.status in (SagaStatus.STARTED, SagaStatus.IN_PROGRESS):
                await self._handle_saga_timeout(saga_id)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error in timeout monitor for saga {saga_id}: {e}", exc_info=True)

    async def _handle_saga_timeout(self, saga_id: uuid.UUID) -> None:
        """Handle saga timeout with proper compensation events"""
        state = self._active_sagas.get(saga_id)
        if not state:
            return

        log.error(f"Saga {saga_id} timed out [SERVER]")

        # Start compensation with proper event structure
        compensation_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "SagaCompensationStarted",
            "saga_id": str(saga_id),
            "saga_type": state.saga_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_store_enabled": self._event_store is not None,
            "causation_chain": state.context.get('causation_chain', [str(saga_id)]),
            "correlation_id": state.context.get('correlation_id'),
            "version": 1,
            "compensation_reason": "Saga timed out",
            "steps_to_compensate": [],
            "current_errors": [],
            "reason": "Saga timed out",
            "failed_step": state.current_step_name,  # Add the missing field
            "type": "SagaCompensationStarted"
        }

        await self.event_bus.publish("saga.events", compensation_event)

        # Set timeout status and compensate
        state.status = SagaStatus.TIMED_OUT
        await self._save_saga_state(state)

        # Start compensation
        await self._compensate_saga(state, "Saga timed out")

    async def _publish_saga_event(
            self,
            event_type: str,
            state: SagaState,
            additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """OPTIMIZED: Publish saga lifecycle events asynchronously - FIXED numeric handling"""
        if not self.enable_monitoring:
            return

        try:
            # Base event data with Event Store enhancements
            event_data = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "saga_id": str(state.saga_id),
                "saga_type": state.saga_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_store_enabled": state.event_store_enabled,
                "causation_chain": state.causation_chain,
                "correlation_id": state.correlation_id,
                "version": 1
            }

            # Add specific fields based on event type
            if event_type == "SagaStarted":
                timeout_delta = state.timeout_at - state.started_at
                # FIXED: Ensure timeout_minutes is int
                timeout_minutes = int(timeout_delta.total_seconds() / 60)

                # Get serializable context
                serializable_context = {}
                for key, value in state.context.items():
                    if key in ['event_bus', 'event_store', 'saga_manager', 'command_bus', 'query_bus',
                               'interaction_service', 'auth_service', '_cleanup_conflict_key', '_cleanup_saga_id',
                               '_unlock_aggregate', 'virtual_broker_service', 'projection_rebuilder']:
                        continue
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_context[key] = value
                    elif isinstance(value, uuid.UUID):
                        serializable_context[key] = str(value)
                    elif isinstance(value, datetime):
                        serializable_context[key] = value.isoformat()

                event_data["initial_context"] = serializable_context
                event_data["timeout_minutes"] = timeout_minutes

            elif event_type == "SagaCompleted":
                serializable_context = {}
                for key, value in state.context.items():
                    if key in ['event_bus', 'event_store', 'saga_manager', 'command_bus', 'query_bus',
                               'interaction_service', 'auth_service', '_cleanup_conflict_key', '_cleanup_saga_id',
                               '_unlock_aggregate', 'virtual_broker_service', 'projection_rebuilder']:
                        continue
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_context[key] = value
                    elif isinstance(value, uuid.UUID):
                        serializable_context[key] = str(value)
                    elif isinstance(value, datetime):
                        serializable_context[key] = value.isoformat()

                event_data["final_context"] = serializable_context
                # FIXED: Ensure total_duration_ms is int
                event_data["total_duration_ms"] = int(
                    (state.completed_at - state.started_at).total_seconds() * 1000) if state.completed_at else 0
                event_data["steps_executed"] = state.current_step + 1

                # FIXED: Ensure step_timings values are floats
                event_data["step_timings"] = {k: float(v) for k, v in state.step_timings.items()}

            elif event_type == "SagaCompensationStarted":
                event_data["compensation_reason"] = additional_data.get("reason", "") if additional_data else ""
                event_data["steps_to_compensate"] = [c.step_name for c in state.compensations]
                event_data["current_errors"] = state.errors
                event_data["reason"] = additional_data.get("reason", "") if additional_data else ""
                event_data["failed_step"] = state.current_step_name

            elif event_type == "SagaCompensationCompleted":
                compensated_steps = [
                    c.step_name for c in state.compensations if c.executed_at is not None
                ]
                event_data["compensated_steps"] = compensated_steps
                event_data["compensated_steps_count"] = len(compensated_steps)
                event_data["had_errors"] = len(state.errors) > 0
                event_data["final_status"] = state.status.value

                # Add compensation duration if provided
                if additional_data and "compensation_duration_ms" in additional_data:
                    # FIXED: Ensure compensation_duration_ms is int
                    event_data["compensation_duration_ms"] = int(additional_data["compensation_duration_ms"])
                else:
                    # Default to 0 if not provided
                    event_data["compensation_duration_ms"] = 0

            # Add any additional data provided
            if additional_data:
                for key, value in additional_data.items():
                    if key not in event_data:
                        # FIXED: Handle numeric conversions in additional_data
                        if isinstance(value, float) and key.endswith('_ms'):
                            event_data[key] = int(value)
                        elif isinstance(value, float) and key.endswith('_seconds'):
                            event_data[key] = float(value)
                        else:
                            event_data[key] = value

            # Publish the event asynchronously
            await self.event_bus.publish("saga.events", event_data)

        except Exception as e:
            log.error(f"Failed to publish saga event {event_type}: {e}")

    async def _send_to_manual_intervention(
            self,
            state: SagaState,
            errors: List[Dict[str, Any]]
    ) -> None:
        """Send failed saga to manual intervention queue with Event Store context"""
        intervention_data = {
            "saga_id": str(state.saga_id),
            "saga_type": state.saga_type,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "errors": errors,
            "state": state.to_dict(),
            "event_store_enabled": state.event_store_enabled,
            "causation_chain": state.causation_chain,
            "correlation_id": state.correlation_id
        }

        await self.event_bus.publish("saga.manual-intervention", intervention_data)

        log.error(f"Saga {state.saga_id} sent to manual intervention queue [SERVER]")

    async def get_saga_status(self, saga_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get current status of a saga with Event Store context"""
        state = await self._load_saga_state(saga_id)
        if not state:
            return None

        return {
            "saga_id": str(saga_id),
            "saga_type": state.saga_type,
            "status": state.status.value,
            "progress": f"{state.current_step}/{state.total_steps}",
            "started_at": state.started_at.isoformat(),
            "timeout_at": state.timeout_at.isoformat(),
            "errors": len(state.errors),
            "has_command_bus": 'command_bus' in state.context,
            "has_query_bus": 'query_bus' in state.context,
            "has_event_store": state.event_store_enabled,
            "causation_chain": state.causation_chain,
            "correlation_id": state.correlation_id,
            "step_timings": state.step_timings,
            "context": "SERVER"
        }

    async def retry_compensation(self, saga_id: uuid.UUID) -> bool:
        """Manually retry compensation for a failed saga"""
        state = await self._load_saga_state(saga_id)
        if not state:
            return False

        if state.status != SagaStatus.FAILED:
            log.warning(f"Cannot retry compensation for saga in status {state.status}")
            return False

        await self._compensate_saga(state, "Manual retry requested")
        return True

    def get_active_sagas_count(self) -> int:
        """Get count of active sagas"""
        return len(self._active_sagas)

    async def get_saga_registry_info(self) -> Dict[str, Any]:
        """Get information about registered saga types with Event Store context"""
        return {
            "registered_saga_types": list(self._saga_registry.keys()),
            "active_sagas": len(self._active_sagas),
            "command_bus_available": self._command_bus is not None,
            "query_bus_available": self._query_bus is not None,
            "event_store_available": self._event_store is not None,
            "parent_service_available": self._parent_service is not None,
            "initialized": self._initialized,
            "performance_metrics": self._performance_metrics,
            "context": "SERVER_ONLY",
            "config": {
                "default_timeout_seconds": saga_config.default_timeout_seconds,
                "default_retry_count": saga_config.default_retry_count,
                "default_retry_delay_seconds": saga_config.default_retry_delay_seconds,
                "virtual_broker_speed_factor": saga_config.virtual_broker_speed_factor
            }
        }