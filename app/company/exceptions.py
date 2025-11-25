# =============================================================================
# File: app/company/exceptions.py
# Description: Company domain exceptions
# =============================================================================

from app.common.exceptions.exceptions import DomainError, ResourceNotFoundError


class CompanyError(DomainError):
    """Base exception for Company domain"""
    pass


class CompanyNotFoundError(ResourceNotFoundError):
    """Company not found"""
    def __init__(self, company_id: str):
        super().__init__(f"Company not found: {company_id}")
        self.company_id = company_id


class CompanyAlreadyExistsError(CompanyError):
    """Company already exists"""
    def __init__(self, company_id: str):
        super().__init__(f"Company already exists: {company_id}")
        self.company_id = company_id


class CompanyInactiveError(CompanyError):
    """Company is not active"""
    def __init__(self, company_id: str):
        super().__init__(f"Company {company_id} is not active")
        self.company_id = company_id


class UserNotInCompanyError(CompanyError):
    """User is not associated with the company"""
    def __init__(self, company_id: str, user_id: str):
        super().__init__(f"User {user_id} is not associated with company {company_id}")
        self.company_id = company_id
        self.user_id = user_id


class UserAlreadyInCompanyError(CompanyError):
    """User is already associated with the company"""
    def __init__(self, company_id: str, user_id: str):
        super().__init__(f"User {user_id} is already associated with company {company_id}")
        self.company_id = company_id
        self.user_id = user_id


class InsufficientCompanyPermissionsError(CompanyError):
    """User does not have sufficient permissions in company"""
    def __init__(self, user_id: str, action: str):
        super().__init__(f"User {user_id} does not have permission to {action}")
        self.user_id = user_id
        self.action = action


class TelegramSupergroupNotFoundError(ResourceNotFoundError):
    """Telegram supergroup not found for company"""
    def __init__(self, company_id: str, telegram_group_id: int):
        super().__init__(f"Telegram supergroup {telegram_group_id} not found for company {company_id}")
        self.company_id = company_id
        self.telegram_group_id = telegram_group_id


class TelegramSupergroupAlreadyLinkedError(CompanyError):
    """Telegram supergroup is already linked to company"""
    def __init__(self, company_id: str, telegram_group_id: int):
        super().__init__(f"Telegram supergroup {telegram_group_id} is already linked to company {company_id}")
        self.company_id = company_id
        self.telegram_group_id = telegram_group_id


class InsufficientBalanceError(CompanyError):
    """Company does not have sufficient balance"""
    def __init__(self, company_id: str, required: str, available: str):
        super().__init__(f"Company {company_id} has insufficient balance: required {required}, available {available}")
        self.company_id = company_id
        self.required = required
        self.available = available


class CannotRemoveOwnerError(CompanyError):
    """Cannot remove the owner from company"""
    def __init__(self, company_id: str, user_id: str):
        super().__init__(f"Cannot remove owner {user_id} from company {company_id}")
        self.company_id = company_id
        self.user_id = user_id
