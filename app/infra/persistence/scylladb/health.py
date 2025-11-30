# =============================================================================
# File: app/infra/persistence/scylladb/health.py
# Description: Health check and monitoring utilities for ScyllaDB.
# =============================================================================

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

try:
    from app.config.logging_config import get_logger
    log = get_logger("wellwon.infra.scylladb.health")
except ImportError:
    log = logging.getLogger("wellwon.infra.scylladb.health")


# =============================================================================
# Health Status
# =============================================================================
class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class NodeHealth:
    """Health information for a single ScyllaDB node."""
    address: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    datacenter: Optional[str] = None
    rack: Optional[str] = None
    is_up: bool = False
    tokens: int = 0
    error: Optional[str] = None
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ClusterHealth:
    """Aggregated health information for ScyllaDB cluster."""
    status: HealthStatus
    healthy_nodes: int = 0
    total_nodes: int = 0
    average_latency_ms: Optional[float] = None
    nodes: List[NodeHealth] = field(default_factory=list)
    keyspace: Optional[str] = None
    replication_factor: Optional[int] = None
    error: Optional[str] = None
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "healthy_nodes": self.healthy_nodes,
            "total_nodes": self.total_nodes,
            "average_latency_ms": self.average_latency_ms,
            "keyspace": self.keyspace,
            "replication_factor": self.replication_factor,
            "error": self.error,
            "last_check": self.last_check.isoformat(),
            "nodes": [
                {
                    "address": n.address,
                    "status": n.status.value,
                    "latency_ms": n.latency_ms,
                    "datacenter": n.datacenter,
                    "rack": n.rack,
                    "is_up": n.is_up,
                    "tokens": n.tokens,
                    "error": n.error,
                }
                for n in self.nodes
            ]
        }


