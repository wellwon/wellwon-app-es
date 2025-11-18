# =============================================================================
# File: app/infra/event_bus/topic_manager.py
# Description: Automatic Topic Management для Redpanda/Kafka
#
# Features:
# - Automatic topic creation on startup
# - Retention policy validation
# - Configuration enforcement (based on Redpanda 2025 best practices)
# - Health checks and statistics
#
# Based on:
# - Redpanda documentation: https://docs.redpanda.com/current/
# - Kafka best practices
# - WellWon architecture requirements
# =============================================================================

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Use aiokafka for admin operations (async-compatible)
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError, KafkaError

log = logging.getLogger("wellwon.topic_manager")


class RetentionPolicy(Enum):
    """
    Topic retention policies based on WellWon architecture.

    - EVENT_STORE: 10 years (永久хранение событий для audit trail)
    - TRANSPORT: 7 days (временный транспорт между сервисами)
    - SNAPSHOT: 1 year + compaction (snapshots агрегатов)
    - TEMP: 1 day (временные топики для координации)
    """
    EVENT_STORE = "event_store"      # 10 years
    TRANSPORT = "transport"          # 7 days
    SNAPSHOT = "snapshot"            # 1 year + compaction
    TEMP = "temporary"               # 1 day


@dataclass
class TopicSpec:
    """
    Topic specification with Redpanda best practices.

    Based on:
    - https://docs.redpanda.com/current/reference/properties/topic-properties/
    - https://www.redpanda.com/guides/kafka-performance-kafka-optimization
    """
    name: str
    partitions: int
    replication_factor: int
    retention_policy: RetentionPolicy
    cleanup_policy: str = "delete"  # delete, compact, compact,delete
    compression_type: str = "producer"  # Use producer compression (client-side)
    min_insync_replicas: int = 2  # Safety: require 2 replicas for ack
    segment_ms: Optional[int] = None
    segment_bytes: Optional[int] = None

    def get_retention_ms(self) -> int:
        """Get retention in milliseconds based on policy"""
        return {
            RetentionPolicy.EVENT_STORE: 10 * 365 * 24 * 60 * 60 * 1000,  # 10 years
            RetentionPolicy.TRANSPORT: 7 * 24 * 60 * 60 * 1000,           # 7 days
            RetentionPolicy.SNAPSHOT: 365 * 24 * 60 * 60 * 1000,          # 1 year
            RetentionPolicy.TEMP: 24 * 60 * 60 * 1000,                    # 1 day
        }[self.retention_policy]

    def to_kafka_config(self) -> Dict[str, str]:
        """
        Convert to Kafka/Redpanda topic config.

        Config properties based on Redpanda documentation:
        https://docs.redpanda.com/current/reference/properties/topic-properties/
        """
        config = {
            'retention.ms': str(self.get_retention_ms()),
            'cleanup.policy': self.cleanup_policy,
            'compression.type': self.compression_type,  # Redpanda recommends 'producer'
            'min.insync.replicas': str(self.min_insync_replicas),
        }

        # Segment settings (for rollover control)
        if self.segment_ms:
            config['segment.ms'] = str(self.segment_ms)
        if self.segment_bytes:
            config['segment.bytes'] = str(self.segment_bytes)

        # Compaction-specific settings
        if 'compact' in self.cleanup_policy:
            config.update({
                # Trigger compaction at 50% dirty ratio
                'min.cleanable.dirty.ratio': '0.5',
                # Max lag before compaction (24h)
                'max.compaction.lag.ms': str(24 * 60 * 60 * 1000),
                # Keep tombstones for 24h (allow consumers to see deletes)
                'delete.retention.ms': str(86400000),
            })

        return config


