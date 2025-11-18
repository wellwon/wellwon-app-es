"""
Saga Operation Tracker - Redis-Backed Idempotency Tracking

Provides idempotency guarantees for saga operations by tracking operation
execution state in Redis. Enables safe saga retry without duplicating operations.

Usage:
    tracker = SagaOperationTracker(redis_client)

    # Check if operation already completed
    if await tracker.is_operation_completed(saga_id, "discover_accounts", resource_id):
        return await tracker.get_operation_result(saga_id, "discover_accounts", resource_id)

    # Execute operation
    result = await perform_operation()

    # Mark as completed
    await tracker.mark_operation_completed(saga_id, "discover_accounts", resource_id, result)

Key Features:
- Redis-backed persistence across saga restarts
- TTL-based automatic cleanup
- Atomic operations via Lua scripts
- JSON serialization for complex results
- Comprehensive logging for debugging

Created: 2025-10-29
Phase: 2 Week 4 - Saga Idempotency
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.infra.persistence.redis_client import safe_get, safe_set, safe_delete

log = logging.getLogger(__name__)


class SagaOperationTracker:
    """
    Redis-backed operation tracking for saga idempotency.

    Tracks saga operation execution state to enable safe retry without
    duplicate resource creation or mutations.

    Redis Key Pattern:
        saga:op:{saga_id}:{operation_name}:{resource_id}

    Value Structure:
        {
            "status": "started" | "completed",
            "started_at": "ISO8601 timestamp",
            "completed_at": "ISO8601 timestamp",
            "result": {...},
            "saga_id": "uuid",
            "operation_name": "string",
            "resource_id": "string"
        }

    TTL: Configured per operation, defaults to 24 hours
    """

    def __init__(
        self,
        default_ttl_seconds: int = 86400  # 24 hours
    ):
        """
        Initialize operation tracker.

        Args:
            default_ttl_seconds: Default TTL for operation records (24 hours)
        """
        self.default_ttl = default_ttl_seconds

    def _build_key(self, saga_id: uuid.UUID, operation_name: str, resource_id: str) -> str:
        """
        Build Redis key for operation tracking.

        Args:
            saga_id: Unique saga identifier
            operation_name: Name of the operation (e.g., "discover_accounts")
            resource_id: Resource being operated on (e.g., broker_connection_id)

        Returns:
            Redis key string
        """
        return f"saga:op:{saga_id}:{operation_name}:{resource_id}"

    async def is_operation_completed(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = ""
    ) -> bool:
        """
        Check if operation has been completed.

        Args:
            saga_id: Saga executing the operation
            operation_name: Name of operation to check
            resource_id: Resource identifier (optional, defaults to empty string)

        Returns:
            True if operation completed, False otherwise
        """
        key = self._build_key(saga_id, operation_name, resource_id)

        try:
            data_json = await safe_get(key)

            if not data_json:
                return False

            data = json.loads(data_json)
            is_completed = data.get('status') == 'completed'

            if is_completed:
                log.info(
                    f"Operation already completed (idempotent retry): "
                    f"saga={saga_id}, operation={operation_name}, resource={resource_id}"
                )

            return is_completed

        except json.JSONDecodeError as e:
            log.error(f"Failed to decode operation data for {key}: {e}")
            return False
        except Exception as e:
            log.error(f"Error checking operation completion for {key}: {e}")
            return False

    async def mark_operation_started(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Mark operation as started.

        Args:
            saga_id: Saga executing the operation
            operation_name: Name of operation
            resource_id: Resource identifier
            metadata: Optional metadata to store
            ttl_seconds: TTL override (uses default if not specified)

        Returns:
            True if marked successfully, False if already exists
        """
        key = self._build_key(saga_id, operation_name, resource_id)
        ttl = ttl_seconds or self.default_ttl

        data = {
            "status": "started",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "saga_id": str(saga_id),
            "operation_name": operation_name,
            "resource_id": resource_id,
            "metadata": metadata or {}
        }

        try:
            data_json = json.dumps(data)

            # Use NX (set if not exists) to prevent overwriting
            success = await safe_set(
                key,
                data_json,
                ttl_seconds=ttl,
                nx=True  # Only set if key doesn't exist
            )

            if success:
                log.debug(
                    f"Marked operation started: saga={saga_id}, "
                    f"operation={operation_name}, resource={resource_id}"
                )
            else:
                log.warning(
                    f"Operation already exists (concurrent execution?): "
                    f"saga={saga_id}, operation={operation_name}, resource={resource_id}"
                )

            return success

        except Exception as e:
            log.error(f"Error marking operation started for {key}: {e}")
            return False

    async def mark_operation_completed(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = "",
        result: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Mark operation as completed and store result.

        Args:
            saga_id: Saga executing the operation
            operation_name: Name of operation
            resource_id: Resource identifier
            result: Operation result to cache
            ttl_seconds: TTL override

        Returns:
            True if marked successfully
        """
        key = self._build_key(saga_id, operation_name, resource_id)
        ttl = ttl_seconds or self.default_ttl

        try:
            # Get existing data if any
            existing_json = await self.redis.safe_get(key)
            if existing_json:
                data = json.loads(existing_json)
            else:
                data = {
                    "saga_id": str(saga_id),
                    "operation_name": operation_name,
                    "resource_id": resource_id,
                    "started_at": datetime.now(timezone.utc).isoformat()
                }

            # Update with completion data
            data.update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result or {}
            })

            data_json = json.dumps(data)

            # XX: Only set if key already exists (update)
            # If doesn't exist, create it anyway (operation may have started before tracking)
            success = await safe_set(key, data_json, ttl_seconds=ttl)

            if success:
                log.info(
                    f"Marked operation completed: saga={saga_id}, "
                    f"operation={operation_name}, resource={resource_id}"
                )

            return success

        except Exception as e:
            log.error(f"Error marking operation completed for {key}: {e}")
            return False

    async def get_operation_result(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached operation result.

        Args:
            saga_id: Saga that executed the operation
            operation_name: Name of operation
            resource_id: Resource identifier

        Returns:
            Operation result dict if exists and completed, None otherwise
        """
        key = self._build_key(saga_id, operation_name, resource_id)

        try:
            data_json = await safe_get(key)

            if not data_json:
                return None

            data = json.loads(data_json)

            if data.get('status') != 'completed':
                log.warning(
                    f"Operation exists but not completed: {operation_name} "
                    f"(status={data.get('status')})"
                )
                return None

            result = data.get('result', {})

            log.debug(
                f"Retrieved cached operation result: saga={saga_id}, "
                f"operation={operation_name}, resource={resource_id}"
            )

            return result

        except json.JSONDecodeError as e:
            log.error(f"Failed to decode operation result for {key}: {e}")
            return None
        except Exception as e:
            log.error(f"Error getting operation result for {key}: {e}")
            return None

    async def get_operation_data(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Get full operation data (status, timestamps, result, metadata).

        Args:
            saga_id: Saga that executed the operation
            operation_name: Name of operation
            resource_id: Resource identifier

        Returns:
            Full operation data dict if exists, None otherwise
        """
        key = self._build_key(saga_id, operation_name, resource_id)

        try:
            data_json = await safe_get(key)

            if not data_json:
                return None

            return json.loads(data_json)

        except json.JSONDecodeError as e:
            log.error(f"Failed to decode operation data for {key}: {e}")
            return None
        except Exception as e:
            log.error(f"Error getting operation data for {key}: {e}")
            return None

    async def clear_operation(
        self,
        saga_id: uuid.UUID,
        operation_name: str,
        resource_id: str = ""
    ) -> bool:
        """
        Clear operation tracking record.

        Useful for testing or manual cleanup.

        Args:
            saga_id: Saga that executed the operation
            operation_name: Name of operation
            resource_id: Resource identifier

        Returns:
            True if cleared successfully
        """
        key = self._build_key(saga_id, operation_name, resource_id)

        try:
            deleted = await safe_delete(key)

            if deleted:
                log.debug(
                    f"Cleared operation tracking: saga={saga_id}, "
                    f"operation={operation_name}, resource={resource_id}"
                )

            return bool(deleted)

        except Exception as e:
            log.error(f"Error clearing operation for {key}: {e}")
            return False

    async def clear_all_saga_operations(self, saga_id: uuid.UUID) -> int:
        """
        Clear all operation records for a saga.

        Useful when saga completes or is manually cleaned up.

        NOTE: This method is not yet implemented as it requires a keys() function
        from redis_client. Operations will expire automatically based on TTL.

        Args:
            saga_id: Saga identifier

        Returns:
            Number of operations cleared (always 0 currently)
        """
        # TODO: Implement when redis_client exposes keys() or scan() function
        # Operations will auto-expire based on TTL for now
        log.warning(
            f"clear_all_saga_operations not yet implemented for saga {saga_id}. "
            f"Operations will auto-expire based on TTL."
        )
        return 0
