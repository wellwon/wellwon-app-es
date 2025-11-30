# =============================================================================
# File: app/infra/persistence/scylladb/__init__.py
# Description: ScyllaDB/Cassandra client package for WellWon
# =============================================================================

from app.infra.persistence.scylladb.client import (
    ScyllaClient,
    get_scylla_client,
    init_global_scylla_client,
    close_global_scylla_client,
    init_app_scylla,
    close_app_scylla,
    get_app_scylla,
    scylla_client_context,
)
from app.infra.persistence.scylladb.snowflake import (
    SnowflakeIDGenerator,
    SnowflakeIDParser,
    ParsedSnowflake,
    get_snowflake_generator,
    generate_snowflake_id,
    generate_snowflake_id_str,
    calculate_message_bucket,
    get_bucket_range,
    WELLWON_EPOCH,
)
from app.infra.persistence.scylladb.health import (
    HealthStatus,
    NodeHealth,
    ClusterHealth,
    ScyllaHealthChecker,
    check_connection_health,
    check_cluster_health,
    check_keyspace_health,
    check_table_health,
    readiness_probe,
    liveness_probe,
)

__all__ = [
    # Client
    "ScyllaClient",
    "get_scylla_client",
    "init_global_scylla_client",
    "close_global_scylla_client",
    "init_app_scylla",
    "close_app_scylla",
    "get_app_scylla",
    "scylla_client_context",
    # Snowflake ID
    "SnowflakeIDGenerator",
    "SnowflakeIDParser",
    "ParsedSnowflake",
    "get_snowflake_generator",
    "generate_snowflake_id",
    "generate_snowflake_id_str",
    "calculate_message_bucket",
    "get_bucket_range",
    "WELLWON_EPOCH",
    # Health
    "HealthStatus",
    "NodeHealth",
    "ClusterHealth",
    "ScyllaHealthChecker",
    "check_connection_health",
    "check_cluster_health",
    "check_keyspace_health",
    "check_table_health",
    "readiness_probe",
    "liveness_probe",
]