class TopicManager:
    """
    Manages Redpanda/Kafka topics with best practices.

    Usage:
        topic_manager = TopicManager("localhost:9092")
        await topic_manager.ensure_topics_exist()
        await topic_manager.validate_retention_policies()

    Features:
    - Automatic topic creation based on WellWon architecture
    - Retention validation
    - Configuration enforcement
    - Health checks
    """

    # =========================================================================
    # Default topic specifications for WellWon
    # =========================================================================
    DEFAULT_TOPICS = [
        # =====================================================================
        # EVENT STORE TOPICS (10-year retention)
        # =====================================================================
        TopicSpec(
            name="eventstore.all-events",
            partitions=12,  # High partitioning for parallel processing
            replication_factor=3,  # Safety: 3 replicas
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",  # Never compact event store!
            compression_type="producer",  # Client-side compression
            segment_ms=7 * 24 * 60 * 60 * 1000,  # 7-day segments
        ),
        TopicSpec(
            name="eventstore.user-account-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
            segment_ms=7 * 24 * 60 * 60 * 1000,
        ),
        TopicSpec(
            name="eventstore.entity-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.account-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.automation-events",
            partitions=12,  # High volume expected
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.order-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.position-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.virtual-broker-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),
        TopicSpec(
            name="eventstore.saga-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.EVENT_STORE,
            cleanup_policy="delete",
        ),

        # =====================================================================
        # SNAPSHOT TOPICS (1-year retention + compaction)
        # =====================================================================
        TopicSpec(
            name="eventstore.snapshots-user-account",
            partitions=3,
            replication_factor=3,
            retention_policy=RetentionPolicy.SNAPSHOT,
            cleanup_policy="compact,delete",  # Keep latest + time-based deletion
            compression_type="producer",  # Client-side compression (zstd recommended)
            segment_ms=7 * 24 * 60 * 60 * 1000,  # 7-day segments
        ),
        TopicSpec(
            name="eventstore.snapshots-broker-account",
            partitions=3,
            replication_factor=3,
            retention_policy=RetentionPolicy.SNAPSHOT,
            cleanup_policy="compact,delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="eventstore.snapshots-automation",
            partitions=6,  # Higher for automation volume
            replication_factor=3,
            retention_policy=RetentionPolicy.SNAPSHOT,
            cleanup_policy="compact,delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="eventstore.snapshots-virtual-broker",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.SNAPSHOT,
            cleanup_policy="compact,delete",
            compression_type="producer",
        ),

        # =====================================================================
        # TRANSPORT TOPICS (7-day retention)
        # =====================================================================
        TopicSpec(
            name="transport.user-account-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",  # Use producer compression (lz4)
        ),
        TopicSpec(
            name="transport.entity-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="transport.account-events",
            partitions=6,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="transport.automation-events",
            partitions=12,  # High volume
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="transport.order-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="transport.position-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
        TopicSpec(
            name="transport.virtual-broker-events",
            partitions=12,
            replication_factor=3,
            retention_policy=RetentionPolicy.TRANSPORT,
            cleanup_policy="delete",
            compression_type="producer",
        ),
    ]

    def __init__(
        self,
        bootstrap_servers: str,
        custom_topics: Optional[List[TopicSpec]] = None,
        enable_auto_create: bool = True
    ):
        """
        Initialize Topic Manager.

        Args:
            bootstrap_servers: Kafka/Redpanda bootstrap servers
            custom_topics: Additional custom topics to manage
            enable_auto_create: Auto-create topics on ensure_topics_exist()
        """
        self.bootstrap_servers = bootstrap_servers
        self.enable_auto_create = enable_auto_create

        # Create async admin client (will be started when needed)
        self.admin_client = AIOKafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id="wellwon-topic-manager",
            request_timeout_ms=30000
        )
        self._admin_started = False

        # Merge default and custom topics
        self.topics = self.DEFAULT_TOPICS.copy()
        if custom_topics:
            self.topics.extend(custom_topics)

        log.info(
            f"TopicManager initialized with {len(self.topics)} topics "
            f"(auto_create={enable_auto_create})"
        )

    async def ensure_topics_exist(self) -> Dict[str, str]:
        """
        Create topics if they don't exist (async).

        Returns:
            Dict with results: {topic_name: status}

        Statuses:
        - "created": Topic was created successfully
        - "exists": Topic already exists
        - "skipped": Auto-create disabled
        - "error: <msg>": Creation failed
        """
        if not self.enable_auto_create:
            log.info("Topic auto-creation disabled")
            return {spec.name: "skipped" for spec in self.topics}

        # Start admin client if not started
        if not self._admin_started:
            try:
                await self.admin_client.start()
                self._admin_started = True
                log.debug("Admin client started")
            except Exception as e:
                log.error(f"Failed to start admin client: {e}")
                return {spec.name: f"error: {e}" for spec in self.topics}

        results = {}

        try:
            # Get existing topics
            metadata = await self.admin_client.list_topics()
            existing_topics = set(metadata)

            # Create missing topics
            topics_to_create = []
            for spec in self.topics:
                if spec.name not in existing_topics:
                    new_topic = NewTopic(
                        name=spec.name,
                        num_partitions=spec.partitions,
                        replication_factor=spec.replication_factor,
                        topic_configs=spec.to_kafka_config()
                    )
                    topics_to_create.append(new_topic)
                    results[spec.name] = "creating"
                else:
                    results[spec.name] = "exists"

            if topics_to_create:
                log.info(f"Creating {len(topics_to_create)} topics...")

                try:
                    # Create topics (aiokafka doesn't return futures, just creates)
                    await self.admin_client.create_topics(
                        new_topics=topics_to_create,
                        timeout_ms=30000
                    )

                    # Mark all as created (aiokafka doesn't give per-topic status)
                    for topic in topics_to_create:
                        results[topic.name] = "created"
                        log.info(f"Created topic: {topic.name}")

                    log.info(f"Topic creation complete: {len(topics_to_create)} topics processed")

                except TopicAlreadyExistsError:
                    # Some topics already exist
                    for topic in topics_to_create:
                        results[topic.name] = "already_exists"
                    log.debug("Some topics already exist")

                except Exception as e:
                    # Creation failed
                    for topic in topics_to_create:
                        results[topic.name] = f"error: {e}"
                    log.error(f"Failed to create topics: {e}")
            else:
                log.info("All topics already exist")

        except Exception as e:
            log.error(f"Failed to create topics: {e}")
            for spec in self.topics:
                if spec.name not in results:
                    results[spec.name] = f"error: {e}"

        return results

    def validate_retention_policies(self) -> Dict[str, Dict[str, any]]:
        """
        Validate topic retention matches expected values.

        HIGH FIX #7 (2025-11-14): Added validation warnings for retention mismatches.
        Note: Full async validation requires AdminClient, which is async.
        This sync method provides basic validation warnings.

        Returns:
            Dict with validation results per topic
        """
        results = {}

        for spec in self.topics:
            expected_retention_ms = spec.get_retention_ms()

            # HIGH FIX #7: Warn about critical retention policies
            if spec.retention_policy == RetentionPolicy.EVENT_STORE:
                # 10-year retention - critical for audit trail
                log.info(
                    f"Topic '{spec.name}' configured for EVENT_STORE retention: "
                    f"{expected_retention_ms}ms (10 years). "
                    f"CRITICAL: Verify actual retention with: rpk topic describe {spec.name}"
                )
            elif spec.retention_policy == RetentionPolicy.TRANSPORT and spec.cleanup_policy != "delete":
                # Transport topics should use delete policy
                log.warning(
                    f"POTENTIAL ISSUE: Transport topic '{spec.name}' has cleanup_policy='{spec.cleanup_policy}'. "
                    f"Expected 'delete' for transport topics. Data may accumulate!"
                )

            results[spec.name] = {
                'valid': True,  # Assume valid (actual validation requires async AdminClient)
                'expected_retention_ms': expected_retention_ms,
                'actual_retention_ms': 'use_rpk_to_verify',
                'retention_policy': spec.retention_policy.value,
                'cleanup_policy': spec.cleanup_policy,
                'validation_command': f"rpk topic describe {spec.name}",
                'note': 'Use AdminClient.describe_configs() for async validation'
            }

        return results

    async def get_topic_stats(self) -> Dict[str, Dict[str, any]]:
        """
        Get statistics for all managed topics (async).

        Returns:
            Dict with stats per topic
        """
        stats = {}

        try:
            # Start admin client if not started
            if not self._admin_started:
                await self.admin_client.start()
                self._admin_started = True

            # Get list of existing topics
            metadata = await self.admin_client.list_topics()
            existing_topics = set(metadata)

            for spec in self.topics:
                try:
                    if spec.name in existing_topics:
                        stats[spec.name] = {
                            'exists': True,
                            'expected_partitions': spec.partitions,
                            'expected_replication': spec.replication_factor,
                            'retention_policy': spec.retention_policy.value,
                            'cleanup_policy': spec.cleanup_policy,
                        }
                    else:
                        stats[spec.name] = {
                            'exists': False,
                            'expected_partitions': spec.partitions,
                            'expected_replication': spec.replication_factor,
                        }

                except Exception as e:
                    stats[spec.name] = {'error': str(e)}

        except Exception as e:
            log.error(f"Failed to get topic stats: {e}")
            return {'error': str(e)}

        return stats

    async def get_health_status(self) -> Dict[str, any]:
        """
        Get overall health status of topic management (async).

        Returns:
            Health status dict with summary
        """
        try:
            stats = await self.get_topic_stats()

            total_topics = len(self.topics)
            existing_topics = sum(
                1 for s in stats.values()
                if isinstance(s, dict) and s.get('exists', False)
            )
            error_topics = sum(
                1 for s in stats.values()
                if isinstance(s, dict) and 'error' in s
            )

            health = {
                'status': 'healthy' if existing_topics == total_topics else 'degraded',
                'total_topics': total_topics,
                'existing_topics': existing_topics,
                'missing_topics': total_topics - existing_topics,
                'error_topics': error_topics,
                'admin_client_connected': self._admin_started,
            }

            return health

        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'admin_client_connected': False,
            }

    async def close(self):
        """Close admin client connection (async)"""
        try:
            if self._admin_started:
                await self.admin_client.close()
                self._admin_started = False
            log.info("TopicManager closed")
        except Exception as e:
            log.error(f"Error closing TopicManager: {e}")


# =============================================================================
# Convenience functions
# =============================================================================

def create_topic_manager(
    bootstrap_servers: str,
    custom_topics: Optional[List[TopicSpec]] = None,
    enable_auto_create: bool = True
) -> TopicManager:
    """
    Factory function to create TopicManager.

    Usage:
        topic_manager = create_topic_manager("localhost:9092")
        topic_manager.ensure_topics_exist()
    """
    return TopicManager(
        bootstrap_servers=bootstrap_servers,
        custom_topics=custom_topics,
        enable_auto_create=enable_auto_create
    )