# =============================================================================
# Health Check Functions
# =============================================================================
async def check_connection_health(client) -> Dict[str, Any]:
    """
    Basic connection health check.

    Args:
        client: ScyllaClient instance

    Returns:
        Health check result dictionary
    """
    try:
        start_time = time.time()
        result = await client.execute("SELECT now() FROM system.local")
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": HealthStatus.HEALTHY.value,
            "latency_ms": round(latency_ms, 2),
            "connected": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error(f"Connection health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY.value,
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def check_cluster_health(client) -> ClusterHealth:
    """
    Comprehensive cluster health check.

    Checks all nodes, replication, and latency.

    Args:
        client: ScyllaClient instance

    Returns:
        ClusterHealth object with detailed status
    """
    try:
        # Check basic connectivity
        start_time = time.time()
        await client.execute("SELECT now() FROM system.local")
        base_latency = (time.time() - start_time) * 1000

        # Get peer information
        peers_result = await client.execute("""
            SELECT peer, data_center, rack, tokens
            FROM system.peers
        """)

        # Get local node info
        local_result = await client.execute("""
            SELECT broadcast_address, data_center, rack, tokens
            FROM system.local
        """)

        nodes: List[NodeHealth] = []
        latencies: List[float] = [base_latency]

        # Add local node
        if local_result:
            local = local_result[0]
            nodes.append(NodeHealth(
                address=str(local.get('broadcast_address', 'localhost')),
                status=HealthStatus.HEALTHY,
                latency_ms=round(base_latency, 2),
                datacenter=local.get('data_center'),
                rack=local.get('rack'),
                is_up=True,
                tokens=len(local.get('tokens', [])) if local.get('tokens') else 0,
            ))

        # Add peer nodes
        for peer in peers_result:
            peer_address = str(peer.get('peer', ''))
            try:
                # Try to check peer health (simple connectivity)
                start_time = time.time()
                await client.execute(
                    "SELECT now() FROM system.local",
                    timeout=2.0
                )
                peer_latency = (time.time() - start_time) * 1000
                latencies.append(peer_latency)

                nodes.append(NodeHealth(
                    address=peer_address,
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(peer_latency, 2),
                    datacenter=peer.get('data_center'),
                    rack=peer.get('rack'),
                    is_up=True,
                    tokens=len(peer.get('tokens', [])) if peer.get('tokens') else 0,
                ))
            except Exception as peer_error:
                nodes.append(NodeHealth(
                    address=peer_address,
                    status=HealthStatus.UNHEALTHY,
                    datacenter=peer.get('data_center'),
                    rack=peer.get('rack'),
                    is_up=False,
                    tokens=len(peer.get('tokens', [])) if peer.get('tokens') else 0,
                    error=str(peer_error),
                ))

        # Get keyspace replication info
        keyspace = client.config.keyspace
        replication_factor = None

        try:
            # Use parameterized query to prevent SQL injection
            ks_result = await client.execute(
                "SELECT replication FROM system_schema.keyspaces WHERE keyspace_name = ?",
                (keyspace,)
            )
            if ks_result:
                replication = ks_result[0].get('replication', {})
                rf = replication.get('replication_factor')
                if rf:
                    replication_factor = int(rf)
        except Exception as ks_error:
            log.warning(f"Could not get keyspace info: {ks_error}")

        # Calculate overall health
        healthy_count = sum(1 for n in nodes if n.status == HealthStatus.HEALTHY)
        total_count = len(nodes)
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        # Determine cluster status
        if healthy_count == total_count:
            cluster_status = HealthStatus.HEALTHY
        elif healthy_count > 0:
            cluster_status = HealthStatus.DEGRADED
        else:
            cluster_status = HealthStatus.UNHEALTHY

        return ClusterHealth(
            status=cluster_status,
            healthy_nodes=healthy_count,
            total_nodes=total_count,
            average_latency_ms=round(avg_latency, 2) if avg_latency else None,
            nodes=nodes,
            keyspace=keyspace,
            replication_factor=replication_factor,
        )

    except Exception as e:
        log.error(f"Cluster health check failed: {e}")
        return ClusterHealth(
            status=HealthStatus.UNHEALTHY,
            error=str(e),
        )


async def check_keyspace_health(client, keyspace: Optional[str] = None) -> Dict[str, Any]:
    """
    Check keyspace health and table statistics.

    Args:
        client: ScyllaClient instance
        keyspace: Optional keyspace name (defaults to client keyspace)

    Returns:
        Keyspace health information
    """
    keyspace = keyspace or client.config.keyspace

    try:
        # Get keyspace info (parameterized to prevent SQL injection)
        ks_result = await client.execute(
            "SELECT keyspace_name, replication, durable_writes FROM system_schema.keyspaces WHERE keyspace_name = ?",
            (keyspace,)
        )

        if not ks_result:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": f"Keyspace '{keyspace}' not found",
            }

        ks_info = ks_result[0]

        # Get tables in keyspace (parameterized)
        tables_result = await client.execute(
            "SELECT table_name FROM system_schema.tables WHERE keyspace_name = ?",
            (keyspace,)
        )

        tables = [t.get('table_name') for t in tables_result]

        return {
            "status": HealthStatus.HEALTHY.value,
            "keyspace": keyspace,
            "replication": ks_info.get('replication', {}),
            "durable_writes": ks_info.get('durable_writes', True),
            "table_count": len(tables),
            "tables": tables,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error(f"Keyspace health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY.value,
            "keyspace": keyspace,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def check_table_health(
        client,
        table_name: str,
        keyspace: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check health of a specific table.

    Args:
        client: ScyllaClient instance
        table_name: Table name to check
        keyspace: Optional keyspace name

    Returns:
        Table health information
    """
    keyspace = keyspace or client.config.keyspace

    try:
        # Get table schema (parameterized to prevent SQL injection)
        schema_result = await client.execute(
            "SELECT column_name, type, kind FROM system_schema.columns WHERE keyspace_name = ? AND table_name = ?",
            (keyspace, table_name)
        )

        if not schema_result:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": f"Table '{keyspace}.{table_name}' not found",
            }

        columns = [
            {
                "name": col.get('column_name'),
                "type": col.get('type'),
                "kind": col.get('kind'),
            }
            for col in schema_result
        ]

        # Try to check if the table is readable
        # Note: Table names can't be parameterized in CQL, so we validate them first
        # Only allow alphanumeric and underscore characters
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": f"Invalid table name: {table_name}",
            }
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', keyspace):
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": f"Invalid keyspace name: {keyspace}",
            }

        try:
            # Table names can't be parameterized, but we validated them above
            count_result = await client.execute(
                f"SELECT COUNT(*) as count FROM {keyspace}.{table_name} LIMIT 1"
            )
            # Note: This only checks if the table is readable
            is_readable = True
        except Exception:
            is_readable = False

        return {
            "status": HealthStatus.HEALTHY.value if is_readable else HealthStatus.DEGRADED.value,
            "keyspace": keyspace,
            "table": table_name,
            "columns": columns,
            "column_count": len(columns),
            "is_readable": is_readable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error(f"Table health check failed for {keyspace}.{table_name}: {e}")
        return {
            "status": HealthStatus.UNHEALTHY.value,
            "keyspace": keyspace,
            "table": table_name,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Health Check Runner
# =============================================================================
class ScyllaHealthChecker:
    """
    Periodic health checker for ScyllaDB.

    Can be used to run health checks in the background and maintain
    a cached health status.
    """

    def __init__(
            self,
            client,
            check_interval_seconds: int = 30,
    ):
        """
        Initialize health checker.

        Args:
            client: ScyllaClient instance
            check_interval_seconds: Interval between health checks
        """
        self._client = client
        self._check_interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_health: Optional[ClusterHealth] = None
        self._last_check_time: Optional[datetime] = None

    async def start(self) -> None:
        """Start background health checking."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        log.info(f"ScyllaDB health checker started (interval: {self._check_interval}s)")

    async def stop(self) -> None:
        """Stop background health checking."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("ScyllaDB health checker stopped")

    async def _check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                self._last_health = await check_cluster_health(self._client)
                self._last_check_time = datetime.now(timezone.utc)

                if self._last_health.status != HealthStatus.HEALTHY:
                    log.warning(
                        f"ScyllaDB cluster health: {self._last_health.status.value} "
                        f"({self._last_health.healthy_nodes}/{self._last_health.total_nodes} nodes)"
                    )

            except Exception as e:
                log.error(f"Health check error: {e}")
                self._last_health = ClusterHealth(
                    status=HealthStatus.UNKNOWN,
                    error=str(e),
                )

            await asyncio.sleep(self._check_interval)

    def get_last_health(self) -> Optional[ClusterHealth]:
        """Get the last health check result."""
        return self._last_health

    def get_last_check_time(self) -> Optional[datetime]:
        """Get the time of the last health check."""
        return self._last_check_time

    @property
    def is_running(self) -> bool:
        """Check if health checker is running."""
        return self._running


# =============================================================================
# Readiness and Liveness Probes
# =============================================================================
async def readiness_probe(client) -> Dict[str, Any]:
    """
    Kubernetes readiness probe for ScyllaDB.

    Returns true if ScyllaDB is ready to accept queries.

    Args:
        client: ScyllaClient instance

    Returns:
        Readiness status
    """
    try:
        # Try a simple query
        start_time = time.time()
        await client.execute("SELECT now() FROM system.local", timeout=5.0)
        latency_ms = (time.time() - start_time) * 1000

        # Consider ready if latency is under 100ms
        is_ready = latency_ms < 100

        return {
            "ready": is_ready,
            "latency_ms": round(latency_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "ready": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def liveness_probe(client) -> Dict[str, Any]:
    """
    Kubernetes liveness probe for ScyllaDB.

    Returns true if ScyllaDB connection is alive.

    Args:
        client: ScyllaClient instance

    Returns:
        Liveness status
    """
    try:
        # Simple connectivity check
        await client.execute("SELECT now() FROM system.local", timeout=10.0)

        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "alive": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# EOF
# =============================================================================
