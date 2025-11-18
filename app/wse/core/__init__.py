# =============================================================================
# File: app/wse/core/__init__.py
# Description: WSE Core Module
# =============================================================================

"""
WSE Core - Redis Pub/Sub and Event Processing

Components:
- PubSubBus: Redis Pub/Sub for multi-instance coordination
- EventPriority: Event priority levels
- EventTransformer: Domain events → WebSocket format
- CompressionManager: Message compression
- EventSequencer: Deduplication and ordering
"""

from app.wse.core.pubsub_bus import PubSubBus

__all__ = [
    "PubSubBus",
]
