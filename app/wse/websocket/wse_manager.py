# =============================================================================
# File: app/wse/websocket/wse_manager.py (SIMPLIFIED WITH DIRECT RELIABILITY USAGE)
# Description: WebSocket connection manager using reliability infrastructure directly
# =============================================================================

import asyncio
import logging
from typing import Dict, Set, Optional, List, Any
from datetime import datetime, timezone
from dataclasses import dataclass

from app.wse.websocket.wse_connection import WSEConnection
from app.infra.reliability.rate_limiter import RateLimiter
from app.config.reliability_config import RateLimiterConfig

log = logging.getLogger("wellwon.wse_manager")


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection"""
    connection: WSEConnection
    user_id: str
    ip_address: str
    connected_at: datetime
    last_activity: datetime
    client_version: str
    protocol_version: int


class WSEManager:
    """
    Manages multiple WebSocket connections with reliability infrastructure.

    Industry Standard (2025): 1 connection per user using multiplexing pattern.
    All events routed through topics over single connection for optimal performance.
    """

    def __init__(self, max_connections_per_user: int = 1):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.ip_connections: Dict[str, Set[str]] = {}

        self.max_connections_per_user = max_connections_per_user

        # Create rate limiters for users and IPs
        self.user_rate_limiters: Dict[str, RateLimiter] = {}
        self.ip_rate_limiters: Dict[str, RateLimiter] = {}

        # Metrics
        self.total_connections = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0

        self._lock = asyncio.Lock()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def add_connection(
            self,
            connection: WSEConnection,
            ip_address: str,
            client_version: str,
            protocol_version: int
    ) -> bool:
        """Add a new connection"""
        # First, check if we need to close an old connection (outside lock to avoid deadlock)
        old_connection_to_close = None

        async with self._lock:
            conn_id = connection.conn_id
            user_id = connection.user_id

            # Check user connection limit
            user_conns = self.user_connections.get(user_id, set())
            if len(user_conns) >= self.max_connections_per_user:
                # Find oldest connection to close
                oldest_conn_id = None
                oldest_time = None

                for existing_conn_id in user_conns:
                    if existing_conn_id in self.connections:
                        conn_info = self.connections[existing_conn_id]
                        if oldest_time is None or conn_info.connected_at < oldest_time:
                            oldest_time = conn_info.connected_at
                            oldest_conn_id = existing_conn_id

                if oldest_conn_id and oldest_conn_id in self.connections:
                    old_connection_to_close = self.connections[oldest_conn_id].connection
                    log.info(
                        f"User {user_id} at connection limit ({self.max_connections_per_user}). "
                        f"Will close oldest connection {oldest_conn_id} to make room for {conn_id}"
                    )
                else:
                    log.warning(f"User {user_id} exceeded max connections but no old connection found")
                    return False

        # Close old connection OUTSIDE the lock to prevent deadlock
        if old_connection_to_close:
            try:
                await old_connection_to_close.close(reason="Replaced by new connection")
                log.info(f"Closed old connection {old_connection_to_close.conn_id}")
            except Exception as e:
                log.error(f"Error closing old connection: {e}")

            # Remove from tracking (this has its own lock)
            await self.remove_connection(old_connection_to_close.conn_id)

        # Now add the new connection
        async with self._lock:
            conn_id = connection.conn_id
            user_id = connection.user_id

            # Add connection
            info = ConnectionInfo(
                connection=connection,
                user_id=user_id,
                ip_address=ip_address,
                connected_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                client_version=client_version,
                protocol_version=protocol_version
            )

            self.connections[conn_id] = info

            # Update user connections
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(conn_id)

            # Update IP connections
            if ip_address not in self.ip_connections:
                self.ip_connections[ip_address] = set()
            self.ip_connections[ip_address].add(conn_id)

            self.total_connections += 1

            log.info(
                f"Added connection {conn_id} for user {user_id} from {ip_address}. "
                f"User now has {len(self.user_connections[user_id])} connections."
            )

            return True

    async def remove_connection(self, conn_id: str) -> None:
        """Remove a connection"""
        async with self._lock:
            if conn_id not in self.connections:
                return

            info = self.connections[conn_id]
            user_id = info.user_id
            ip_address = info.ip_address

            # Update metrics
            self.total_messages_sent += info.connection.metrics.messages_sent
            self.total_messages_received += info.connection.metrics.messages_received

            # Remove from tracking
            del self.connections[conn_id]

            if user_id in self.user_connections:
                self.user_connections[user_id].discard(conn_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    # Clean up user rate limiter
                    if user_id in self.user_rate_limiters:
                        del self.user_rate_limiters[user_id]

            if ip_address in self.ip_connections:
                self.ip_connections[ip_address].discard(conn_id)
                if not self.ip_connections[ip_address]:
                    del self.ip_connections[ip_address]
                    # Clean up IP rate limiter
                    if ip_address in self.ip_rate_limiters:
                        del self.ip_rate_limiters[ip_address]

            log.info(f"Removed connection {conn_id} for user {user_id}")

    async def get_user_connections(self, user_id: str) -> List[WSEConnection]:
        """Get all connections for a user"""
        async with self._lock:
            conn_ids = self.user_connections.get(user_id, set())
            connections = []

            for conn_id in conn_ids:
                if conn_id in self.connections:
                    connections.append(self.connections[conn_id].connection)

            return connections

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Broadcast message to all user connections"""
        connections = await self.get_user_connections(user_id)
        sent_count = 0

        for connection in connections:
            try:
                await connection.send_message(message)
                sent_count += 1
            except Exception as e:
                log.error(f"Failed to send to connection {connection.conn_id}: {e}")

        return sent_count

    async def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        async with self._lock:
            active_users = len(self.user_connections)
            active_ips = len(self.ip_connections)
            active_connections = len(self.connections)

            # Calculate average connections per user
            avg_connections_per_user = 0
            if active_users > 0:
                total_user_connections = sum(
                    len(conns) for conns in self.user_connections.values()
                )
                avg_connections_per_user = total_user_connections / active_users

            # Get client version distribution
            version_distribution = {}
            for info in self.connections.values():
                version = info.client_version
                version_distribution[version] = version_distribution.get(version, 0) + 1

            # Get protocol version distribution
            protocol_distribution = {}
            for info in self.connections.values():
                protocol = info.protocol_version
                protocol_distribution[protocol] = protocol_distribution.get(protocol, 0) + 1

            return {
                'active_connections': active_connections,
                'active_users': active_users,
                'active_ips': active_ips,
                'total_connections': self.total_connections,
                'total_messages_sent': self.total_messages_sent,
                'total_messages_received': self.total_messages_received,
                'avg_connections_per_user': round(avg_connections_per_user, 2),
                'max_connections_per_user': self.max_connections_per_user,
                'client_versions': version_distribution,
                'protocol_versions': protocol_distribution
            }

    async def check_rate_limits(self, user_id: str, ip_address: str, is_premium: bool = False) -> bool:
        """Check if the connection is rate-limited"""
        # Get or create user rate limiter
        if user_id not in self.user_rate_limiters:
            # Create rate limiter with appropriate config
            if is_premium:
                config = RateLimiterConfig(
                    algorithm="token_bucket",
                    capacity=5000,  # Premium users get more
                    refill_rate=500.0,
                    distributed=False
                )
            else:
                config = RateLimiterConfig(
                    algorithm="token_bucket",
                    capacity=1000,
                    refill_rate=100.0,
                    distributed=False
                )

            self.user_rate_limiters[user_id] = RateLimiter(
                name=f"wse_user_{user_id}",
                config=config
            )

        # Get or create IP rate limiter
        if ip_address not in self.ip_rate_limiters:
            # Create IP rate limiter with burst protection
            config = RateLimiterConfig(
                algorithm="token_bucket",
                capacity=10000,
                refill_rate=1000.0,
                distributed=False
            )

            self.ip_rate_limiters[ip_address] = RateLimiter(
                name=f"wse_ip_{ip_address}",
                config=config
            )

        # Check both rate limits
        user_allowed = await self.user_rate_limiters[user_id].acquire()
        if not user_allowed:
            return False

        ip_allowed = await self.ip_rate_limiters[ip_address].acquire()
        if not ip_allowed:
            return False

        return True

    async def _cleanup_loop(self):
        """Periodically clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds (increased from 5 minutes)

                async with self._lock:
                    now = datetime.now(timezone.utc)
                    stale_connections = []

                    for conn_id, info in self.connections.items():
                        # Check if the connection is stale (no activity for 2 minutes)
                        if (now - info.last_activity).total_seconds() > 120:
                            stale_connections.append(conn_id)

                    for conn_id in stale_connections:
                        log.warning(f"Removing stale connection {conn_id}")
                        await self.remove_connection(conn_id)

                    # Clean up orphaned rate limiters
                    # Remove rate limiters for users/IPs with no connections
                    user_ids_to_remove = []
                    for user_id in list(self.user_rate_limiters.keys()):
                        if user_id not in self.user_connections:
                            user_ids_to_remove.append(user_id)

                    for user_id in user_ids_to_remove:
                        del self.user_rate_limiters[user_id]

                    ip_addresses_to_remove = []
                    for ip in list(self.ip_rate_limiters.keys()):
                        if ip not in self.ip_connections:
                            ip_addresses_to_remove.append(ip)

                    for ip in ip_addresses_to_remove:
                        del self.ip_rate_limiters[ip]

                    if user_ids_to_remove or ip_addresses_to_remove:
                        log.info(f"Cleaned up {len(user_ids_to_remove)} user rate limiters "
                                 f"and {len(ip_addresses_to_remove)} IP rate limiters")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in connection cleanup: {e}")

    async def shutdown(self):
        """Shutdown the manager"""
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass


# Global instance
_ws_manager: Optional[WSEManager] = None


def get_ws_manager() -> WSEManager:
    """Get the global WebSocket manager instance"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSEManager()
    return _ws_manager


async def reset_ws_manager():
    """Reset the WebSocket manager (useful for testing)"""
    global _ws_manager
    if _ws_manager:
        await _ws_manager.shutdown()
    _ws_manager = None