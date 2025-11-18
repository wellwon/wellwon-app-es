# =============================================================================
# File: app/wse/core/event_filters.py
# Description: Advanced Event Filtering for WSE
# =============================================================================

"""
EventFilter for WSE

Advanced event filtering with MongoDB-like query operators.

Supported Operators:
- $in: Value must be in list
- $regex: Regular expression match
- $gt, $lt, $gte, $lte: Comparison operators
- $ne: Not equal
- $exists: Field existence check
- $contains: Substring match
- $startswith, $endswith: String prefix/suffix match

Example:
    ```python
    criteria = {
        "event_type": {"$in": ["OrderPlaced", "OrderFilled"]},
        "symbol": {"$regex": "^AAPL"},
        "quantity": {"$gte": 100}
    }

    if EventFilter.matches(event, criteria):
        # Process event
    ```

Nested Fields:
    Use dot notation for nested field access:
    ```python
    criteria = {
        "metadata.user_id": "user123",
        "payload.price": {"$gt": 100}
    }
    ```
"""

import re
from typing import Any, Dict

import logging

log = logging.getLogger("wellwon.wse.filters")


class EventFilter:
    """Advanced event filtering with multiple strategies"""

    @staticmethod
    def matches(event: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if an event matches filter criteria"""
        # Special control filters
        if 'start_from_latest' in criteria:
            # This is a control filter, not a content filter
            return True

        for key, expected in criteria.items():
            if '.' in key:
                # Handle nested keys
                value = EventFilter._get_nested(event, key)
            else:
                value = event.get(key)

            if not EventFilter._match_value(value, expected):
                return False
        return True

    @staticmethod
    def _get_nested(data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    @staticmethod
    def _match_value(value: Any, expected: Any) -> bool:
        """Match value against expected criteria"""
        if isinstance(expected, dict):
            # Special operators
            if '$in' in expected:
                return value in expected['$in']
            elif '$regex' in expected:
                return bool(re.match(expected['$regex'], str(value)))
            elif '$gt' in expected:
                return value > expected['$gt']
            elif '$lt' in expected:
                return value < expected['$lt']
            elif '$gte' in expected:
                return value >= expected['$gte']
            elif '$lte' in expected:
                return value <= expected['$lte']
            elif '$ne' in expected:
                return value != expected['$ne']
            elif '$exists' in expected:
                return (value is not None) == expected['$exists']
            elif '$contains' in expected:
                return expected['$contains'] in str(value)
            elif '$startswith' in expected:
                return str(value).startswith(expected['$startswith'])
            elif '$endswith' in expected:
                return str(value).endswith(expected['$endswith'])
        return value == expected


# =============================================================================
# EOF
# =============================================================================
