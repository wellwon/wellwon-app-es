# =============================================================================
# File: app/company/command_handlers/__init__.py
# Description: Company command handlers package
# =============================================================================

from app.company.command_handlers.company_handlers import (
    CreateCompanyHandler,
    UpdateCompanyHandler,
    ArchiveCompanyHandler,
    RestoreCompanyHandler,
    DeleteCompanyHandler,
)
from app.company.command_handlers.user_handlers import (
    AddUserToCompanyHandler,
    RemoveUserFromCompanyHandler,
    ChangeUserCompanyRoleHandler,
)
from app.company.command_handlers.telegram_handlers import (
    CreateTelegramSupergroupHandler,
    LinkTelegramSupergroupHandler,
    UnlinkTelegramSupergroupHandler,
    UpdateTelegramSupergroupHandler,
)
from app.company.command_handlers.balance_handlers import (
    UpdateCompanyBalanceHandler,
)

__all__ = [
    # Company lifecycle
    "CreateCompanyHandler",
    "UpdateCompanyHandler",
    "ArchiveCompanyHandler",
    "RestoreCompanyHandler",
    "DeleteCompanyHandler",
    # User relationships
    "AddUserToCompanyHandler",
    "RemoveUserFromCompanyHandler",
    "ChangeUserCompanyRoleHandler",
    # Telegram
    "CreateTelegramSupergroupHandler",
    "LinkTelegramSupergroupHandler",
    "UnlinkTelegramSupergroupHandler",
    "UpdateTelegramSupergroupHandler",
    # Balance
    "UpdateCompanyBalanceHandler",
]
