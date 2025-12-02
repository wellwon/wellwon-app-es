# =============================================================================
# File: app/infra/event_bus/event_bus.py
# Description: Universal async EventBus for CQRS/Event Sourcing
#              for 
# - Uses app.common.base_event_model.BaseEvent.
# - Uses app.models.event_registry.py for validation.
# =============================================================================

from __future__ import annotations

import asyncio
import os
import uuid
import logging
import json
from pathlib import Path
from typing import (
    Any, Awaitable, Callable, Dict, List,
    TypeAlias, Optional, AsyncIterator, Set
)
from pydantic import ValidationError
from datetime import datetime, timezone
import time

from app.infra.event_bus.transport_adapter import TransportAdapter
from app.common.base.base_model import BaseEvent as CommonBaseEvent
from app.infra.event_bus.event_registry import EVENT_TYPE_TO_PYDANTIC_MODEL

# Import NEW reliability patterns from /app/infra/reliability/
from app.infra.reliability.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
)
from app.infra.reliability.retry import retry_async, RetryConfig

# Import configuration
from app.config.eventbus_config import EventBusConfig, get_eventbus_config

log = logging.getLogger("wellwon.event_bus")

Handler: TypeAlias = Callable[[Dict[str, Any]], Awaitable[None]]
FilterFunc: TypeAlias = Callable[[Dict[str, Any]], bool]


