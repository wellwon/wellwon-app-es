# =============================================================================
# File: app/wse/publishers/wse_market_data_publisher.py
# Description: Market Data Publisher for WebSocket Events (WSE)
# =============================================================================

"""
WSE Market Data Publisher

Publishes real-time market data from broker streams to WSE for frontend consumption.

Architecture:
- Infrastructure layer component (not domain)
- Receives market data from StreamingLifecycleManager
- Publishes to PubSubBus for WSE distribution (broadcasts to all server instances)
- Includes throttling to prevent overwhelming clients

Market Data Event Types:
1. quote_update - Real-time quote updates (bid/ask/last)
2. bar_update - Real-time bar/candle updates
3. trade_update - Individual trade updates
4. orderbook_update - Order book / market depth updates

Topic Structure:
- user:{user_id}:market_data - Per-user market data stream
- user:{user_id}:market_data:{symbol} - Per-symbol streams (optional)

Throttling:
- Max 10 quote updates per second per symbol (100ms throttle)
- No throttling for significant price changes (>0.1%)
- No throttling for trades or bars
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal

from app.wse.core.types import EventPriority

if TYPE_CHECKING:
    from app.wse.core.pubsub_bus import PubSubBus

log = logging.getLogger("tradecore.wse.market_data_publisher")


class WSEMarketDataPublisher:
    """
    Publisher for real-time market data to WSE.

    This publisher handles:
    - Quote updates (bid/ask/last)
    - Bar/candle updates
    - Trade updates
    - Order book updates

    Features:
    - Throttling to prevent overwhelming clients
    - Priority-based event delivery
    - Per-user and per-symbol streams
    """

    # Throttling configuration
    QUOTE_THROTTLE_MS = 100  # Max 10 quotes/sec per symbol
    SIGNIFICANT_CHANGE_THRESHOLD = Decimal("0.001")  # 0.1% price change

    def __init__(self, pubsub_bus: 'PubSubBus'):
        """
        Initialize WSE Market Data Publisher.

        Args:
            pubsub_bus: PubSubBus instance for WSE publishing (Redis Pub/Sub)
        """
        self._pubsub_bus = pubsub_bus
        self._last_quote_times: Dict[str, datetime] = {}  # symbol -> last_publish_time
        self._last_prices: Dict[str, Decimal] = {}  # symbol -> last_price

        log.info("WSEMarketDataPublisher initialized")

    # ========================================================================
    # QUOTE UPDATES
    # ========================================================================

    async def publish_quote_update(
        self,
        user_id: UUID,
        broker_id: str,
        symbol: str,
        quote_data: Dict[str, Any],
        broker_connection_id: Optional[UUID] = None
    ) -> None:
        """
        Publish real-time quote update to WSE.

        Args:
            user_id: User ID
            broker_id: Broker ID (e.g., "alpaca", "tradestation")
            symbol: Symbol (e.g., "AAPL")
            quote_data: Quote data dictionary with bid, ask, last, etc.
            broker_connection_id: Optional broker connection ID
        """
        # Throttling check
        throttle_key = f"{user_id}:{symbol}"
        now = datetime.now(timezone.utc)

        # Check for significant price change
        current_price = quote_data.get("last") or quote_data.get("price")
        if current_price:
            current_price = Decimal(str(current_price))
            last_price = self._last_prices.get(throttle_key)

            is_significant_change = False
            if last_price and last_price > 0:
                price_change_pct = abs((current_price - last_price) / last_price)
                is_significant_change = price_change_pct > self.SIGNIFICANT_CHANGE_THRESHOLD

            # Throttle unless significant change
            if not is_significant_change and throttle_key in self._last_quote_times:
                last_time = self._last_quote_times[throttle_key]
                elapsed_ms = (now - last_time).total_seconds() * 1000
                if elapsed_ms < self.QUOTE_THROTTLE_MS:
                    log.debug(f"Throttling quote for {symbol}: {elapsed_ms:.0f}ms < {self.QUOTE_THROTTLE_MS}ms")
                    return

            # Update tracking
            self._last_quote_times[throttle_key] = now
            self._last_prices[throttle_key] = current_price

        # Build event
        event = {
            "event_type": "quote_update",
            "broker_id": broker_id,
            "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
            "symbol": symbol,
            "data": {
                "bid": float(quote_data.get("bid", 0)),
                "ask": float(quote_data.get("ask", 0)),
                "last": float(quote_data.get("last") or quote_data.get("price", 0)),
                "bid_size": quote_data.get("bid_size", 0),
                "ask_size": quote_data.get("ask_size", 0),
                "volume": quote_data.get("volume", 0),
                "high": float(quote_data.get("high", 0)),
                "low": float(quote_data.get("low", 0)),
                "open": float(quote_data.get("open", 0)),
                "close": float(quote_data.get("close", 0)),
                "timestamp": quote_data.get("timestamp", datetime.now(timezone.utc)).isoformat()
            },
            "timestamp": now.isoformat()
        }

        # Publish to user's market data topic
        topic = f"user:{user_id}:market_data"
        await self._pubsub_bus.publish(topic, event, priority=EventPriority.NORMAL)

        log.debug(f"Published quote update: user={user_id}, symbol={symbol}, price={current_price}")

    # ========================================================================
    # BAR UPDATES
    # ========================================================================

    async def publish_bar_update(
        self,
        user_id: UUID,
        broker_id: str,
        symbol: str,
        bar_data: Dict[str, Any],
        broker_connection_id: Optional[UUID] = None
    ) -> None:
        """
        Publish real-time bar/candle update to WSE.

        Args:
            user_id: User ID
            broker_id: Broker ID
            symbol: Symbol
            bar_data: Bar data dictionary with OHLCV
            broker_connection_id: Optional broker connection ID
        """
        now = datetime.now(timezone.utc)

        event = {
            "event_type": "bar_update",
            "broker_id": broker_id,
            "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
            "symbol": symbol,
            "data": {
                "open": float(bar_data.get("open", 0)),
                "high": float(bar_data.get("high", 0)),
                "low": float(bar_data.get("low", 0)),
                "close": float(bar_data.get("close", 0)),
                "volume": bar_data.get("volume", 0),
                "vwap": float(bar_data.get("vwap", 0)) if bar_data.get("vwap") else None,
                "trade_count": bar_data.get("trade_count"),
                "timestamp": bar_data.get("timestamp", datetime.now(timezone.utc)).isoformat()
            },
            "timestamp": now.isoformat()
        }

        topic = f"user:{user_id}:market_data"
        await self._pubsub_bus.publish(topic, event, priority=EventPriority.NORMAL)

        log.debug(f"Published bar update: user={user_id}, symbol={symbol}")

    # ========================================================================
    # TRADE UPDATES
    # ========================================================================

    async def publish_trade_update(
        self,
        user_id: UUID,
        broker_id: str,
        symbol: str,
        trade_data: Dict[str, Any],
        broker_connection_id: Optional[UUID] = None
    ) -> None:
        """
        Publish individual trade update to WSE.

        Args:
            user_id: User ID
            broker_id: Broker ID
            symbol: Symbol
            trade_data: Trade data dictionary
            broker_connection_id: Optional broker connection ID
        """
        now = datetime.now(timezone.utc)

        event = {
            "event_type": "trade_update",
            "broker_id": broker_id,
            "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
            "symbol": symbol,
            "data": {
                "price": float(trade_data.get("price", 0)),
                "size": trade_data.get("size", 0),
                "exchange": trade_data.get("exchange"),
                "conditions": trade_data.get("conditions", []),
                "timestamp": trade_data.get("timestamp", datetime.now(timezone.utc)).isoformat()
            },
            "timestamp": now.isoformat()
        }

        topic = f"user:{user_id}:market_data"
        await self._pubsub_bus.publish(topic, event, priority=EventPriority.NORMAL)

        log.debug(f"Published trade update: user={user_id}, symbol={symbol}, price={trade_data.get('price')}")

    # ========================================================================
    # ORDER BOOK UPDATES
    # ========================================================================

    async def publish_orderbook_update(
        self,
        user_id: UUID,
        broker_id: str,
        symbol: str,
        orderbook_data: Dict[str, Any],
        broker_connection_id: Optional[UUID] = None
    ) -> None:
        """
        Publish order book / market depth update to WSE.

        Args:
            user_id: User ID
            broker_id: Broker ID
            symbol: Symbol
            orderbook_data: Order book data dictionary
            broker_connection_id: Optional broker connection ID
        """
        now = datetime.now(timezone.utc)

        event = {
            "event_type": "orderbook_update",
            "broker_id": broker_id,
            "broker_connection_id": str(broker_connection_id) if broker_connection_id else None,
            "symbol": symbol,
            "data": {
                "bids": orderbook_data.get("bids", []),
                "asks": orderbook_data.get("asks", []),
                "timestamp": orderbook_data.get("timestamp", datetime.now(timezone.utc)).isoformat()
            },
            "timestamp": now.isoformat()
        }

        topic = f"user:{user_id}:market_data"
        await self._pubsub_bus.publish(topic, event, priority=EventPriority.NORMAL)

        log.debug(f"Published orderbook update: user={user_id}, symbol={symbol}")

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def clear_throttle_cache(self) -> None:
        """Clear throttle cache (for testing or manual reset)."""
        self._last_quote_times.clear()
        self._last_prices.clear()
        log.info("Throttle cache cleared")

    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for market data publisher.

        Returns:
            Health status dictionary
        """
        return {
            "publisher": "wse_market_data",
            "status": "healthy" if self._pubsub_bus else "degraded",
            "reactive_bus_connected": self._pubsub_bus is not None,
            "throttle_cache_size": len(self._last_quote_times),
            "price_cache_size": len(self._last_prices)
        }
