# =============================================================================
# File: app/user_account/command_handlers/__init__.py
# Description: Command Handlers exports for User Account domain
# =============================================================================

from .auth_handlers import (
    CreateUserAccountHandler,
    AuthenticateUserHandler,
    DeleteUserHandler,
    VerifyUserEmailHandler,
)

from .password_handlers import (
    ChangeUserPasswordHandler,
    ResetUserPasswordWithSecretHandler,
)

from .profile_handlers import (
    UpdateUserProfileHandler,
)

__all__ = [
    # Auth
    'CreateUserAccountHandler',
    'AuthenticateUserHandler',
    'DeleteUserHandler',
    'VerifyUserEmailHandler',
    # Password
    'ChangeUserPasswordHandler',
    'ResetUserPasswordWithSecretHandler',
    # Profile
    'UpdateUserProfileHandler',
]