class EventBus:
    def __init__(
            self,
            adapter: TransportAdapter,
            validate_on_publish: bool = True,
            event_bus_config: Optional[EventBusConfig] = None,
            transport_config: Optional[TransportConfig] = None
    ):
        if not isinstance(adapter, TransportAdapter):
            raise TypeError("EventBus requires a valid TransportAdapter instance.")

        self._adapter: TransportAdapter = adapter
        self._validate_on_publish: bool = validate_on_publish
        self._stream_consumer_tasks: List[asyncio.Task] = []
        self._is_shutting_down: bool = False

        # Configuration
        self._event_bus_config = event_bus_config or EventBusConfig.from_env()
        self._transport_config = transport_config or TransportConfig.from_env()

        # NEW: Circuit breakers using new patterns
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._critical_channels: Set[str] = set()

        # NEW: Default retry configurations using new patterns
        self._default_stream_retry_config = RetryConfig(
            max_attempts=self._event_bus_config.publish_retry_max_attempts,
            initial_delay_ms=self._event_bus_config.publish_retry_initial_delay_ms,
            max_delay_ms=self._event_bus_config.publish_retry_max_delay_ms,
            backoff_factor=self._event_bus_config.publish_retry_backoff_factor,
        )

        # Get version dynamically
        from app import __version__

        log.info(
            f"EventBus initialized with adapter: {type(self._adapter).__name__}, "
            f"validation_on_publish: {self._validate_on_publish}, "
            f"reliability features enabled (version {__version__})"
        )

    def _get_circuit_breaker(self, channel: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a channel using new patterns."""
        if channel not in self._circuit_breakers:
            # Check if we have specific configuration for this topic
            topic_config = self._event_bus_config.get_topic_config(channel)

            if topic_config or channel in self._critical_channels:
                # Use more aggressive settings for critical channels
                config = CircuitBreakerConfig(
                    name=f"eventbus-{channel}",  # Add this line
                    failure_threshold=3,
                    success_threshold=2,
                    reset_timeout_seconds=15,
                    half_open_max_calls=2,
                )
            else:
                # Use default config from EventBusConfig
                config = CircuitBreakerConfig(
                    name=f"eventbus-{channel}",  # Add this line
                    failure_threshold=self._event_bus_config.publish_circuit_breaker_failure_threshold,
                    success_threshold=self._event_bus_config.publish_circuit_breaker_success_threshold,
                    reset_timeout_seconds=self._event_bus_config.publish_circuit_breaker_timeout_seconds,
                    half_open_max_calls=self._event_bus_config.publish_circuit_breaker_half_open_calls,
                )

            # Get circuit breaker instance using new pattern
            self._circuit_breakers[channel] = get_circuit_breaker(
                f"eventbus-{channel}",
                config=config
            )

        return self._circuit_breakers[channel]

    def mark_channel_as_critical(self, channel: str) -> None:
        """Mark a channel as critical for additional reliability measures."""
        self._critical_channels.add(channel)

        # Update the circuit breaker if it already exists
        if channel in self._circuit_breakers:
            # Replace with a more sensitive circuit breaker
            config = CircuitBreakerConfig(
                name=f"eventbus-{channel}-critical",
                failure_threshold=3,
                success_threshold=2,
                reset_timeout_seconds=15,
                half_open_max_calls=2,
            )
            self._circuit_breakers[channel] = get_circuit_breaker(
                f"eventbus-{channel}-critical",
                config=config
            )

    @staticmethod
    def _enrich_and_prepare_event_dict(event_data: Dict[str, Any], context_for_log: Optional[str] = None) -> Dict[
        str, Any]:
        """
        Ensures base event fields (event_id, timestamp, event_type, version) are present
        and correctly formatted as strings for JSON serialization.
        """
        if not isinstance(event_data, dict):
            log.error(
                f"Cannot enrich non-dict event for '{context_for_log}': {type(event_data)}. Data: {str(event_data)[:200]}")
            raise TypeError("Event data for enrichment must be a dict")

        # Ensure event_id is a string
        event_id_val = event_data.get("event_id")
        if not isinstance(event_id_val, str) or not event_id_val:
            event_data["event_id"] = str(uuid.uuid4())
            log.debug(
                f"EventBus: Generated event_id '{event_data['event_id']}' for event (type: {event_data.get('event_type')}) in '{context_for_log}'.")

        # Ensure timestamp is an ISO format string
        ts_val = event_data.get("timestamp")
        if not isinstance(ts_val, str):
            original_ts = ts_val
            event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
            log.debug(
                f"EventBus: Timestamp for event {event_data['event_id']} was '{original_ts}', set to ISO string '{event_data['timestamp']}'.")

        # Ensure version (integer) is present
        event_data.setdefault("version", CommonBaseEvent.model_fields["version"].default)

        # Ensure event_type is present and set 'type' for compatibility if the validator uses it
        event_type_val = event_data.get("event_type")
        if not event_type_val and "type" in event_data:  # Fallback for the old 'type' field
            event_type_val = event_data["type"]
            event_data["event_type"] = event_type_val

        if not event_type_val:
            log.error(
                f"Event being enriched for '{context_for_log}' is missing 'event_type'. ID: {event_data.get('event_id')}")
            raise ValueError("Event missing required 'event_type' field!")

        event_data["type"] = event_type_val  # Ensure the 'type' field exists if the validator relies on it

        # Remove old schema_version if present, as new BaseEvent uses 'version'
        event_data.pop("schema_version", None)

        return event_data

    def _validate_event_payload(self, event_payload_dict: Dict[str, Any], stream_name: str = None) -> bool:
        """
        Validates the event payload against its Pydantic model in the registry.

        HIGH FIX #6 (2025-11-14): Added stream_name for critical channel validation.
        """
        if not self._validate_on_publish:
            # HIGH FIX #6: Warn if validation disabled for critical channels
            if stream_name and stream_name in self._critical_channels:
                log.warning(
                    f"PRODUCTION WARNING: Event validation DISABLED for CRITICAL channel '{stream_name}'. "
                    f"Malformed events may enter stream. Set EVENTBUS_VALIDATE_ON_PUBLISH=true for production."
                )
            return True

        event_type_str = event_payload_dict.get("event_type")
        if not event_type_str:
            log.error(f"Event validation failed: 'event_type' field missing. ID: {event_payload_dict.get('event_id')}")
            return False

        pydantic_model_class = EVENT_TYPE_TO_PYDANTIC_MODEL.get(str(event_type_str))

        # Fallback to auto-registered events if not in merged registry
        if not pydantic_model_class:
            from app.infra.event_bus.event_decorators import get_auto_registered_events
            auto_events = get_auto_registered_events()
            pydantic_model_class = auto_events.get(str(event_type_str))

        if not pydantic_model_class:
            log.warning(
                f"No Pydantic model registered in EVENT_TYPE_TO_PYDANTIC_MODEL for event_type '{event_type_str}'. "
                f"Skipping validation for this event. Event ID: {event_payload_dict.get('event_id')}"
            )
            return True

        try:
            pydantic_model_class.model_validate(event_payload_dict)
            log.debug(
                f"Event validation successful for type '{event_type_str}', ID '{event_payload_dict.get('event_id')}'")
            return True
        except ValidationError as ve:
            log.error(
                f"Event schema validation FAILED for '{event_type_str}', ID '{event_payload_dict.get('event_id')}': "
                f"{ve.errors(include_url=False)}. Payload preview: {str(event_payload_dict)[:500]}"
            )
            return False
        except Exception as val_ex:
            log.error(
                f"Unexpected error during event validation for '{event_type_str}', ID '{event_payload_dict.get('event_id')}': {val_ex}",
                exc_info=True
            )
            return False

    async def publish(self, stream_name: str, event_data_dict: Dict[str, Any]) -> None:
        """Publishes an event to a durable stream with reliability features."""
        if self._is_shutting_down:
            log.warning(f"Publish attempt on '{stream_name}' while closing event bus.")
            return

        # Get circuit breaker for this stream
        circuit = self._get_circuit_breaker(stream_name)

        # HIGH FIX #5 (2025-11-14): Don't drop critical events when circuit breaker is open
        # Check if the circuit allows execution
        if not circuit.can_execute():
            # If this is a critical channel, send to DLQ instead of dropping
            if stream_name in self._critical_channels:
                log.error(
                    f"Circuit breaker for CRITICAL stream '{stream_name}' is OPEN. "
                    f"Sending event to DLQ for retry instead of dropping."
                )
                # Send to DLQ (handled by transport adapter's DLQ service)
                # Event will be retried later when circuit recovers
                try:
                    await self._adapter._send_to_dlq(  # noqa
                        topic=stream_name,
                        message=json.dumps(event_data_dict).encode('utf-8'),
                        error="Circuit breaker OPEN",
                        metadata={"reason": "circuit_breaker_open", "critical": True}
                    )
                except Exception as dlq_error:
                    log.error(f"Failed to send critical event to DLQ: {dlq_error}")
                return
            else:
                # Non-critical channel - safe to skip
                log.warning(f"Circuit breaker for stream '{stream_name}' is OPEN, skipping publish")
                return

        prepared_event_dict: Dict[str, Any]
        try:
            prepared_event_dict = self._enrich_and_prepare_event_dict(event_data_dict, stream_name)
        except (TypeError, ValueError) as e_enrich:
            log.error(
                f"Failed to prepare event for stream '{stream_name}'. Error: {e_enrich}. "
                f"Original data preview: {str(event_data_dict)[:500]}"
            )
            return

        if not self._validate_event_payload(prepared_event_dict, stream_name=stream_name):
            log.error(
                f"Invalid event for Stream '{stream_name}' after preparation. Not sent. "
                f"Type: {prepared_event_dict.get('event_type')}, ID: {prepared_event_dict.get('event_id')}"
            )
            return

        # Get retry configuration
        topic_config = self._event_bus_config.get_topic_config(stream_name)
        if topic_config or stream_name in self._critical_channels:
            # Use more aggressive retry for configured/critical topics
            retry_config = RetryConfig(
                max_attempts=5,
                initial_delay_ms=200,
                max_delay_ms=5000,
                backoff_factor=2.0,
            )
        else:
            retry_config = self._default_stream_retry_config

        try:
            # Use retry_async with circuit breaker protection
            async def publish_with_circuit():
                return await self._adapter.publish(stream_name, prepared_event_dict)

            await retry_async(
                lambda: circuit.execute_async(publish_with_circuit),
                retry_config=retry_config,
                context=f"publish({stream_name})"  # FIXED (2025-11-14): Correct method name
            )

            log.debug(
                f"Published to Stream '{stream_name}': "
                f"{prepared_event_dict.get('event_type')}/{prepared_event_dict.get('event_id')}"
            )
        except Exception as e_adapter_pub:
            log.error(
                f"Failed to publish to Stream '{stream_name}' after retries: {e_adapter_pub}",
                exc_info=True
            )

            # Send to DLQ if configured
            if self._event_bus_config.enable_dlq:
                await self._send_to_dlq(stream_name, prepared_event_dict, e_adapter_pub)

    async def publish_batch(self, channel: str, events_data_list: List[Dict[str, Any]],
                            partition_key: Optional[str] = None) -> None:
        """Publishes a batch of events with reliability."""
        if self._is_shutting_down:
            log.warning(f"Publish_batch attempt on '{channel}' while closing.")
            return

        # Get circuit breaker for this channel
        circuit = self._get_circuit_breaker(channel)

        # Check if the circuit allows execution
        if not circuit.can_execute():
            log.warning(f"Circuit breaker for channel '{channel}' is OPEN, skipping batch publish")
            return

        valid_prepared_events: List[Dict[str, Any]] = []
        for i, ev_data in enumerate(events_data_list):
            try:
                prepared = self._enrich_and_prepare_event_dict(ev_data, f"{channel} batch item {i}")
                if self._validate_event_payload(prepared, stream_name=channel):
                    valid_prepared_events.append(prepared)
                else:
                    log.error(
                        f"Event at index {i} in batch for '{channel}' failed validation. "
                        f"Type: {prepared.get('event_type')}, ID: {prepared.get('event_id')}"
                    )
            except (TypeError, ValueError) as e_enrich_batch:
                log.error(
                    f"Failed to prepare event at index {i} in batch for '{channel}': {e_enrich_batch}. "
                    f"Original: {str(ev_data)[:200]}"
                )

        if not valid_prepared_events:
            log.info(f"No valid events to publish in batch to '{channel}'.")
            return

        # Get retry configuration
        topic_config = self._event_bus_config.get_topic_config(channel)
        if topic_config or channel in self._critical_channels:
            retry_config = RetryConfig(
                max_attempts=4,
                initial_delay_ms=200,
                max_delay_ms=5000,
                backoff_factor=2.0,
            )
        else:
            retry_config = self._default_stream_retry_config

        try:
            # Use retry_async with circuit breaker protection
            async def publish_batch_with_circuit():
                return await self._adapter.publish_batch(channel, valid_prepared_events, partition_key)

            await retry_async(
                lambda: circuit.execute_async(publish_batch_with_circuit),
                retry_config=retry_config,
                context=f"publish_batch({channel})"
            )

            log.debug(f"Published batch of {len(valid_prepared_events)} events to '{channel}'")
        except Exception as e:
            log.error(f"Failed to publish batch to '{channel}' after retries: {e}", exc_info=True)

            # Send to DLQ if configured
            if self._event_bus_config.enable_dlq:
                for event in valid_prepared_events:
                    await self._send_to_dlq(channel, event, e)

    @staticmethod
    async def _safe_execute_handler_wrapper(handler: Handler, event: Dict[str, Any], context: str,
                                            handler_type: str) -> None:
        """Safely execute handler with error handling."""
        try:
            await handler(event)
        except asyncio.CancelledError:
            log.debug(f"{handler_type} handler for '{context}' cancelled. Event ID: {event.get('event_id', 'N/A')}")
        except Exception:
            log.exception(f"Error in {handler_type} handler for '{context}'. Event ID: {event.get('event_id')}")

    async def subscribe(
            self, channel: str, handler: Handler, group: str, consumer: str,
            filter_fn: Optional[FilterFunc] = None,
            batch_size: int = int(os.getenv("EVENT_BUS_SUB_BATCH_SIZE", "10")),
            block_ms: int = int(os.getenv("EVENT_BUS_SUB_BLOCK_MS", "10000"))
    ) -> None:
        """Subscribe to a durable stream with reliability."""
        if self._is_shutting_down:
            log.warning(f"Cannot subscribe to '{channel}': shutting down.")
            return

        async def inner_handler_for_adapter(event_dict: Dict[str, Any]):
            if self._is_shutting_down:
                return
            if filter_fn and not filter_fn(event_dict):
                log.debug(
                    f"Stream event filtered out for {channel}/{group}/{consumer}. Event ID: {event_dict.get('event_id')}")
                return
            await self._safe_execute_handler_wrapper(handler, event_dict, f"{channel}/{group}/{consumer}", "Stream")

        try:
            # This task will run the adapter's stream_consume loop
            task = asyncio.create_task(
                self._adapter.stream_consume(
                    channel=channel, handler=inner_handler_for_adapter, group=group, consumer=consumer,
                    batch_size=batch_size, block_ms=block_ms
                )
            )
            self._stream_consumer_tasks.append(task)
            log.info(f"Started stream consumer task for '{channel}', group '{group}', consumer '{consumer}'.")
        except Exception as e:
            log.error(f"Failed to start stream consumer task '{channel}/{group}/{consumer}': {e}", exc_info=True)

    async def stream(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        """Raw stream access from the underlying adapter."""
        if self._is_shutting_down:
            log.warning(f"Attempt to read raw stream '{channel}' while shutting down.")
            return
        try:
            async for ev in self._adapter.stream(channel):
                if self._is_shutting_down:
                    break
                yield ev
        except NotImplementedError:
            log.error(f"Adapter does not support raw streaming for '{channel}'.")
            return
        except Exception:
            log.exception(f"Error reading raw stream '{channel}'.")
            return

    async def stream_consume(
            self, channel: str, handler: Handler, group: str, consumer: str,
            batch_size: int = 10, block_ms: int = 15000
    ) -> None:
        """Direct proxy for stream consume with retry."""
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=500,
            max_delay_ms=5000,
            backoff_factor=2.0,
        )

        try:
            await retry_async(
                self._adapter.stream_consume,
                channel, handler, group, consumer, batch_size, block_ms,
                retry_config=retry_config,
                context=f"stream_consume({channel}/{group}/{consumer})"
            )
        except Exception as e:
            log.error(f"Failed to start stream_consume for '{channel}/{group}/{consumer}': {e}", exc_info=True)

    async def _write_to_dlq_fallback(self, event: Dict[str, Any], error: Exception) -> None:
        """
        Last resort fallback: Write failed DLQ event to local file to prevent data loss.
        This is only called when DLQ publish itself fails.
        """
        try:
            # Create fallback directory if it doesn't exist
            fallback_dir = Path(os.getenv("DLQ_FALLBACK_DIR", "/var/log/wellwon/dlq_fallback"))
            fallback_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped filename for event
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            event_id = event.get("event_id", "unknown")
            filename = fallback_dir / f"dlq_failure_{timestamp}_{event_id}.json"

            # Write event to file with metadata
            fallback_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dlq_publish_error": str(error),
                "event": event
            }

            # Use async file I/O to avoid blocking
            import aiofiles
            async with aiofiles.open(filename, 'w') as f:
                await f.write(json.dumps(fallback_data, indent=2, default=str))

            log.critical(f"DLQ fallback: Event written to {filename}")

        except Exception as fallback_error:
            # Ultimate fallback: Just log to stderr
            log.critical(
                f"FATAL: DLQ fallback file write failed. Event data: {json.dumps(event, default=str)[:1000]}. "
                f"Fallback error: {fallback_error}",
                exc_info=True
            )

    async def _send_to_dlq(self, channel: str, event: Dict[str, Any], error: Exception) -> None:
        """Send failed event to dead letter queue with fallback logging."""
        if not self._event_bus_config.enable_dlq:
            return

        dlq_topic = f"{channel}{self._event_bus_config.dlq_topic_suffix}"
        dlq_event = {
            **event,
            "_dlq_metadata": {
                "original_channel": channel,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": event.get("_dlq_metadata", {}).get("retry_count", 0) + 1
            }
        }

        try:
            # Send to DLQ without retry to avoid infinite loops
            await self._adapter.publish(dlq_topic, dlq_event)
            log.info(f"Sent failed event to DLQ: {dlq_topic}, event_id: {event.get('event_id')}")
        except Exception as dlq_error:
            # CRITICAL: DLQ publish failed - use fallback file logging as last resort
            log.critical(
                f"CRITICAL: Failed to send event to DLQ '{dlq_topic}'. "
                f"Event will be logged to fallback file. Error: {dlq_error}",
                exc_info=True
            )
            # Last resort: Write to fallback file to prevent data loss
            await self._write_to_dlq_fallback(dlq_event, dlq_error)

    async def close(self) -> None:
        """Gracefully shut down the event bus."""
        if self._is_shutting_down:
            log.info("EventBus already in shutdown process.")
            return

        log.info("EventBus initiating graceful shutdown...")
        self._is_shutting_down = True

        # Cancel all active stream consumer tasks
        tasks_to_cancel: List[asyncio.Task] = self._stream_consumer_tasks

        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()

        if tasks_to_cancel:
            log.debug(f"Waiting for {len(tasks_to_cancel)} EventBus tasks to complete cancellation...")
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            log.info("All EventBus active tasks processed for shutdown.")

        self._stream_consumer_tasks.clear()

        try:
            await self._adapter.close()
            log.info("Transport adapter successfully closed.")
        except Exception:
            log.exception("Error closing transport adapter during EventBus shutdown.")
        log.info("EventBus shutdown complete.")

    async def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get the status of all circuit breakers for monitoring."""
        status = {}
        for channel, cb in self._circuit_breakers.items():
            metrics = cb.get_metrics()
            status[channel] = {
                "state": cb.get_state().name,
                "failure_count": metrics.failure_count,
                "consecutive_successes": metrics.consecutive_successes,
                "total_failures": metrics.total_failures,
                "total_success": metrics.total_success,
                "last_failure_time": metrics.last_failure_time,
            }
        return status

    async def health_check(self) -> Dict[str, Any]:
        """Get comprehensive health status for the event bus system."""
        # Get version dynamically
        from app import __version__

        results = {
            "circuit_breakers": await self.get_circuit_breaker_status(),
            "timestamp": time.time(),
            "version": __version__,
            "is_shutting_down": self._is_shutting_down,
        }

        # Get open circuits
        open_circuits = [
            channel for channel, status in results["circuit_breakers"].items()
            if status["state"] == "OPEN"
        ]
        results["open_circuits"] = open_circuits
        results["open_circuits_count"] = len(open_circuits)

        # Add adapter health check if available
        try:
            adapter_health = await self._adapter.health_check()
            results["adapter"] = {
                "healthy": adapter_health.is_healthy,
                "details": adapter_health.details
            }
        except Exception as e:
            log.error(f"Error getting adapter health: {e}", exc_info=True)
            results["adapter"] = {
                "healthy": False,
                "details": {"error": str(e)}
            }

        # Overall system health
        results["healthy"] = (
                len(open_circuits) == 0 and
                results["adapter"]["healthy"] and
                not self._is_shutting_down
        )

        # Add configuration info
        results["config"] = {
            "dlq_enabled": self._event_bus_config.enable_dlq,
            "validation_enabled": self._validate_on_publish,
            "critical_channels": list(self._critical_channels),
            "total_channels_monitored": len(self._circuit_breakers),
        }

        return results

    async def check_connection(self) -> bool:
        """Quick check if the event bus connection to the transport is working."""
        try:
            return await self._adapter.ping()
        except Exception as e:
            log.error(f"Error pinging adapter: {e}")
            return False


# Factory function - compatible with original
def init_event_bus(
        adapter: TransportAdapter,
        validate_on_publish: bool = True,
        event_bus_config: Optional[EventBusConfig] = None,
        transport_config: Optional[TransportConfig] = None
) -> EventBus:
    """Initialize EventBus with optional configuration."""
    return EventBus(
        adapter,
        validate_on_publish=validate_on_publish,
        event_bus_config=event_bus_config,
        transport_config=transport_config
    )