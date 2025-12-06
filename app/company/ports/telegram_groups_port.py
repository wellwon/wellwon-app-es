# =============================================================================
# File: app/company/ports/telegram_groups_port.py
# Description: Port interface for Telegram group management operations
# Pattern: Hexagonal Architecture / Ports & Adapters
# =============================================================================

from __future__ import annotations

from typing import Protocol, Optional, List, Tuple, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.telegram.adapter import CompanyGroupResult
    from app.infra.telegram.mtproto_client import GroupInfo, TopicInfo


@runtime_checkable
class TelegramGroupsPort(Protocol):
    """
    Port: Telegram Group Management

    Defined by: Company Domain
    Implemented by: TelegramAdapter (app/infra/telegram/adapter.py)

    This port defines the contract for Telegram group management operations.
    Used primarily by Company domain for creating company workspaces
    and by Sagas for group lifecycle management.

    Categories:
    - Group creation/management (4 methods)
    - User management (3 methods)
    - Topic management (2 methods)

    Total: 9 methods
    """

    # =========================================================================
    # Group Creation/Management (4 methods)
    # =========================================================================

    async def create_company_group(
        self,
        company_name: str,
        description: str = "",
        photo_url: Optional[str] = None,
        setup_bots: bool = True
    ) -> 'CompanyGroupResult':
        """
        Create a full company group with forum, bots, and permissions.

        This is the main method for creating company workspaces on Telegram.
        Creates a supergroup with forum enabled, sets up permissions,
        adds configured bots as admins.

        Args:
            company_name: Name for the group
            description: Group description
            photo_url: Optional photo URL for group avatar
            setup_bots: Whether to add configured bots as admins

        Returns:
            CompanyGroupResult with group details:
            - success: bool
            - group_id: Telegram group ID (or None on failure)
            - group_title: Group title
            - invite_link: Invite link for joining
            - bots_results: Results of bot setup
            - error: Error message (on failure)
        """
        ...

    async def update_group(
        self,
        group_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update group title and/or description.

        Args:
            group_id: Telegram group ID
            title: New title (if provided)
            description: New description (if provided)

        Returns:
            True if successful
        """
        ...

    async def leave_group(
        self,
        group_id: int
    ) -> bool:
        """
        Leave/delete a Telegram supergroup.

        Attempts to delete the group if we're the owner,
        otherwise just leaves the group.

        Used for compensation in Sagas when company creation fails.

        Args:
            group_id: Telegram group ID

        Returns:
            True if successful
        """
        ...

    async def get_group_info(
        self,
        group_id: int
    ) -> Optional['GroupInfo']:
        """
        Get group information.

        Args:
            group_id: Telegram group ID

        Returns:
            GroupInfo with group details, or None if not found
        """
        ...

    # =========================================================================
    # User Management (3 methods)
    # =========================================================================

    async def invite_user_to_group(
        self,
        group_id: int,
        username: str
    ) -> bool:
        """
        Invite a user to a group by username.

        Args:
            group_id: Telegram group ID
            username: Telegram username (with or without @)

        Returns:
            True if successful
        """
        ...

    async def resolve_and_invite_by_contact(
        self,
        group_id: int,
        contact: str,
        client_name: str
    ) -> Tuple[bool, Optional[int], str]:
        """
        Resolve contact (phone or @username) to telegram_user_id and invite to group.

        Supports both phone numbers and usernames. For phones, uses Telegram's
        contact import feature to find the user.

        Args:
            group_id: Telegram supergroup ID to invite user to
            contact: Phone (+79001234567) or username (@username or just username)
            client_name: Client's name for contact import

        Returns:
            Tuple of (success, telegram_user_id, status)
            Status values: 'success', 'already_member', 'user_not_found',
                          'privacy_restricted', 'rate_limit', 'error', etc.
        """
        ...

    async def remove_user_from_group(
        self,
        group_id: int,
        username: str
    ) -> bool:
        """
        Remove a user from a group.

        Args:
            group_id: Telegram group ID
            username: Telegram username

        Returns:
            True if successful
        """
        ...

    # =========================================================================
    # Topic Management (2 methods)
    # =========================================================================

    async def get_group_topics(
        self,
        group_id: int
    ) -> List['TopicInfo']:
        """
        Get all topics in a group.

        Args:
            group_id: Telegram group ID

        Returns:
            List of TopicInfo objects
        """
        ...

    async def create_chat_topic(
        self,
        group_id: int,
        topic_name: str,
        emoji: Optional[str] = None
    ) -> Optional['TopicInfo']:
        """
        Create a forum topic in a group.

        Args:
            group_id: Telegram group ID
            topic_name: Topic name
            emoji: Optional emoji character for topic icon

        Returns:
            TopicInfo if successful, None otherwise
        """
        ...


# =============================================================================
# EOF
# =============================================================================
