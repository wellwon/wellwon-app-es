# =============================================================================
# File: app/security/ssl/alerting.py
# Description: Simple alert management module for TradeCore
# =============================================================================

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum

log = logging.getLogger("tradecore.ssl.alerting")


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """Simple alert manager for sending notifications."""

    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
        self.handlers = []

    async def send_alert(
            self,
            severity: str,
            message: str,
            details: Optional[Dict[str, Any]] = None,
            alert_type: Optional[str] = None
    ):
        """Send an alert."""
        alert = {
            "severity": severity,
            "message": message,
            "details": details or {},
            "alert_type": alert_type,
            "timestamp": datetime.now(timezone.utc),
            "id": len(self.alerts) + 1
        }

        self.alerts.append(alert)

        # Log the alert
        if severity == "critical":
            log.critical(f"ALERT: {message} - {details}")
        elif severity == "error":
            log.error(f"ALERT: {message} - {details}")
        elif severity == "warning":
            log.warning(f"ALERT: {message} - {details}")
        else:
            log.info(f"ALERT: {message} - {details}")

        # Process handlers (webhook, email, etc.)
        for handler in self.handlers:
            try:
                await handler(alert)
            except Exception as e:
                log.error(f"Error in alert handler: {e}")

    def add_handler(self, handler):
        """Add an alert handler function."""
        self.handlers.append(handler)

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        return self.alerts[-limit:]

    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []


# Global instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager