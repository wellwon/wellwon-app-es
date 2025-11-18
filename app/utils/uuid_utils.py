# =============================================================================
# File: app/utils/uuid_utils.py  — Universal ID Utilities
# =============================================================================
# Generates unique identifiers for system entities.
# - Strategy ID format: 'strategy:<account_id_or_orphan>:<short_random_hash>'
# - Generic ID format:  '<prefix>:<uuid4_hex>'
# - Standard UUIDv4 string generation.
# =============================================================================

import uuid
import hashlib
from typing import Optional, Union  # Added Union


# import logging
# log = logging.getLogger("wellwon.utils.uuid")

def generate_strategy_id(account_id_data: Optional[Union[str, uuid.UUID]] = None) -> str:
    """
    Generates a unique, context-aware strategy ID.
    Format: 'strategy:<account_id_str_or_orphan>:<10_char_hex_hash>'

    Args:
        account_id_data: The account identifier (str or UUID) or None if orphaned.

    Returns:
        A string representing the unique strategy ID.
    """
    # Use a significant portion of a UUID4 for high initial randomness
    random_component = uuid.uuid4().hex[:16]

    # Determine the base identifier (account_id as string or 'orphan')
    base_identifier: str
    if account_id_data is not None:
        base_identifier = str(account_id_data)  # Ensure it's a string
    else:
        base_identifier = "orphan"

    # Combine base identifier and random component for hashing
    # SHA1 is used for a short, fixed-length suffix; primarily for collision avoidance, not security.
    hash_input = f"{base_identifier}:{random_component}".encode('utf-8')
    # Take a 10-character hexadecimal representation of the hash
    # 10 hex chars = 40 bits of entropy from the hash part.
    short_hash = hashlib.sha1(hash_input).hexdigest()[:10]

    return f"strategy:{base_identifier}:{short_hash}"


def generate_generic_id(prefix: str = "entity") -> str:
    """
    Generates a generic ID using a specified prefix and a full UUIDv4 hex string.
    This ensures global uniqueness for the generated ID.

    Args:
        prefix: The string prefix for the ID (e.g., "order", "user"). Defaults to "entity".

    Returns:
        A string in the format '<prefix>:<uuid4_hex>'.

    Raises:
        ValueError: If the provided prefix is empty or contains only whitespace.
    """
    cleaned_prefix = prefix.strip()
    if not cleaned_prefix:
        # log.error("Attempted to generate generic ID with empty prefix.") # Optional logging
        raise ValueError("ID prefix cannot be empty or whitespace.")

    # Use lowercase prefix for consistency
    return f"{cleaned_prefix.lower()}:{uuid.uuid4().hex}"


def generate_uuid_v4_str() -> str:
    """Generates a standard UUID version 4 as a string."""
    return str(uuid.uuid4())

# Example Usage (can be removed or kept for testing):
# if __name__ == "__main__":
#     print("Strategy IDs:")
#     print(f"  Orphan: {generate_strategy_id()}")
#     print(f"  Account 'acc123': {generate_strategy_id('acc123')}")
#     my_uuid_acc_id = uuid.uuid4()
#     print(f"  Account UUID {my_uuid_acc_id}: {generate_strategy_id(my_uuid_acc_id)}")
#
#     print("\nGeneric IDs:")
#     print(f"  Default: {generate_generic_id()}")
#     print(f"  Order:   {generate_generic_id('order')}")
#     print(f"  Session: {generate_generic_id('Session')}") # Will be lowercased
#
#     print("\nUUIDv4 String:")
#     print(f"  {generate_uuid_v4_str()}")