# =============================================================================
# File: app/infra/telegram/mtproto_client.py
# Description: Telegram MTProto client using Telethon for user-level operations
# =============================================================================

from __future__ import annotations

import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from app.infra.telegram.config import TelegramConfig

log = logging.getLogger("wellwon.telegram.mtproto_client")

# Lazy import telethon to avoid import errors when not installed
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import (
        CreateChannelRequest,
        CreateForumTopicRequest,
        EditForumTopicRequest,
        DeleteTopicHistoryRequest,
        EditAdminRequest,
        InviteToChannelRequest,
        EditTitleRequest,
        EditAboutRequest,
        EditPhotoRequest,
        GetForumTopicsRequest,
        UpdatePinnedForumTopicRequest,
        EditBannedRequest,
    )
    from telethon.tl.functions.messages import (
        ExportChatInviteRequest,
        EditChatDefaultBannedRightsRequest,
    )
    from telethon.tl.functions.contacts import ResolveUsernameRequest
    from telethon.tl.types import ChatAdminRights, ChatBannedRights
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = None
    StringSession = None
    log.warning("telethon not installed. MTProto features will be disabled.")


# Emoji ID mapping for forum topics
EMOJI_MAP = {
    # Main organizational emojis
    "🎯": 5789953624849456205,
    "📝": 5787188704434982946,
    "💼": 5789678837029509659,
    "🔥": 5789419962516207616,
    "⚡": 5787544865457888514,
    "🚀": 5789739369064388642,
    "💡": 5787846042074624041,
    "🎉": 5789953624849456206,
    "📊": 5787188704434982947,
    "🔧": 5789678837029509660,
    "🌟": 5789419962516207617,
    "📱": 5787544865457888515,
    "💰": 5789739369064388643,
    "🎮": 5787846042074624042,
    "🏆": 5789953624849456207,
    "📈": 5787188704434982948,
    "🔔": 5789678837029509661,
    "💻": 5789419962516207618,
    "🎨": 5787544865457888516,
    "🎵": 5789739369064388644,
    # Status emojis
    "✅": 5789953624849456208,
    "❌": 5789953624849456209,
    "⚡️": 5787544865457888517,
    "🗄️": 5789678837029509662,
    "🔒": 5789678837029509663,
    "🔓": 5789678837029509664,
    "⏰": 5787544865457888518,
    "📅": 5787188704434982950,
    "🔍": 5789678837029509665,
    "📦": 5787188704434982951,
    "🏠": 5789953624849456211,
    "🌐": 5789419962516207619,
    "🔗": 5789678837029509666,
    "📬": 5787188704434982952,
    "📭": 5787188704434982953,
    "📋": 5787188704434982949,
}

# Default bot configuration for groups
DEFAULT_BOTS_CONFIG = [
    {
        "username": "WellWonAssist_bot",
        "title": "Assistant",
    },
    {
        "username": "wellwon_app_bot",
        "title": "Manager",
    }
]


@dataclass
class GroupInfo:
    """Information about a Telegram group"""
    group_id: int
    title: str
    access_hash: Optional[int] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    members_count: Optional[int] = None


@dataclass
class TopicInfo:
    """Information about a forum topic"""
    topic_id: int
    title: str
    emoji: Optional[str] = None
    emoji_id: Optional[int] = None
    pinned: bool = False


