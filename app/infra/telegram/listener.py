# =============================================================================
# File: app/infra/telegram/listener.py
# Description: Event listener that syncs Chat Domain events to Telegram
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional, Any, TYPE_CHECKING
from uuid import UUID

from app.infra.telegram.adapter import TelegramAdapter, get_telegram_adapter

if TYPE_CHECKING:
    from app.infra.cqrs.query_bus import QueryBus

log = logging.getLogger("wellwon.telegram.listener")


class TelegramEventListener:
    """
    Listens to Chat Domain events and syncs to Telegram.

    This listener subscribes to domain events and translates them
    to Telegram API calls via the TelegramAdapter.

    Events handled:
    - MessageSent: Web message -> Telegram
    - ChatCreated: Create Telegram topic if configured
    - ChatUpdated: Update topic name/emoji
    - ChatDeleted: (Optional) Archive/close topic

    Architecture:
    - Receives events from EventBus (RedPanda)
    - Uses QueryBus to lookup data (CQRS compliance)
    - Calls TelegramAdapter to perform Telegram operations

    Pattern follows WSEDomainPublisher for consistency.
    """

    def __init__(
        self,
        event_bus: Any,
        query_bus: 'QueryBus',
        telegram_adapter: Optional[TelegramAdapter] = None,
    ):
        self._event_bus = event_bus
        self._query_bus = query_bus
        self._telegram: Optional[TelegramAdapter] = telegram_adapter
        self._initialized = False
        self._running = False
        self._subscriptions: dict = {}

    async def start(self) -> None:
        """Start the Telegram Event Listener - subscribe to chat domain events"""
        if self._running:
            log.warning("TelegramEventListener already running")
            return

        log.info("Starting TelegramEventListener...")

        # Initialize telegram adapter if not provided
        if self._telegram is None:
            self._telegram = await get_telegram_adapter()

        self._initialized = True
        self._running = True

        try:
            await self._subscribe_to_chat_events()
            log.info(
                f"TelegramEventListener ready - "
                f"{len(self._subscriptions)} subscriptions active"
            )
        except Exception as e:
            log.error(f"Failed to start TelegramEventListener: {e}", exc_info=True)
            self._running = False
            raise

    async def _subscribe_to_chat_events(self) -> None:
        """Subscribe to chat domain events for Telegram forwarding"""
        if not self._running:
            return

        import os
        topic = "transport.chat-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_chat_event,
                group="telegram-event-listener",
                consumer=f"telegram-listener-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::telegram-event-listener"
            log.info(f"Subscribed to {topic} for Telegram forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _handle_chat_event(self, event: dict) -> None:
        """Route chat domain events to appropriate handlers"""
        event_type = event.get("event_type", "")

        handler_map = {
            "MessageSent": self.on_message_sent,
            "MessageDeleted": self.on_message_deleted,
            "ChatCreated": self.on_chat_created,
            "ChatUpdated": self.on_chat_updated,
            "ChatArchived": self.on_chat_archived,
            "ChatHardDeleted": self.on_chat_deleted,  # Hard delete with Telegram topic removal
        }

        handler = handler_map.get(event_type)
        if handler:
            await handler(event)
        else:
            log.debug(f"No Telegram handler for event type: {event_type}")

    async def stop(self) -> None:
        """Stop the Telegram Event Listener"""
        if not self._running:
            return

        log.info("Stopping TelegramEventListener...")
        self._running = False
        self._subscriptions.clear()
        log.info("TelegramEventListener stopped")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def on_message_sent(self, event: dict) -> None:
        """
        Handle MessageSent event - send message to Telegram.

        Event payload:
        {
            "chat_id": UUID,
            "message_id": UUID,
            "sender_id": UUID,
            "content": str,
            "message_type": str,  # text, photo, document, voice
            "file_url": Optional[str],
            "source": str,  # web, telegram, api
            "metadata": dict
        }
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        # Skip messages that came FROM Telegram (avoid echo)
        # Also skip messages from web - SendMessageHandler already syncs those to Telegram
        source = event.get("source", "web")
        if source == "telegram":
            log.debug(f"Skipping message {event.get('message_id')} - already from Telegram")
            return
        if source == "web":
            log.debug(f"Skipping message {event.get('message_id')} - web messages synced by SendMessageHandler")
            return

        try:
            chat_id = event.get("chat_id")
            content = event.get("content", "")
            file_url = event.get("file_url")
            message_type = event.get("message_type", "text")
            sender_id = event.get("sender_id")

            # Lookup sender name via QueryBus (CQRS compliant)
            sender_name = "Unknown"
            if sender_id:
                try:
                    from app.user_account.queries import GetUserProfileQuery
                    user = await self._query_bus.query(
                        GetUserProfileQuery(
                            user_id=UUID(sender_id) if isinstance(sender_id, str) else sender_id,
                            include_preferences=False,
                            include_security_settings=False
                        )
                    )
                    if user:
                        first = getattr(user, 'first_name', '') or ''
                        last = getattr(user, 'last_name', '') or ''
                        username = getattr(user, 'username', '') or ''
                        sender_name = f"{first} {last}".strip() or username or "Unknown"
                except Exception as e:
                    log.warning(f"Failed to lookup sender {sender_id}: {e}")

            # Get chat configuration via QueryBus (CQRS compliant)
            from app.chat.queries import GetChatByIdQuery
            chat = await self._query_bus.query(
                GetChatByIdQuery(
                    chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                )
            )

            if not chat:
                log.debug(f"Chat {chat_id} not found")
                return

            # Check if chat has Telegram integration
            telegram_chat_id = getattr(chat, 'telegram_chat_id', None)
            if not telegram_chat_id:
                log.debug(f"Chat {chat_id} has no Telegram integration")
                return

            # Get Telegram identifiers
            topic_id = getattr(chat, 'telegram_topic_id', None)

            # Format message with sender name
            formatted_content = f"<b>{sender_name}</b>\n{content}"

            # Send to Telegram based on type
            if file_url and message_type in ("photo", "image"):
                result = await self._telegram.send_file(
                    chat_id=telegram_chat_id,
                    file_url=file_url,
                    caption=formatted_content if content else None,
                    topic_id=topic_id
                )
            elif file_url and message_type == "voice":
                result = await self._telegram.send_voice(
                    chat_id=telegram_chat_id,
                    voice_url=file_url,
                    caption=formatted_content if content else None,
                    topic_id=topic_id
                )
            elif file_url:
                result = await self._telegram.send_file(
                    chat_id=telegram_chat_id,
                    file_url=file_url,
                    caption=formatted_content if content else None,
                    topic_id=topic_id
                )
            else:
                result = await self._telegram.send_message(
                    chat_id=telegram_chat_id,
                    text=formatted_content,
                    topic_id=topic_id
                )

            if result.success:
                log.debug(f"Message sent to Telegram: {result.message_id}")
            else:
                log.error(f"Failed to send to Telegram: {result.error}")

        except Exception as e:
            log.error(f"Error handling MessageSent event: {e}", exc_info=True)

    async def on_message_deleted(self, event: dict) -> None:
        """
        Handle MessageDeleted event - delete message in Telegram.

        Event payload:
        {
            "message_id": UUID,
            "chat_id": UUID,
            "deleted_by": UUID,
            "telegram_message_id": Optional[int],
            "telegram_chat_id": Optional[int]
        }
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        try:
            telegram_message_id = event.get("telegram_message_id")
            telegram_chat_id = event.get("telegram_chat_id")

            # If telegram IDs are not in the event, try to look up from chat/message
            if not telegram_message_id or not telegram_chat_id:
                message_id = event.get("message_id")
                chat_id = event.get("chat_id")

                # Lookup chat to get telegram_chat_id
                if chat_id and not telegram_chat_id:
                    from app.chat.queries import GetChatByIdQuery
                    chat = await self._query_bus.query(
                        GetChatByIdQuery(
                            chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                        )
                    )
                    if chat:
                        telegram_chat_id = getattr(chat, 'telegram_chat_id', None) or getattr(chat, 'telegram_supergroup_id', None)

                # Without telegram_message_id, we cannot delete the message in Telegram
                if not telegram_message_id:
                    log.debug(
                        f"No telegram_message_id for message {message_id}, cannot sync deletion to Telegram"
                    )
                    return

            if not telegram_chat_id:
                log.debug(f"No telegram_chat_id available, cannot sync deletion to Telegram")
                return

            # Delete message in Telegram
            success = await self._telegram.delete_message(
                chat_id=telegram_chat_id,
                message_id=telegram_message_id
            )

            if success:
                log.info(
                    f"Deleted Telegram message {telegram_message_id} in chat {telegram_chat_id}"
                )
            else:
                log.warning(
                    f"Failed to delete Telegram message {telegram_message_id} in chat {telegram_chat_id}"
                )

        except Exception as e:
            log.error(f"Error handling MessageDeleted event: {e}", exc_info=True)

    async def on_chat_created(self, event: dict) -> None:
        """
        Handle ChatCreated event - optionally create Telegram topic.

        Event payload:
        {
            "chat_id": UUID,
            "chat_name": str,
            "company_id": UUID,
            "create_telegram_topic": bool,
            "telegram_group_id": Optional[int],
            "topic_emoji": Optional[str]
        }
        """
        if not self._initialized or not self._telegram:
            return

        try:
            # Check if we should create a Telegram topic
            if not event.get("create_telegram_topic"):
                return

            telegram_group_id = event.get("telegram_group_id")
            if not telegram_group_id:
                log.warning("No telegram_group_id provided for topic creation")
                return

            chat_name = event.get("chat_name", "New Chat")
            topic_emoji = event.get("topic_emoji")

            # Create topic in Telegram
            topic = await self._telegram.create_chat_topic(
                group_id=telegram_group_id,
                topic_name=chat_name,
                emoji=topic_emoji
            )

            if topic:
                log.info(f"Created Telegram topic {topic.topic_id} for chat {event.get('chat_id')}")

                # TODO: Update chat with external_topic_id via Command Bus
                # command = UpdateChatExternalChannelCommand(
                #     chat_id=event["chat_id"],
                #     external_channel_type="telegram",
                #     external_channel_id=str(telegram_group_id),
                #     external_topic_id=str(topic.topic_id)
                # )
                # await command_bus.dispatch(command)
            else:
                log.error(f"Failed to create Telegram topic for chat {event.get('chat_id')}")

        except Exception as e:
            log.error(f"Error handling ChatCreated event: {e}", exc_info=True)

    async def on_chat_updated(self, event: dict) -> None:
        """
        Handle ChatUpdated event - update Telegram topic if needed.

        Event payload:
        {
            "chat_id": UUID,
            "name": Optional[str],
            "updated_by": UUID
        }
        """
        if not self._initialized or not self._telegram:
            return

        try:
            chat_id = event.get("chat_id")
            new_name = event.get("name")

            if not new_name:
                log.debug(f"ChatUpdated event has no name change, skipping Telegram sync")
                return

            # Fetch chat details to get Telegram integration info
            from app.chat.queries import GetChatByIdQuery
            chat = await self._query_bus.query(
                GetChatByIdQuery(
                    chat_id=UUID(chat_id) if isinstance(chat_id, str) else chat_id
                )
            )

            if not chat:
                log.debug(f"Chat {chat_id} not found")
                return

            # Check if chat has Telegram integration
            telegram_chat_id = getattr(chat, 'telegram_chat_id', None)
            telegram_topic_id = getattr(chat, 'telegram_topic_id', None)

            if not telegram_chat_id or not telegram_topic_id:
                log.debug(f"Chat {chat_id} has no Telegram topic integration")
                return

            # Topic ID 1 (General) cannot be renamed
            if telegram_topic_id == 1:
                log.info("Cannot rename General topic (ID 1), skipping Telegram sync")
                return

            log.info(f"Syncing chat name to Telegram: chat_id={chat_id}, name={new_name}, topic_id={telegram_topic_id}")

            success = await self._telegram.update_chat_topic(
                group_id=telegram_chat_id,
                topic_id=telegram_topic_id,
                new_name=new_name,
                new_emoji=None
            )

            if success:
                log.info(f"Updated Telegram topic {telegram_topic_id} with name '{new_name}'")
            else:
                log.error(f"Failed to update Telegram topic {telegram_topic_id}")

        except Exception as e:
            log.error(f"Error handling ChatUpdated event: {e}", exc_info=True)

    async def on_chat_archived(self, event: dict) -> None:
        """
        Handle ChatArchived event - close/archive Telegram topic.

        Event payload:
        {
            "chat_id": UUID,
            "archived_by": UUID,
            "telegram_supergroup_id": Optional[int],
            "telegram_topic_id": Optional[int]
        }

        Note: Telegram topics cannot be truly deleted, only closed.
        Closing a topic hides it from the topic list but preserves messages.
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping event")
            return

        try:
            telegram_supergroup_id = event.get("telegram_supergroup_id")
            telegram_topic_id = event.get("telegram_topic_id")

            if not telegram_supergroup_id or not telegram_topic_id:
                log.debug(
                    f"Chat {event.get('chat_id')} has no Telegram integration, skipping archive sync"
                )
                return

            # Topic ID 1 (General) cannot be closed
            if telegram_topic_id == 1:
                log.info("Cannot close General topic (ID 1), skipping Telegram sync")
                return

            # Close the topic in Telegram (this hides it from the topic list)
            # Using MTProto client's close_forum_topic if available
            if self._telegram.mtproto_client:
                try:
                    # Try to close the topic (hide from list)
                    success = await self._telegram.mtproto_client.close_forum_topic(
                        group_id=telegram_supergroup_id,
                        topic_id=telegram_topic_id
                    )
                    if success:
                        log.info(
                            f"Closed Telegram topic {telegram_topic_id} in group {telegram_supergroup_id}"
                        )
                    else:
                        log.warning(
                            f"Failed to close Telegram topic {telegram_topic_id}"
                        )
                except AttributeError:
                    # close_forum_topic might not exist yet
                    log.debug("close_forum_topic not available, skipping topic close")
            else:
                log.debug("MTProto client not available for topic close")

        except Exception as e:
            log.error(f"Error handling ChatArchived event: {e}", exc_info=True)

    async def on_chat_deleted(self, event: dict) -> None:
        """
        Handle ChatHardDeleted event - delete Telegram topic.

        Event payload from ChatHardDeleted:
        {
            "chat_id": UUID,
            "deleted_by": UUID,
            "reason": Optional[str],
            "telegram_supergroup_id": Optional[int],
            "telegram_topic_id": Optional[int]
        }

        Note: This actually deletes the topic and its message history.
        """
        if not self._initialized or not self._telegram:
            log.warning("Listener not initialized, skipping chat delete event")
            return

        try:
            telegram_supergroup_id = event.get("telegram_supergroup_id")
            telegram_topic_id = event.get("telegram_topic_id")

            if not telegram_supergroup_id or not telegram_topic_id:
                log.debug(
                    f"Chat {event.get('chat_id')} has no Telegram integration, skipping delete sync"
                )
                return

            # Topic ID 1 (General) cannot be deleted
            if telegram_topic_id == 1:
                log.info("Cannot delete General topic (ID 1), skipping Telegram sync")
                return

            # Delete the topic and its history in Telegram
            if self._telegram.mtproto_client:
                success = await self._telegram.mtproto_client.delete_forum_topic(
                    group_id=telegram_supergroup_id,
                    topic_id=telegram_topic_id
                )

                if success:
                    log.info(
                        f"Deleted Telegram topic {telegram_topic_id} in group {telegram_supergroup_id}"
                    )
                else:
                    log.warning(f"Failed to delete Telegram topic {telegram_topic_id}")
            else:
                log.debug("MTProto client not available for topic deletion")

        except Exception as e:
            log.error(f"Error handling ChatDeleted event: {e}", exc_info=True)


# =============================================================================
# Factory Function for Startup
# =============================================================================

async def create_telegram_event_listener(
    event_bus: Any,
    query_bus: 'QueryBus',
) -> TelegramEventListener:
    """
    Factory function to create and start a TelegramEventListener.

    Usage in startup:
        listener = await create_telegram_event_listener(
            event_bus=app.state.event_bus,
            query_bus=app.state.query_bus
        )
        app.state.telegram_event_listener = listener
    """
    listener = TelegramEventListener(
        event_bus=event_bus,
        query_bus=query_bus
    )
    await listener.start()
    return listener
