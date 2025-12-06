# =============================================================================
# File: app/chat/value_objects.py
# Description: Chat domain value objects
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ContactType(str, Enum):
    """Type of Telegram contact identifier"""
    PHONE = "phone"       # +79001234567
    USERNAME = "username"  # @username or username


@dataclass(frozen=True)
class TelegramContact:
    """
    Value Object: identifies a Telegram user by phone or username.

    Immutable and auto-detects the contact type from the input string.
    """
    contact_type: ContactType
    value: str  # phone number or username (without @)

    @classmethod
    def from_string(cls, contact: str) -> 'TelegramContact':
        """
        Auto-detect contact type from string.

        - Starts with + or digit = phone
        - Otherwise = username (@ prefix is stripped)

        Args:
            contact: Phone number (+79001234567) or username (@username or username)

        Returns:
            TelegramContact value object
        """
        contact = contact.strip()

        if not contact:
            raise ValueError("Contact cannot be empty")

        if contact.startswith('+') or contact[0].isdigit():
            # Phone number - keep as-is
            return cls(ContactType.PHONE, contact)
        else:
            # Username - remove @ prefix if present
            return cls(ContactType.USERNAME, contact.lstrip('@'))

    @property
    def is_phone(self) -> bool:
        """Returns True if this is a phone contact"""
        return self.contact_type == ContactType.PHONE

    @property
    def is_username(self) -> bool:
        """Returns True if this is a username contact"""
        return self.contact_type == ContactType.USERNAME

    def __str__(self) -> str:
        if self.is_username:
            return f"@{self.value}"
        return self.value