@dataclass
class OperationResult:
    """Generic result for MTProto operations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TelegramMTProtoClient:
    """
    Telegram MTProto client for user-level operations.

    Uses Telethon for operations that are not available through Bot API:
    - Creating supergroups with forums
    - Managing forum topics (create, edit, delete)
    - Setting topic emojis
    - Adding bots as administrators
    - Setting group photos
    - Managing group permissions
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self._client: Optional['TelegramClient'] = None
        self._connected = False
        self._bots_config = DEFAULT_BOTS_CONFIG

    async def connect(self) -> bool:
        """Connect to Telegram MTProto servers"""
        if not TELETHON_AVAILABLE:
            log.error("telethon not installed. Cannot connect to MTProto.")
            return False

        if self._connected:
            return True

        try:
            # Create client with StringSession if available
            session_string = getattr(self.config, 'session_string', None)
            if session_string:
                log.debug("Using existing session string for MTProto")
                self._client = TelegramClient(
                    StringSession(session_string),
                    self.config.api_id,
                    self.config.api_hash
                )
            else:
                log.debug("Creating new session for MTProto")
                self._client = TelegramClient(
                    self.config.session_name,
                    self.config.api_id,
                    self.config.api_hash
                )

            await self._client.connect()

            # Check if authorized
            if not await self._client.is_user_authorized():
                if self.config.admin_phone:
                    log.info(f"Starting MTProto authorization for {self.config.admin_phone}")
                    await self._client.start(phone=self.config.admin_phone)
                else:
                    log.error("MTProto not authorized and no phone number provided")
                    return False

            me = await self._client.get_me()
            log.info(f"MTProto connected as: {me.first_name} (ID: {me.id})")

            self._connected = True
            return True

        except Exception as e:
            log.error(f"Failed to connect MTProto: {e}", exc_info=True)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Telegram"""
        if self._client and self._connected:
            await self._client.disconnect()
            self._connected = False
            log.info("MTProto disconnected")

    async def _ensure_connected(self) -> bool:
        """Ensure client is connected"""
        if not self._connected:
            return await self.connect()
        return True

    # =========================================================================
    # Group Management
    # =========================================================================

    async def create_supergroup(
        self,
        title: str,
        description: str = "",
        forum: bool = True
    ) -> Optional[GroupInfo]:
        """
        Create a new supergroup with optional forum support.

        Args:
            title: Group title
            description: Group description
            forum: Enable forum (topics) support

        Returns:
            GroupInfo if successful, None otherwise
        """
        if not await self._ensure_connected():
            return None

        try:
            # Check if group with this title already exists
            existing = await self._find_group_by_title(title)
            if existing:
                log.info(f"Group '{title}' already exists, returning existing")
                return GroupInfo(
                    group_id=existing.id,
                    title=existing.title,
                    access_hash=getattr(existing, 'access_hash', None)
                )

            result = await self._client(CreateChannelRequest(
                title=title,
                about=description,
                megagroup=True,
                forum=forum
            ))

            group = result.chats[0]
            log.info(f"Supergroup created: {title} (ID: {group.id})")

            return GroupInfo(
                group_id=group.id,
                title=group.title,
                access_hash=group.access_hash
            )

        except Exception as e:
            log.error(f"Failed to create supergroup: {e}", exc_info=True)
            return None

    async def _find_group_by_title(self, title: str):
        """Find existing group by title"""
        try:
            async for dialog in self._client.iter_dialogs():
                entity = dialog.entity
                if getattr(entity, 'megagroup', False) and getattr(entity, 'title', '') == title:
                    return entity
            return None
        except Exception:
            return None

    async def update_group_title(self, group_id: int, new_title: str) -> bool:
        """Update group title"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            await self._client(EditTitleRequest(channel=group, title=new_title))
            log.info(f"Group {group_id} title updated to: {new_title}")
            return True
        except Exception as e:
            log.error(f"Failed to update group title: {e}", exc_info=True)
            return False

    async def update_group_description(self, group_id: int, description: str) -> bool:
        """Update group description"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            await self._client(EditAboutRequest(channel=group, about=description))
            log.info(f"Group {group_id} description updated")
            return True
        except Exception as e:
            log.error(f"Failed to update group description: {e}", exc_info=True)
            return False

    async def set_group_photo(self, group_id: int, photo_url: str) -> bool:
        """Set group photo from URL"""
        if not await self._ensure_connected():
            return False

        try:
            import aiohttp
            import tempfile
            import os

            # Download photo
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url) as response:
                    if response.status != 200:
                        log.error(f"Failed to download photo: HTTP {response.status}")
                        return False
                    content = await response.read()

            # Save to temp file and upload
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name

            try:
                group = await self._client.get_entity(group_id)
                uploaded_file = await self._client.upload_file(tmp_file_path)
                await self._client(EditPhotoRequest(channel=group, photo=uploaded_file))
                log.info(f"Group {group_id} photo set")
                return True
            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

        except Exception as e:
            log.error(f"Failed to set group photo: {e}", exc_info=True)
            return False

    async def set_group_permissions(self, group_id: int) -> bool:
        """Set default group permissions (restrict regular members)"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)

            banned_rights = ChatBannedRights(
                until_date=None,
                view_messages=False,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False,
                send_polls=False,
                change_info=True,  # Restrict
                invite_users=False,
                pin_messages=True,  # Restrict
                manage_topics=False
            )

            await self._client(EditChatDefaultBannedRightsRequest(
                peer=group,
                banned_rights=banned_rights
            ))

            log.info(f"Group {group_id} permissions set")
            return True

        except Exception as e:
            log.error(f"Failed to set group permissions: {e}", exc_info=True)
            return False

    async def get_invite_link(self, group_id: int) -> Optional[str]:
        """Get group invite link"""
        if not await self._ensure_connected():
            return None

        try:
            group = await self._client.get_entity(group_id)
            invite = await self._client(ExportChatInviteRequest(group.id))
            return invite.link
        except Exception as e:
            log.error(f"Failed to get invite link: {e}", exc_info=True)
            return None

    async def get_group_info(self, group_id: int) -> Optional[GroupInfo]:
        """Get full group information"""
        if not await self._ensure_connected():
            return None

        try:
            group = await self._client.get_entity(group_id)
            invite_link = await self.get_invite_link(group_id)

            return GroupInfo(
                group_id=group.id,
                title=group.title,
                access_hash=getattr(group, 'access_hash', None),
                description=getattr(group, 'about', ''),
                invite_link=invite_link,
                members_count=getattr(group, 'participants_count', 0)
            )
        except Exception as e:
            log.error(f"Failed to get group info: {e}", exc_info=True)
            return None

    # =========================================================================
    # Topic Management
    # =========================================================================

    async def create_forum_topic(
        self,
        group_id: int,
        title: str,
        icon_emoji: Optional[str] = None
    ) -> Optional[TopicInfo]:
        """
        Create a new forum topic.

        Args:
            group_id: Telegram group ID
            title: Topic title
            icon_emoji: Optional emoji character (will be converted to ID)

        Returns:
            TopicInfo if successful, None otherwise
        """
        if not await self._ensure_connected():
            return None

        try:
            group = await self._client.get_entity(group_id)

            # Convert emoji to ID
            icon_emoji_id = EMOJI_MAP.get(icon_emoji) if icon_emoji else None

            result = await self._client(CreateForumTopicRequest(
                channel=group,
                title=title,
                icon_emoji_id=icon_emoji_id,
                send_as=None,
                random_id=None
            ))

            topic_id = result.updates[0].message.id if result.updates else None
            log.info(f"Topic '{title}' created with ID: {topic_id}")

            return TopicInfo(
                topic_id=topic_id,
                title=title,
                emoji=icon_emoji,
                emoji_id=icon_emoji_id
            )

        except Exception as e:
            log.error(f"Failed to create forum topic: {e}", exc_info=True)
            return None

    async def update_forum_topic(
        self,
        group_id: int,
        topic_id: int,
        new_title: Optional[str] = None,
        new_emoji: Optional[str] = None
    ) -> bool:
        """
        Update forum topic title and/or emoji.

        Args:
            group_id: Telegram group ID
            topic_id: Topic ID to update
            new_title: New title (optional)
            new_emoji: New emoji character (optional)

        Returns:
            True if successful, False otherwise
        """
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)

            # Convert emoji to ID
            icon_emoji_id = EMOJI_MAP.get(new_emoji) if new_emoji else None

            await self._client(EditForumTopicRequest(
                channel=group,
                topic_id=topic_id,
                title=new_title,
                icon_emoji_id=icon_emoji_id
            ))

            log.info(f"Topic {topic_id} updated")
            return True

        except Exception as e:
            log.error(f"Failed to update forum topic: {e}", exc_info=True)
            return False

    async def delete_forum_topic(self, group_id: int, topic_id: int) -> bool:
        """Delete a forum topic"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            await self._client(DeleteTopicHistoryRequest(
                channel=group,
                top_msg_id=topic_id
            ))
            log.info(f"Topic {topic_id} deleted from group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to delete forum topic: {e}", exc_info=True)
            return False

    async def pin_forum_topic(self, group_id: int, topic_id: int, pinned: bool = True) -> bool:
        """Pin or unpin a forum topic"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            await self._client(UpdatePinnedForumTopicRequest(
                channel=group,
                topic_id=topic_id,
                pinned=pinned
            ))
            log.info(f"Topic {topic_id} {'pinned' if pinned else 'unpinned'}")
            return True
        except Exception as e:
            log.error(f"Failed to pin/unpin topic: {e}", exc_info=True)
            return False

    async def get_forum_topics(self, group_id: int) -> List[TopicInfo]:
        """Get list of all forum topics"""
        if not await self._ensure_connected():
            return []

        try:
            group = await self._client.get_entity(group_id)

            result = await self._client(GetForumTopicsRequest(
                channel=group,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))

            topics = []
            for message in result.messages:
                if hasattr(message, 'action') and hasattr(message.action, 'title'):
                    action = message.action
                    topic_info = TopicInfo(
                        topic_id=message.id,
                        title=action.title,
                        emoji_id=getattr(action, 'icon_emoji_id', None),
                        pinned=getattr(message, 'pinned', False)
                    )
                    topics.append(topic_info)

            return topics

        except Exception as e:
            log.error(f"Failed to get forum topics: {e}", exc_info=True)
            return []

    # =========================================================================
    # Bot Management
    # =========================================================================

    async def add_bot_as_admin(
        self,
        group_id: int,
        bot_username: str,
        title: str = "Bot"
    ) -> bool:
        """
        Add a bot to the group as administrator.

        Args:
            group_id: Telegram group ID
            bot_username: Bot username (without @)
            title: Admin title for the bot

        Returns:
            True if successful, False otherwise
        """
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)

            # Resolve bot username
            resolved = await self._client(ResolveUsernameRequest(bot_username))
            bot_user = resolved.users[0]

            # Invite bot to group
            await self._client(InviteToChannelRequest(
                channel=group.id,
                users=[bot_user.id]
            ))

            await asyncio.sleep(1)  # Wait before promoting

            # Set admin rights
            rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True,
                manage_topics=True,
                post_stories=True,
                edit_stories=True,
                delete_stories=True
            )

            await self._client(EditAdminRequest(
                channel=group.id,
                user_id=bot_user.id,
                admin_rights=rights,
                rank=title
            ))

            log.info(f"Bot @{bot_username} added as admin to group {group_id}")
            return True

        except Exception as e:
            log.error(f"Failed to add bot as admin: {e}", exc_info=True)
            return False

    async def setup_group_bots(self, group_id: int) -> List[Dict[str, Any]]:
        """
        Add all configured bots to the group.

        Returns:
            List of results for each bot
        """
        results = []

        for bot_config in self._bots_config:
            try:
                success = await self.add_bot_as_admin(
                    group_id=group_id,
                    bot_username=bot_config["username"],
                    title=bot_config["title"]
                )
                results.append({
                    "username": bot_config["username"],
                    "title": bot_config["title"],
                    "status": "success" if success else "error"
                })
            except Exception as e:
                results.append({
                    "username": bot_config["username"],
                    "title": bot_config["title"],
                    "status": "error",
                    "reason": str(e)
                })

        return results

    # =========================================================================
    # User Management
    # =========================================================================

    async def invite_user(self, group_id: int, username: str) -> bool:
        """Invite a user to the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            user = await self._client.get_entity(username)
            await self._client(InviteToChannelRequest(channel=group, users=[user]))
            log.info(f"User @{username} invited to group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to invite user: {e}", exc_info=True)
            return False

    async def remove_user(self, group_id: int, username: str) -> bool:
        """Remove a user from the group"""
        if not await self._ensure_connected():
            return False

        try:
            group = await self._client.get_entity(group_id)
            user = await self._client.get_entity(username)
            await self._client(EditBannedRequest(
                channel=group,
                participant=user,
                banned_rights=ChatBannedRights(until_date=None, view_messages=True)
            ))
            log.info(f"User @{username} removed from group {group_id}")
            return True
        except Exception as e:
            log.error(f"Failed to remove user: {e}", exc_info=True)
            return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def get_emoji_id(emoji: str) -> Optional[int]:
        """Get emoji ID from emoji character"""
        return EMOJI_MAP.get(emoji)

    @staticmethod
    def get_available_emojis() -> Dict[str, int]:
        """Get all available emojis with their IDs"""
        return EMOJI_MAP.copy()
