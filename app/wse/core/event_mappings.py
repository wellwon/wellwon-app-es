# =============================================================================
# File: app/wse/core/event_mappings.py
# Description: Event Type Mappings (Internal Events → WebSocket Events)
# =============================================================================

"""
Event Type Mappings for WSE

Maps internal domain event types to WebSocket-friendly event types.

Usage:
    ```python
    from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

    internal_event = "BrokerConnectionEstablished"
    ws_event_type = INTERNAL_TO_WS_EVENT_TYPE_MAP.get(internal_event)
    # Result: "broker_connection_update"
    ```

Domains covered:
- Broker Connection events
- Account events
- Order events
- Position events
- Portfolio events
- Strategy events
- System events
"""

# ─────────────────────────────────────────────────────────────────────────────
# Internal Event Type → WebSocket Event Type Mapping
# ─────────────────────────────────────────────────────────────────────────────

INTERNAL_TO_WS_EVENT_TYPE_MAP = {
    # =========================================================================
    # DOMAIN EVENTS → broker_connection_events topic
    # =========================================================================
    # Broker connection lifecycle (OAuth, credentials, saga completion)
    'BrokerConnectionInitiated': 'broker_connection_update',
    'BrokerConnectionEstablished': 'broker_connection_update',
    'BrokerConnectionEstablishedSagaCompleted': 'broker_connection_update',
    'BrokerConnectionRestored': 'broker_connection_update',
    'BrokerConnectionAttemptFailed': 'broker_connection_update',
    'BrokerDisconnected': 'broker_connection_update',
    'BrokerTokensSuccessfullyStored': 'broker_connection_update',
    'BrokerTokensSuccessfullyRefreshed': 'broker_connection_update',
    'BrokerOAuthClientCredentialsStored': 'broker_connection_update',
    'BrokerApiEndpointConfigured': 'broker_connection_update',
    'BrokerApiCredentialsStored': 'broker_connection_update',
    'BrokerConnectionPurged': 'broker_status_remove',

    # =========================================================================
    # MONITORING EVENTS → broker_health topic (NEW! Nov 13, 2025)
    # =========================================================================
    # REST API health checks and module health
    'BrokerConnectionHealthUpdated': 'broker_health_update',
    'BrokerConnectionHealthChecked': 'broker_health_update',
    'BrokerConnectionModuleHealthChanged': 'broker_health_update',

    # =========================================================================
    # MONITORING EVENTS → broker_streaming topic (Nov 13, 2025)
    # =========================================================================
    # WebSocket/HTTP Chunked streaming lifecycle
    # Note: These are infrastructure events, not domain events
    # Mapped in WSEMonitoringPublisher.publish_streaming_*() methods
    'streaming_connection_status': 'broker_streaming_update',
    'streaming_subscription_started': 'broker_streaming_update',
    'streaming_subscription_stopped': 'broker_streaming_update',
    'streaming_error': 'broker_streaming_update',

    # =========================================================================
    # REAL-TIME DATA → market_data topic (Nov 13, 2025)
    # =========================================================================
    # Market data streams (quotes, trades, bars, orderbook)
    # Note: Direct pass-through from WSEMarketDataPublisher
    'quote_update': 'quote_update',
    'trade_update': 'trade_update',
    'bar_update': 'bar_update',
    'orderbook_update': 'orderbook_update',

    # Account events
    'broker_account_snapshot': 'broker_account_snapshot',  # Snapshot (identity mapping - no transformation needed)
    'AccountDataFromBrokerUpdated': 'broker_account_update',
    'BrokerAccountLinked': 'broker_account_update',
    'UserSetAccountDetailsChanged': 'broker_account_update',
    'UserAccountMarkedDeleted': 'broker_account_remove',  # User-initiated deletion
    'BrokerAccountDeleted': 'broker_account_remove',  # Single account deletion (hard delete)
    'BrokerAccountsDeleted': 'broker_accounts_bulk_remove',  # Broker disconnection cascade
    'BrokerAccountBatchDeleted': 'broker_accounts_bulk_remove',  # Batch deletion
    'BrokerAccountRecovered': 'broker_account_update',  # Account recovery after reconnection
    'AccountDeleted': 'broker_account_remove',  # Generic account deletion

    # Trading events
    'PositionUpdated': 'position_update',
    'OrderExecuted': 'order_update',
    'OrderStatusChanged': 'order_update',
    'OrderRejected': 'order_update',
    'OrderCancelled': 'order_update',
    'OrderPartiallyFilled': 'order_update',

    # Order Domain Events (CQRS/ES)
    'OrderPlacedEvent': 'order_update',
    'OrderSubmittedEvent': 'order_update',
    'OrderAcceptedEvent': 'order_update',
    'OrderFilledEvent': 'order_update',
    'OrderCompletedEvent': 'order_update',
    'OrderCancelledEvent': 'order_update',
    'OrderRejectedEvent': 'order_update',
    'OrderExpiredEvent': 'order_update',
    'OrderModifiedEvent': 'order_update',
    'BracketOrderPlacedEvent': 'order_update',
    'OrderMetadataUpdatedEvent': 'order_update',

    # Position Domain Events (CQRS/ES)
    'PositionOpenedEvent': 'position_update',
    'PositionIncreasedEvent': 'position_update',
    'PositionReducedEvent': 'position_update',
    'PositionClosedEvent': 'position_update',
    'PositionPriceUpdatedEvent': 'position_update',
    'PositionPnLUpdatedEvent': 'position_update',
    'PositionStopLossUpdatedEvent': 'position_update',
    'PositionTakeProfitUpdatedEvent': 'position_update',
    'PositionMetadataUpdatedEvent': 'position_update',
    'PositionReconciledEvent': 'position_update',
    'PositionSyncedFromBrokerEvent': 'position_update',

    # Portfolio Domain Events (Read-Only Domain - projects from other domains)
    # Portfolio snapshots are created when account data is updated
    'PortfolioSnapshotCreated': 'portfolio_snapshot_update',

    # Strategy events
    'StrategyUpdated': 'strategy_update',
    'StrategyExecutionStarted': 'strategy_update',
    'StrategyExecutionCompleted': 'strategy_update',
    'StrategyExecutionError': 'strategy_error',
    'StrategyParametersUpdated': 'strategy_update',
    'StrategyDeleted': 'strategy_remove',

    # System events
    'SystemAnnouncement': 'system_announcement',
    'MarketDataUpdate': 'market_data_update',
    'SystemMaintenanceScheduled': 'system_announcement',
    'DatafeedStatusChanged': 'datafeed_status',
    'CircuitBreakerTriggered': 'circuit_breaker_event',
    'SystemHealthUpdate': 'system_health_update',
    'ComponentHealthUpdate': 'component_health',
    'PerformanceMetrics': 'performance_metrics',
}


# =============================================================================
# EOF
# =============================================================================
