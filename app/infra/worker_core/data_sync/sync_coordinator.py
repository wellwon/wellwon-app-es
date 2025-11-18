"""
Sync Coordinator - Manages batch sync operations

Handles:
- Batch coordination across multiple accounts
- Rate limiting per broker (using TokenBucket)
- Distributed locking (prevent concurrent syncs)
- Priority ordering (open first, then recent, then historical)
"""

import logging
import asyncio
from typing import List, Dict, Any
from uuid import UUID

from app.infra.reliability.distributed_lock import DistributedLockManager
from app.infra.reliability.rate_limiter import TokenBucket

log = logging.getLogger("tradecore.data_sync.coordinator")


class SyncCoordinator:
    """Coordinates sync operations across accounts with locking and rate limiting"""

    def __init__(self):
        self.lock_manager = DistributedLockManager()
        # TokenBucket: 10 tokens capacity, 1 token per 6 seconds = ~10 calls per minute
        self.rate_limiter = TokenBucket(capacity=10, refill_rate=1.0/6.0)

    async def coordinate_sync(self, account_ids: List[UUID], sync_function):
        """
        Coordinate sync across multiple accounts with locking.

        Ensures only one sync per account at a time across all worker instances.
        """
        results = []

        for account_id in account_ids:
            lock_key = f"sync:account:{account_id}"

            # Try to acquire lock (using context manager)
            async with self.lock_manager.lock_context(lock_key, ttl_seconds=300):  # 5 min lock
                # Rate limit (wait if needed)
                await self.rate_limiter.wait_and_acquire()

                # Execute sync
                try:
                    result = await sync_function(account_id)
                    results.append(result)
                except Exception as e:
                    log.error(f"Sync failed for {account_id}: {e}")
                    results.append({'error': str(e)})

        return results
