# app/user_account/enums.py
# =============================================================================
# File: app/user_account/enums.py
# Description: Domain enums for User Account - synchronized with database
# =============================================================================

from enum import Enum


class UserType(str, Enum):
    """
    User type (business role in platform)

    Common values (but database accepts any string):
    - client
    - payment_agent
    - logistician
    - purchaser
    - unassigned
    - manager
    """
    CLIENT = "client"
    PAYMENT_AGENT = "payment_agent"
    LOGISTICIAN = "logistician"
    PURCHASER = "purchaser"
    UNASSIGNED = "unassigned"
    MANAGER = "manager"

    @classmethod
    def get_label(cls, value: str) -> str:
        """Get Russian label for user type"""
        labels = {
            cls.CLIENT: "Клиент",
            cls.PAYMENT_AGENT: "Плат. агент",
            cls.LOGISTICIAN: "Логист",
            cls.PURCHASER: "Закупщик",
            cls.UNASSIGNED: "Не назначен",
            cls.MANAGER: "Менеджер",
        }
        return labels.get(value, "Пользователь")  # type: ignore


class UserRole(str, Enum):
    """
    User role (permission level)

    Separate from UserType - this is for authorization/permissions
    """
    USER = "user"
    ADMIN = "admin"
    DEVELOPER = "developer"


# Default values
DEFAULT_USER_TYPE = UserType.CLIENT
DEFAULT_USER_ROLE = UserRole.USER
