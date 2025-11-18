# =============================================================================
# File: app/wse/__init__.py
# Description: WebSocket Event System (WSE) - Bounded Context
# =============================================================================

"""
WSE (WebSocket Event System) - Bounded Context

Architecture:
- Redis Pub/Sub for multi-instance WebSocket coordination
- Domain events → WebSocket clients
- Market data streaming
- Infrastructure monitoring

Modules:
- core: PubSubBus, types, event transformers
- publishers: Domain, market data, monitoring publishers
- websocket: Connection management, handlers
- services: Snapshot generation
"""

from app.wse.core.pubsub_bus import PubSubBus

__all__ = [
    "PubSubBus",
]
