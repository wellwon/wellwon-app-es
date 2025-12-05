# =============================================================================
# File: app/utils/uuid_utils.py  — Universal ID Utilities (UUIDv7)
# =============================================================================
# Generates unique identifiers for system entities using UUIDv7 (RFC 9562).
#
# UUIDv7 advantages over UUIDv4:
# - Time-sortable (first 48 bits = Unix timestamp in ms)
# - Better for database indexes (sequential inserts)
# - Easier debugging (can extract creation timestamp)
# - Better for distributed tracing
#
# Migration: All uuid4() calls should use uuid7() or generate_uuid() instead.
# =============================================================================

import uuid
import hashlib
from typing import Optional, Union
from uuid import UUID

# Python 3.12+ has native UUIDv7 support (RFC 9562)


def generate_uuid() -> UUID:
    """
    Generate a new UUIDv7 (RFC 9562).

    This is the PRIMARY function for generating UUIDs in WellWon.
    UUIDv7 is time-sortable and better for database performance.

    Returns:
        UUID object (UUIDv7)
    """
    return uuid.uuid7()


def generate_uuid_str() -> str:
    """
    Generate a new UUIDv7 as string.

    Returns:
        String representation of UUIDv7
    """
    return str(uuid.uuid7())


def generate_uuid_hex() -> str:
    """
    Generate a new UUIDv7 as hex string (no dashes).

    Returns:
        Hex string (32 characters, no dashes)
    """
    return uuid.uuid7().hex


# =============================================================================
# Legacy compatibility (deprecated - use generate_uuid() instead)
# =============================================================================

def generate_uuid_v4() -> UUID:
    """
    [DEPRECATED] Generate UUIDv4. Use generate_uuid() for UUIDv7 instead.

    Kept for backward compatibility with existing data.
    """
    return uuid.uuid4()


def generate_uuid_v4_str() -> str:
    """
    [DEPRECATED] Generate UUIDv4 string. Use generate_uuid_str() instead.
    """
    return str(uuid.uuid4())


def uuid7() -> UUID:
    """
    Alias for generate_uuid() - generates UUIDv7.

    Use this for explicit v7 generation.
    """
    return uuid.uuid7()


def uuid7_str() -> str:
    """
    Generate UUIDv7 as string.
    """
    return str(uuid.uuid7())


# =============================================================================
# Specialized ID generators
# =============================================================================

def generate_strategy_id(account_id_data: Optional[Union[str, UUID]] = None) -> str:
    """
    Generates a unique, context-aware strategy ID.
    Format: 'strategy:<account_id_str_or_orphan>:<10_char_hex_hash>'

    Now uses UUIDv7 for the random component.

    Args:
        account_id_data: The account identifier (str or UUID) or None if orphaned.

    Returns:
        A string representing the unique strategy ID.
    """
    # Use UUIDv7 for high randomness with time component
    random_component = uuid.uuid7().hex[:16]

    # Determine the base identifier (account_id as string or 'orphan')
    base_identifier: str
    if account_id_data is not None:
        base_identifier = str(account_id_data)
    else:
        base_identifier = "orphan"

    # Combine base identifier and random component for hashing
    hash_input = f"{base_identifier}:{random_component}".encode('utf-8')
    short_hash = hashlib.sha1(hash_input).hexdigest()[:10]

    return f"strategy:{base_identifier}:{short_hash}"


def generate_generic_id(prefix: str = "entity") -> str:
    """
    Generates a generic ID using a specified prefix and a full UUIDv7 hex string.

    Args:
        prefix: The string prefix for the ID (e.g., "order", "user"). Defaults to "entity".

    Returns:
        A string in the format '<prefix>:<uuid7_hex>'.

    Raises:
        ValueError: If the provided prefix is empty or contains only whitespace.
    """
    cleaned_prefix = prefix.strip()
    if not cleaned_prefix:
        raise ValueError("ID prefix cannot be empty or whitespace.")

    return f"{cleaned_prefix.lower()}:{uuid.uuid7().hex}"


def generate_event_id() -> str:
    """
    Generate a unique event ID using UUIDv7.

    Specifically for event sourcing - time-sortable events.
    """
    return str(uuid.uuid7())


def generate_correlation_id() -> str:
    """
    Generate a correlation ID for distributed tracing.

    UUIDv7 makes it easy to see temporal ordering of correlated events.
    """
    return str(uuid.uuid7())


def generate_idempotency_key() -> str:
    """
    Generate an idempotency key for exactly-once delivery.

    UUIDv7 is ideal because:
    - Time-sortable for debugging
    - Unique across distributed systems
    - Can extract timestamp if needed
    """
    return str(uuid.uuid7())


# =============================================================================
# Utility functions
# =============================================================================

def extract_timestamp_from_uuid7(uuid_val: Union[str, UUID]) -> Optional[float]:
    """
    Extract Unix timestamp (in seconds) from a UUIDv7.

    Args:
        uuid_val: UUIDv7 as string or UUID object

    Returns:
        Unix timestamp in seconds, or None if not a valid UUIDv7
    """
    try:
        if isinstance(uuid_val, str):
            uuid_val = UUID(uuid_val)

        # UUIDv7: first 48 bits are Unix timestamp in milliseconds
        # Version is stored in bits 48-51 (should be 7)
        version = (uuid_val.int >> 76) & 0xF
        if version != 7:
            return None

        timestamp_ms = uuid_val.int >> 80
        return timestamp_ms / 1000.0
    except (ValueError, AttributeError):
        return None


def is_uuid7(uuid_val: Union[str, UUID]) -> bool:
    """
    Check if a UUID is version 7.

    Args:
        uuid_val: UUID to check

    Returns:
        True if UUIDv7, False otherwise
    """
    try:
        if isinstance(uuid_val, str):
            uuid_val = UUID(uuid_val)
        return uuid_val.version == 7
    except (ValueError, AttributeError):
        return False
