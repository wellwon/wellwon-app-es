# =============================================================================
# File: app/infra/event_store/projection_checkpoint_service.py
# Description: Projection checkpoint persistence service (separate from EventStore)
# =============================================================================

"""
Projection Checkpoint Service

Handles persistence of projection checkpoints to PostgreSQL.
Separates checkpoint logic from EventStore (like OutboxService pattern).

Architecture:
- EventStore injects this service (not pg_client directly)
- Service encapsulates all PostgreSQL checkpoint operations
- Clean separation of concerns
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timezone

log = logging.getLogger("tradecore.projection_checkpoint_service")


class ProjectionCheckpointService:
    """
    Service for managing projection checkpoints in PostgreSQL.

    Separates checkpoint persistence from EventStore to maintain clean architecture.
    Similar pattern to TransportOutboxService.
    """

    def __init__(self, pg_client=None):
        """
        Initialize checkpoint service.

        Args:
            pg_client: PostgreSQL client module (app.infra.persistence.pg_client)
                      If None, checkpoints stored in-memory only (for workers without projections)
        """
        self._pg_client = pg_client
        self._in_memory_checkpoints: Dict[str, int] = {}

        if not self._pg_client:
            log.info("ProjectionCheckpointService initialized WITHOUT pg_client (in-memory only)")
        else:
            log.info("ProjectionCheckpointService initialized WITH pg_client (persistent)")

    async def save_checkpoint(
        self,
        projection_name: str,
        commit_position: int,
        last_event_type: Optional[str] = None
    ) -> None:
        """
        Save projection checkpoint.

        Args:
            projection_name: Name of the projection
            commit_position: Global commit position from KurrentDB $all stream
            last_event_type: Type of last processed event (optional)
        """
        # In-memory cache (always updated)
        self._in_memory_checkpoints[projection_name] = commit_position

        # Persist to PostgreSQL if available
        if self._pg_client:
            try:
                await self._pg_client.execute(
                    """
                    INSERT INTO projection_checkpoints (projection_name, commit_position, last_event_type)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (projection_name)
                    DO UPDATE SET
                        commit_position = $2,
                        last_event_type = $3,
                        events_processed = projection_checkpoints.events_processed + 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    projection_name, commit_position, last_event_type
                )
                log.debug(f"Saved checkpoint {commit_position} for projection {projection_name}")
            except Exception as e:
                log.error(f"Failed to save checkpoint to PostgreSQL: {e}")
                # Don't fail - in-memory cache is updated
        else:
            log.debug(f"Saved checkpoint {commit_position} for projection {projection_name} (in-memory only)")

    async def load_checkpoint(self, projection_name: str) -> int:
        """
        Load projection checkpoint.

        Args:
            projection_name: Name of the projection

        Returns:
            Last commit_position, or 0 if not found
        """
        # Try PostgreSQL first (source of truth)
        if self._pg_client:
            try:
                result = await self._pg_client.fetchrow(
                    """
                    SELECT commit_position
                    FROM projection_checkpoints
                    WHERE projection_name = $1
                    """,
                    projection_name
                )
                if result:
                    checkpoint = result['commit_position']
                    # Update in-memory cache
                    self._in_memory_checkpoints[projection_name] = checkpoint
                    log.debug(f"Loaded checkpoint {checkpoint} for projection {projection_name} from PostgreSQL")
                    return checkpoint
            except Exception as e:
                log.error(f"Failed to load checkpoint from PostgreSQL: {e}")
                # Fall through to in-memory cache

        # Fall back to in-memory cache
        checkpoint = self._in_memory_checkpoints.get(projection_name, 0)
        if checkpoint > 0:
            log.debug(f"Loaded checkpoint {checkpoint} for projection {projection_name} from cache")
        else:
            log.debug(f"No checkpoint found for projection {projection_name}, starting from 0")
        return checkpoint

    async def delete_checkpoint(self, projection_name: str) -> None:
        """
        Delete projection checkpoint (for projection rebuilds).

        Args:
            projection_name: Name of the projection
        """
        # Remove from in-memory cache
        if projection_name in self._in_memory_checkpoints:
            del self._in_memory_checkpoints[projection_name]

        # Delete from PostgreSQL
        if self._pg_client:
            try:
                await self._pg_client.execute(
                    "DELETE FROM projection_checkpoints WHERE projection_name = $1",
                    projection_name
                )
                log.info(f"Deleted checkpoint for projection {projection_name}")
            except Exception as e:
                log.error(f"Failed to delete checkpoint from PostgreSQL: {e}")

    async def get_all_checkpoints(self) -> Dict[str, int]:
        """
        Get all projection checkpoints.

        Returns:
            Dict mapping projection_name -> commit_position
        """
        if self._pg_client:
            try:
                rows = await self._pg_client.fetch(
                    "SELECT projection_name, commit_position FROM projection_checkpoints"
                )
                return {row['projection_name']: row['commit_position'] for row in rows}
            except Exception as e:
                log.error(f"Failed to load checkpoints from PostgreSQL: {e}")
                # Fall through to in-memory

        return dict(self._in_memory_checkpoints)

    def is_persistent(self) -> bool:
        """Check if checkpoints are persisted to PostgreSQL."""
        return self._pg_client is not None

    def get_in_memory_checkpoints(self) -> Dict[str, int]:
        """Get in-memory checkpoint cache (for debugging)."""
        return dict(self._in_memory_checkpoints)


# =============================================================================
# Factory function
# =============================================================================

def create_projection_checkpoint_service(pg_client=None) -> ProjectionCheckpointService:
    """
    Create projection checkpoint service.

    Args:
        pg_client: PostgreSQL client module (optional)

    Returns:
        ProjectionCheckpointService instance
    """
    return ProjectionCheckpointService(pg_client=pg_client)


# =============================================================================
# Global instance (for convenience, similar to outbox_service pattern)
# =============================================================================

_global_checkpoint_service: Optional[ProjectionCheckpointService] = None


def get_projection_checkpoint_service() -> Optional[ProjectionCheckpointService]:
    """Get global projection checkpoint service instance."""
    return _global_checkpoint_service


def set_projection_checkpoint_service(service: ProjectionCheckpointService) -> None:
    """Set global projection checkpoint service instance."""
    global _global_checkpoint_service
    _global_checkpoint_service = service
