# =============================================================================
# File: app/services/application/customs_status_sync_service.py
# Description: Background service to poll Kontur for declaration status updates
# =============================================================================

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Optional, List

from app.config.logging_config import get_logger
from app.customs.enums import DocflowStatus
from app.customs.declaration.commands import SyncStatusFromKonturCommand

if TYPE_CHECKING:
    from app.infra.cqrs.command_bus import CommandBus
    from app.infra.cqrs.query_bus import QueryBus
    from app.infra.kontur.adapter import KonturAdapter

log = get_logger("wellwon.services.customs_status_sync")


class CustomsStatusSyncService:
    """
    Background service to poll Kontur for declaration status updates.

    Features:
    - Runs every 5 minutes for SENT/REGISTERED declarations
    - Uses changed_from timestamp for efficient polling
    - Sends commands to update status when changes detected
    - Supports manual refresh for individual declarations
    """

    DEFAULT_POLLING_INTERVAL = 300  # 5 minutes
    MIN_POLLING_INTERVAL = 60  # 1 minute minimum
    MAX_POLLING_INTERVAL = 600  # 10 minutes maximum

    def __init__(
        self,
        command_bus: 'CommandBus',
        kontur_adapter: 'KonturAdapter',
        polling_interval: int = DEFAULT_POLLING_INTERVAL,
    ):
        self.command_bus = command_bus
        self.kontur = kontur_adapter
        self.polling_interval = max(
            self.MIN_POLLING_INTERVAL,
            min(polling_interval, self.MAX_POLLING_INTERVAL)
        )
        self._running = False
        self._last_sync_time: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background sync loop."""
        if self._running:
            log.warning("Status sync service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_periodic())
        log.info(
            f"Customs status sync service started "
            f"(polling every {self.polling_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the background sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Customs status sync service stopped")

    async def _run_periodic(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                count = await self.sync_pending_declarations()
                if count > 0:
                    log.info(f"Synced {count} declarations from Kontur")
            except Exception as e:
                log.error(f"Status sync failed: {e}")

            await asyncio.sleep(self.polling_interval)

    async def sync_pending_declarations(self) -> int:
        """
        Sync all pending declarations from Kontur.

        Returns:
            Number of declarations updated
        """
        # Calculate changed_from timestamp (last sync + buffer)
        if self._last_sync_time:
            # Use last sync time minus 1 minute buffer for safety
            changed_from = int(
                (self._last_sync_time - timedelta(minutes=1)).timestamp() * 1000
            )
        else:
            # First sync - get changes from last hour
            changed_from = int(
                (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000
            )

        try:
            # Fetch docflows with status changes
            docflows = await self.kontur.list_docflows(
                take=500,
                changed_from=changed_from,
                # Only poll for active statuses (SENT, REGISTERED)
                # We don't need to poll DRAFT (not submitted) or terminal states
            )

            self._last_sync_time = datetime.now(timezone.utc)
            updated_count = 0

            for docflow in docflows:
                try:
                    # Skip DRAFT status - not submitted yet
                    if docflow.status == DocflowStatus.DRAFT.value:
                        continue

                    # Send sync command
                    await self.command_bus.send(
                        SyncStatusFromKonturCommand(
                            kontur_docflow_id=docflow.id,
                            new_status=DocflowStatus(docflow.status),
                            gtd_number=docflow.gtd_number,
                        )
                    )
                    updated_count += 1

                except Exception as e:
                    log.warning(
                        f"Failed to sync docflow {docflow.id}: {e}"
                    )
                    continue

            return updated_count

        except Exception as e:
            log.error(f"Failed to fetch docflows from Kontur: {e}")
            raise

    async def refresh_declaration(
        self,
        kontur_docflow_id: str,
    ) -> bool:
        """
        Manual refresh for a single declaration.

        Args:
            kontur_docflow_id: Kontur docflow ID

        Returns:
            True if status was updated, False otherwise
        """
        try:
            # Fetch single docflow by searching
            from app.infra.kontur.models import SearchDocflowRequest

            docflows = await self.kontur.search_docflows(
                SearchDocflowRequest(docflow_ids=[kontur_docflow_id]),
                take=1
            )

            if not docflows:
                log.warning(
                    f"Docflow {kontur_docflow_id} not found in Kontur"
                )
                return False

            docflow = docflows[0]

            # Send sync command
            await self.command_bus.send(
                SyncStatusFromKonturCommand(
                    kontur_docflow_id=docflow.id,
                    new_status=DocflowStatus(docflow.status),
                    gtd_number=docflow.gtd_number,
                )
            )

            log.info(
                f"Manually refreshed declaration {kontur_docflow_id} "
                f"(status: {docflow.status})"
            )
            return True

        except Exception as e:
            log.error(
                f"Failed to refresh declaration {kontur_docflow_id}: {e}"
            )
            raise

    @property
    def is_running(self) -> bool:
        """Check if the service is running."""
        return self._running

    @property
    def last_sync_time(self) -> Optional[datetime]:
        """Get the last sync time."""
        return self._last_sync_time


# =============================================================================
# Factory Function
# =============================================================================

_status_sync_service: Optional[CustomsStatusSyncService] = None


async def get_status_sync_service(
    command_bus: 'CommandBus',
    kontur_adapter: 'KonturAdapter',
) -> CustomsStatusSyncService:
    """
    Get or create the status sync service singleton.

    Args:
        command_bus: Command bus for sending commands
        kontur_adapter: Kontur adapter for API calls

    Returns:
        CustomsStatusSyncService instance
    """
    global _status_sync_service

    if _status_sync_service is None:
        _status_sync_service = CustomsStatusSyncService(
            command_bus=command_bus,
            kontur_adapter=kontur_adapter,
        )

    return _status_sync_service


# =============================================================================
# EOF
# =============================================================================
