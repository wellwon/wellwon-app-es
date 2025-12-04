# =============================================================================
# File: app/wse/publishers/domain_publisher.py
# Description: WSE Domain Publisher - Forwards domain events to WebSocket clients
# =============================================================================

"""
WSE Domain Publisher

Bridges EventBus (Redpanda domain events) -> PubSubBus (WebSocket clients)

ARCHITECTURE (CQRS/ES Best Practice):
+-------------------------------------------------------------+
| CommandHandler -> Event -> EventStore -> EventBus (Redpanda) |
+---------------------------+---------------------------------+
                            |
             +--------------+--------------+
             |                             |
      Worker Projector              WSE Domain Publisher
      (Updates PostgreSQL)          (Subscribes to EventBus)
             |                             |
       Read Models                  PubSubBus (Redis Pub/Sub)
                                           |
                                    WebSocket Clients

RESPONSIBILITIES:
- Subscribe to domain events from EventBus (Redpanda)
- Transform events to frontend-friendly format
- Publish to PubSubBus for WSE clients (broadcasts to all server instances)
- Route events to correct user topics

DOMAINS SUPPORTED:
- User (user_update events)
- Company (company_update events)
- Chat (chat_update, message events)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from app.infra.event_bus.event_bus import EventBus
from app.wse.core.pubsub_bus import PubSubBus
from app.wse.core.event_mappings import INTERNAL_TO_WS_EVENT_TYPE_MAP

if TYPE_CHECKING:
    from app.infra.read_repos.chat_read_repo import ChatReadRepo

log = logging.getLogger("wellwon.wse.domain_publisher")


class WSEDomainPublisher:
    """
    WSE Domain Publisher - Forwards domain events to WebSocket clients

    Subscribes to domain events from EventBus and publishes them to PubSubBus
    for real-time WebSocket updates to frontend clients.
    """

    def __init__(
        self,
        event_bus: EventBus,
        pubsub_bus: PubSubBus,
        enable_user_events: bool = True,
        enable_company_events: bool = True,
        enable_chat_events: bool = True,
        enable_saga_events: bool = True,
        chat_read_repo: Optional['ChatReadRepo'] = None,
    ):
        """
        Initialize WSE Domain Publisher

        Args:
            event_bus: Backend event bus (Redpanda)
            pubsub_bus: Frontend event bus (Redis Pub/Sub for multi-instance WebSocket coordination)
            enable_user_events: Enable user event forwarding
            enable_company_events: Enable company event forwarding
            enable_chat_events: Enable chat event forwarding
            enable_saga_events: Enable saga completion event forwarding
            chat_read_repo: Chat read repository for querying participants
        """
        self._event_bus = event_bus
        self._pubsub_bus = pubsub_bus
        self._chat_read_repo = chat_read_repo

        # Feature flags
        self._enable_user_events = enable_user_events
        self._enable_company_events = enable_company_events
        self._enable_chat_events = enable_chat_events
        self._enable_saga_events = enable_saga_events

        # Subscription management
        self._subscriptions: Dict[str, str] = {}  # topic -> subscription_id
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Event type mappings
        self._event_type_map = INTERNAL_TO_WS_EVENT_TYPE_MAP

        # Metrics
        self._events_forwarded = 0
        self._events_filtered = 0
        self._forwarding_errors = 0

        log.info(
            "WSE Domain Publisher initialized - "
            f"Users: {enable_user_events}, "
            f"Companies: {enable_company_events}, "
            f"Chats: {enable_chat_events}, "
            f"Sagas: {enable_saga_events}, "
            f"ChatReadRepo: {'enabled' if chat_read_repo else 'disabled'}"
        )

    async def start(self) -> None:
        """Start the WSE Domain Publisher - subscribe to domain events"""
        if self._running:
            log.warning("WSE Domain Publisher already running")
            return

        log.info("Starting WSE Domain Publisher...")
        self._running = True

        try:
            await self._subscribe_all()
            log.info(
                f"WSE Domain Publisher ready - "
                f"{len(self._subscriptions)} subscriptions active"
            )

        except Exception as e:
            log.error(f"Failed to start WSE Domain Publisher: {e}", exc_info=True)
            self._running = False
            raise

    async def _subscribe_all(self) -> None:
        """Subscribe to all configured domain event topics"""
        log.debug(
            f"Subscribing to domain events - "
            f"user={self._enable_user_events}, company={self._enable_company_events}, "
            f"chat={self._enable_chat_events}, saga={self._enable_saga_events}"
        )
        try:
            if self._enable_user_events:
                await self._subscribe_to_user_events()

            if self._enable_company_events:
                await self._subscribe_to_company_events()

            if self._enable_chat_events:
                await self._subscribe_to_chat_events()

            if self._enable_saga_events:
                await self._subscribe_to_saga_events()

            log.debug(f"WSE subscriptions complete - {len(self._subscriptions)} topics")

        except Exception as e:
            log.error(f"Failed to subscribe to event topics: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop the WSE Domain Publisher - unsubscribe from all topics"""
        if not self._running:
            return

        log.info("Stopping WSE Domain Publisher...")

        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                log.warning("WSE task cancellation timed out after 5s")

        self._tasks.clear()
        self._subscriptions.clear()

        log.info(
            f"WSE Domain Publisher stopped - "
            f"Forwarded: {self._events_forwarded}, "
            f"Filtered: {self._events_filtered}, "
            f"Errors: {self._forwarding_errors}"
        )

    async def shutdown(self) -> None:
        """Shutdown the WSE Domain Publisher (alias for stop)"""
        await self.stop()

    # =========================================================================
    # TOPIC SUBSCRIPTIONS
    # =========================================================================

    async def _subscribe_to_user_events(self) -> None:
        """Subscribe to user account domain events"""
        if not self._running:
            log.debug("Skipping user event subscription - service not running")
            return

        topic = "transport.user-account-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_user_event,
                group="wse-domain-publisher",
                consumer=f"wse-publisher-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_company_events(self) -> None:
        """Subscribe to company domain events"""
        if not self._running:
            log.debug("Skipping company event subscription - service not running")
            return

        topic = "transport.company-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_company_event,
                group="wse-domain-publisher",
                consumer=f"wse-publisher-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_chat_events(self) -> None:
        """Subscribe to chat domain events"""
        if not self._running:
            log.debug("Skipping chat event subscription - service not running")
            return

        topic = "transport.chat-events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_chat_event,
                group="wse-domain-publisher",
                consumer=f"wse-publisher-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    async def _subscribe_to_saga_events(self) -> None:
        """Subscribe to saga completion events"""
        if not self._running:
            log.debug("Skipping saga event subscription - service not running")
            return

        topic = "saga.events"

        try:
            await self._event_bus.subscribe(
                channel=topic,
                handler=self._handle_saga_event,
                group="wse-domain-publisher",
                consumer=f"wse-publisher-{os.getpid()}",
            )
            self._subscriptions[topic] = f"{topic}::wse-domain-publisher"
            log.info(f"Subscribed to {topic} for WSE forwarding")
        except Exception as e:
            log.error(f"Failed to subscribe to {topic}: {e}")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def _handle_user_event(self, event: Dict[str, Any]) -> None:
        """Handle user account domain event"""
        try:
            event_type = event.get("event_type")
            user_id = event.get("user_id") or event.get("aggregate_id")

            if not event_type or not user_id:
                log.warning(f"User event missing event_type or user_id: {event}")
                return

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for event type: {event_type}")
                return

            # Transform to WebSocket format
            # NOTE: Use original event_type for transformer, not ws_event_type
            # The EventTransformer does the mapping again, so we keep the original
            transformed_data = self._transform_user_event(event)
            wse_event = {
                "event_type": event_type,  # Original event type for transformer to map
                "user_id": str(user_id),
                **transformed_data,  # Spread data at root level, not nested in 'data'
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to user-specific events topic
            topic = f"user:{user_id}:events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} -> {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling user event: {e}", exc_info=True)

    async def _handle_company_event(self, event: Dict[str, Any]) -> None:
        """Handle company domain event"""
        try:
            event_type = event.get("event_type")
            company_id = event.get("company_id") or event.get("aggregate_id")

            if not event_type or not company_id:
                log.warning(f"Company event missing event_type or company_id: {event}")
                return

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for company event type: {event_type}")
                return

            # Transform to WebSocket format
            # NOTE: Use original event_type for transformer, not ws_event_type
            # The EventTransformer does the mapping again, so we keep the original
            transformed_data = self._transform_company_event(event)
            wse_event = {
                "event_type": event_type,  # Original event type for transformer to map
                "company_id": str(company_id),
                **transformed_data,  # Spread data at root level, not nested in 'data'
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to company-specific events topic
            topic = f"company:{company_id}:events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            # Also publish user-specific events for membership changes
            user_id = event.get("user_id")
            if user_id and event_type in ("UserAddedToCompany", "UserRemovedFromCompany", "UserCompanyRoleChanged"):
                user_topic = f"user:{user_id}:events"
                await self._pubsub_bus.publish(
                    topic=user_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to user topic {user_topic}")

            # For company creation, notify the creator so their UI updates
            created_by = event.get("created_by")
            if created_by and event_type in ("CompanyCreated", "TelegramSupergroupCreated"):
                creator_topic = f"user:{created_by}:events"
                await self._pubsub_bus.publish(
                    topic=creator_topic,
                    event=wse_event,
                )
                log.debug(f"Forwarded {event_type} to creator topic {creator_topic}")

            # For company deletion, notify the user who deleted so their UI updates
            deleted_by = event.get("deleted_by")
            if deleted_by and event_type == "CompanyDeleted":
                deleter_topic = f"user:{deleted_by}:events"
                await self._pubsub_bus.publish(
                    topic=deleter_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to deleter topic {deleter_topic}")

            self._events_forwarded += 1
            log.debug(f"Forwarded {event_type} -> {ws_event_type} to {topic}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling company event: {e}", exc_info=True)

    async def _handle_chat_event(self, event: Dict[str, Any]) -> None:
        """Handle chat domain event"""
        try:
            import time
            t_start = time.perf_counter()
            event_type = event.get("event_type")
            chat_id = event.get("chat_id") or event.get("aggregate_id")
            log.info(f"[LATENCY] WSE received {event_type} for chat {chat_id}")

            if not event_type or not chat_id:
                log.warning(f"Chat event missing event_type or chat_id: {event}")
                return

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for chat event type: {event_type}")
                return

            # Transform to WebSocket format
            # NOTE: Use original event_type for transformer, not ws_event_type
            # The EventTransformer does the mapping again, so we keep the original
            transformed_data = self._transform_chat_event(event)
            wse_event = {
                "event_type": event_type,  # Original event type for transformer to map
                "chat_id": str(chat_id),
                **transformed_data,  # Spread data at root level, not nested in 'data'
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "event_id": event.get("event_id"),
            }

            # Publish to chat-specific events topic
            topic = f"chat:{chat_id}:events"
            await self._pubsub_bus.publish(
                topic=topic,
                event=wse_event,
            )

            # For message events, publish to ALL participant user topics
            # This enables real-time message delivery to all chat members
            if event_type in ("MessageSent", "TelegramMessageReceived", "MessageEdited", "MessageDeleted", "MessagesMarkedAsRead", "MessageSyncedToTelegram", "MessagesReadOnTelegram"):
                # Get participant_ids from event (MessageSent includes them to avoid read model race condition)
                participant_ids = event.get("participant_ids")
                # Convert UUID objects to strings if needed
                if participant_ids:
                    participant_ids = [str(pid) for pid in participant_ids]
                await self._publish_to_chat_participants(chat_id, wse_event, event_type, participant_ids)

            # Also publish user-specific events for chat membership changes
            # This ensures users get notified when added/removed from chats
            user_id = event.get("user_id")
            if user_id and event_type in ("ChatCreated", "ParticipantAdded", "ParticipantRemoved", "ChatArchived"):
                user_topic = f"user:{user_id}:events"
                await self._pubsub_bus.publish(
                    topic=user_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to user topic {user_topic}")

            # For chat creation by a user, also notify that user
            created_by = event.get("created_by")
            if created_by and event_type == "ChatCreated" and created_by != user_id:
                creator_topic = f"user:{created_by}:events"
                await self._pubsub_bus.publish(
                    topic=creator_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to creator topic {creator_topic}")

            # For Telegram linking, notify the user who linked so their UI updates
            # This is critical for saga - chat is created first, then linked to Telegram
            # Frontend needs to know about the link to show chat in correct supergroup
            linked_by = event.get("linked_by")
            if linked_by and event_type == "TelegramChatLinked":
                linker_topic = f"user:{linked_by}:events"
                await self._pubsub_bus.publish(
                    topic=linker_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to linker topic {linker_topic}")

            self._events_forwarded += 1
            t_end = time.perf_counter()
            log.info(f"[LATENCY] Forwarded {event_type} to WSE PubSub in {(t_end-t_start)*1000:.0f}ms")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling chat event: {e}", exc_info=True)

    async def _handle_saga_event(self, event: Dict[str, Any]) -> None:
        """
        Handle saga completion events.

        Saga completion events are published to the user who initiated the saga,
        so they can update their UI accordingly (e.g., show success/failure).
        """
        try:
            event_type = event.get("event_type")

            if not event_type:
                log.warning(f"Saga event missing event_type: {event}")
                return

            # Map to WebSocket event type
            ws_event_type = self._event_type_map.get(event_type)
            if not ws_event_type:
                self._events_filtered += 1
                log.debug(f"No WSE mapping for saga event type: {event_type}")
                return

            # Extract IDs from saga event
            company_id = event.get("company_id")
            chat_id = event.get("chat_id")
            created_by = event.get("created_by")
            deleted_by = event.get("deleted_by")

            # Transform to WebSocket format
            wse_event = {
                "event_type": event_type,
                "saga_id": event.get("saga_id"),
                "company_id": company_id,
                "company_name": event.get("company_name"),
                "chat_id": chat_id,
                "telegram_group_id": event.get("telegram_group_id"),
                "telegram_invite_link": event.get("telegram_invite_link"),
                "chats_deleted": event.get("chats_deleted"),
                "messages_deleted": event.get("messages_deleted"),
                "telegram_group_deleted": event.get("telegram_group_deleted"),
                "created_by": created_by,
                "deleted_by": deleted_by,
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
            }

            # Publish to the user who initiated the saga
            user_id = created_by or deleted_by
            if user_id:
                user_topic = f"user:{user_id}:events"
                await self._pubsub_bus.publish(
                    topic=user_topic,
                    event=wse_event,
                )
                log.debug(f"Forwarded {event_type} to user topic {user_topic}")

            # Also publish to company topic for other subscribers
            if company_id:
                company_topic = f"company:{company_id}:events"
                await self._pubsub_bus.publish(
                    topic=company_topic,
                    event=wse_event,
                )
                log.debug(f"Also forwarded {event_type} to company topic {company_topic}")

            self._events_forwarded += 1
            log.info(f"Forwarded saga event {event_type} -> {ws_event_type}")

        except Exception as e:
            self._forwarding_errors += 1
            log.error(f"Error handling saga event: {e}", exc_info=True)

    async def _publish_to_chat_participants(
        self,
        chat_id: str,
        wse_event: Dict[str, Any],
        event_type: str,
        participant_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Publish event to all chat participants' user topics.

        This enables real-time message delivery to all users who are
        members of the chat, regardless of which chat they're currently viewing.

        Args:
            chat_id: The chat ID
            wse_event: The event to publish
            event_type: Event type for logging
            participant_ids: Pre-computed participant IDs from event (avoids read model query)
        """
        try:
            # Use participant_ids from event if available (solves eventual consistency issue)
            if participant_ids:
                for user_id in participant_ids:
                    user_topic = f"user:{user_id}:events"
                    await self._pubsub_bus.publish(
                        topic=user_topic,
                        event=wse_event,
                    )
                log.debug(f"Published {event_type} to {len(participant_ids)} participant user topics (from event)")
                return

            # Fallback: query read model (may have race condition for new chats)
            if not self._chat_read_repo:
                log.debug(f"ChatReadRepo not available, skipping participant broadcast for {event_type}")
                return

            import uuid
            chat_uuid = uuid.UUID(str(chat_id))
            participants = await self._chat_read_repo.get_chat_participants(chat_uuid)

            if not participants:
                log.debug(f"No participants found for chat {chat_id}")
                return

            # Publish to each participant's user topic
            for participant in participants:
                if participant.user_id:
                    user_topic = f"user:{participant.user_id}:events"
                    await self._pubsub_bus.publish(
                        topic=user_topic,
                        event=wse_event,
                    )

            log.debug(f"Published {event_type} to {len(participants)} participant user topics (from read model)")

        except Exception as e:
            log.error(f"Error publishing to chat participants: {e}", exc_info=True)

    # =========================================================================
    # EVENT TRANSFORMERS
    # =========================================================================

    def _transform_user_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform user event to WSE format.

        Handles both:
        - Regular domain events (fields at root level)
        - CES events (fields in current_state from PostgreSQL trigger)
        """
        # CES events have current_state with admin fields
        current_state = event.get("current_state", {})

        # For CES events, prefer current_state values; for regular events, use root level
        return {
            "user_id": event.get("aggregate_id") or event.get("user_id"),
            "admin_user_id": event.get("admin_user_id"),  # Who made the change (admin panel)
            "email": event.get("email"),
            "first_name": event.get("first_name"),
            "last_name": event.get("last_name"),
            "company_name": event.get("company_name"),
            "role": current_state.get("role") or event.get("role"),
            "phone": event.get("phone"),
            "avatar_url": event.get("avatar_url"),
            "bio": event.get("bio"),
            "user_type": current_state.get("user_type") or event.get("user_type"),
            "is_developer": current_state.get("is_developer") if "is_developer" in current_state else event.get("is_developer"),
            "timezone": event.get("timezone"),
            "language": event.get("language"),
            "is_active": current_state.get("is_active") if "is_active" in current_state else event.get("is_active", True),
            "email_verified": current_state.get("email_verified") if "email_verified" in current_state else event.get("email_verified", False),
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
            "metadata": event.get("metadata", {}),
            # CES-specific fields for frontend
            "changed_fields": event.get("changed_fields"),
            "detected_by": event.get("detected_by"),
            "compensating_event": event.get("compensating_event", False),
        }

    def _transform_company_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform company event to WSE format."""
        return {
            "company_id": event.get("aggregate_id") or event.get("company_id"),
            "name": event.get("name"),
            "company_type": event.get("company_type"),
            "vat": event.get("vat"),
            "city": event.get("city"),
            "is_active": event.get("is_active", True),
            # User-related fields for membership events
            "user_id": event.get("user_id"),
            "relationship_type": event.get("relationship_type"),
            "added_by": event.get("added_by"),
            "removed_by": event.get("removed_by"),
            "changed_by": event.get("changed_by"),
            # Telegram fields
            "telegram_group_id": event.get("telegram_group_id"),
            "telegram_title": event.get("title"),
            "invite_link": event.get("invite_link"),
            # Balance fields
            "balance": event.get("new_balance"),
            "change_amount": event.get("change_amount"),
            "reason": event.get("reason"),
            # Timestamps
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
        }

    def _transform_chat_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform chat event to WSE format with full Telegram support."""
        # Extract telegram_user_data for external senders
        telegram_user_data = event.get("telegram_user_data") or {}

        # Build sender display name for Telegram users without WellWon account
        sender_id = event.get("sender_id")
        sender_name = event.get("sender_name")
        if not sender_id and not sender_name and telegram_user_data:
            # External Telegram user - build name from telegram_user_data
            first = telegram_user_data.get("first_name", "")
            last = telegram_user_data.get("last_name", "")
            username = telegram_user_data.get("username", "")
            sender_name = f"{first} {last}".strip() or (f"@{username}" if username else "Telegram User")

        # Convert participant_ids to strings if present
        participant_ids = event.get("participant_ids")
        if participant_ids:
            participant_ids = [str(pid) for pid in participant_ids]

        return {
            "chat_id": event.get("aggregate_id") or event.get("chat_id"),
            "name": event.get("name"),
            "chat_type": event.get("chat_type"),
            "is_active": event.get("is_active", True),
            # Message fields
            "message_id": event.get("message_id"),
            "content": event.get("content"),
            "message_type": event.get("message_type"),
            "sender_id": sender_id,
            "sender_name": sender_name,
            "reply_to_id": event.get("reply_to_id"),
            "file_url": event.get("file_url"),
            "file_name": event.get("file_name"),
            "file_size": event.get("file_size"),
            "file_type": event.get("file_type"),
            "voice_duration": event.get("voice_duration"),
            "source": event.get("source", "web"),
            # Participant fields
            "user_id": event.get("user_id"),
            "participant_role": event.get("role"),
            "participant_ids": participant_ids,  # For real-time routing
            # Typing fields
            "typing_user_id": event.get("typing_user_id"),
            "typing_user_name": event.get("typing_user_name"),
            # Read status (MessagesMarkedAsRead event fields)
            "read_message_ids": event.get("message_ids"),
            "read_by": event.get("read_by"),
            "last_read_message_id": event.get("last_read_message_id"),
            "read_at": event.get("read_at"),
            "read_count": event.get("read_count"),
            # Telegram integration (full support)
            "telegram_chat_id": event.get("telegram_chat_id"),
            "telegram_topic_id": event.get("telegram_topic_id"),
            "telegram_message_id": event.get("telegram_message_id"),
            "telegram_user_id": event.get("telegram_user_id"),
            "telegram_user_data": telegram_user_data if telegram_user_data else None,
            "telegram_read_at": event.get("telegram_read_at"),  # Blue checkmarks from Telegram
            "last_read_telegram_message_id": event.get("last_read_telegram_message_id"),
            # Company/Telegram linking
            "company_id": event.get("company_id"),
            "telegram_supergroup_id": event.get("telegram_supergroup_id"),
            "created_by": event.get("created_by"),
            "linked_by": event.get("linked_by"),
            # Timestamps
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
        }

    # =========================================================================
    # METRICS & STATUS
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return {
            "running": self._running,
            "subscriptions": len(self._subscriptions),
            "events_forwarded": self._events_forwarded,
            "events_filtered": self._events_filtered,
            "forwarding_errors": self._forwarding_errors,
            "enabled_domains": {
                "users": self._enable_user_events,
                "companies": self._enable_company_events,
                "chats": self._enable_chat_events,
                "sagas": self._enable_saga_events,
            }
        }


# =============================================================================
# EOF
# =============================================================================
