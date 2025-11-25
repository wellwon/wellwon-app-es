# =============================================================================
# File: app/utils/datetime_utils.py
# Description: Datetime utilities with robust parsing
# =============================================================================

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union


def parse_timestamp_robust(
    timestamp: Union[str, datetime, None],
    fallback: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Parse timestamp string with robust handling of edge cases.

    Handles:
    - ISO 8601 format (standard)
    - PostgreSQL hour 24 format (edge case from NOW()::text)
    - Missing timezone (defaults to UTC)
    - Already datetime objects

    Args:
        timestamp: Timestamp string or datetime object
        fallback: Fallback datetime if parsing fails (default: None)

    Returns:
        datetime object or fallback value

    Examples:
        >>> parse_timestamp_robust("2025-11-25T00:54:40.123456+00:00")
        datetime(2025, 11, 25, 0, 54, 40, 123456, tzinfo=timezone.utc)

        >>> parse_timestamp_robust("2025-11-25 24:00:00")  # PostgreSQL hour 24
        datetime(2025, 11, 26, 0, 0, 0, tzinfo=timezone.utc)
    """
    if timestamp is None:
        return fallback

    if isinstance(timestamp, datetime):
        # Already a datetime, ensure timezone
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    if not isinstance(timestamp, str):
        return fallback

    # Clean the timestamp string
    ts = timestamp.strip()

    # Handle 'Z' suffix (UTC marker)
    ts = ts.replace('Z', '+00:00')

    # Handle PostgreSQL hour 24 format: "2025-11-25 24:00:00"
    # This represents midnight of the next day
    hour_24_match = re.match(r'^(\d{4}-\d{2}-\d{2})\s+24:(\d{2}:\d{2}(?:\.\d+)?)', ts)
    if hour_24_match:
        date_part = hour_24_match.group(1)
        time_remainder = hour_24_match.group(2)
        try:
            # Parse the date and add one day
            base_date = datetime.strptime(date_part, '%Y-%m-%d')
            next_day = base_date + timedelta(days=1)
            # Reconstruct with hour 00
            ts = f"{next_day.strftime('%Y-%m-%d')}T00:{time_remainder}"
        except ValueError:
            pass

    # Try standard ISO format parsing
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # Try additional formats
    formats = [
        '%Y-%m-%d %H:%M:%S.%f%z',
        '%Y-%m-%d %H:%M:%S%z',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Last resort fallback
    return fallback if fallback else datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# =============================================================================
# EOF
# =============================================================================
