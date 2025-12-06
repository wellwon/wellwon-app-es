# =============================================================================
# File: tests/fakes/fake_telegram_adapter.py
# Description: Fake implementation of TelegramMessagingPort for unit testing
# Pattern: Ports & Adapters - Fake/Stub adapter
# =============================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field


@dataclass
class FakeSendMessageResult:
    """Fake SendMessageResult for testing."""
    success: bool = True
    message_id: Optional[int] = None
    error: Optional[str] = None


@dataclass
class FakeTopicInfo:
    """Fake TopicInfo for testing."""
    topic_id: int
    title: str


@dataclass
class FakeMessage:
    """Fake message for testing."""
    message_id: int
    chat_id: int
    text: str
    topic_id: Optional[int] = None


@dataclass
class CallRecord:
    """Record of a method call for verification."""
    method: str
    args: tuple
    kwargs: Dict[str, Any]
    result: Any = None


class FakeTelegramAdapter:
    """
    Fake implementation of TelegramMessagingPort for unit testing.

    This adapter stores data in memory and tracks all method calls
    for verification in tests.

    Usage:
        fake = FakeTelegramAdapter()

        handler = SendMessageHandler(HandlerDependencies(
            telegram_adapter=fake,
            ...
        ))

        await handler.handle(command)

        # Verify calls
        assert fake.was_called("send_message")
        assert fake.get_call_count("send_message") == 1
    """

    def __init__(self):
        # In-memory storage
        self.messages: List[FakeMessage] = []
        self.topics: Dict[str, FakeTopicInfo] = {}  # "group_id:topic_id" -> TopicInfo
        self.read_positions: Dict[str, int] = {}  # "chat_id" -> max_read_id

        # Call tracking
        self._calls: List[CallRecord] = []

        # Configurable responses
        self._should_fail: Dict[str, str] = {}  # method -> error message
        self._custom_responses: Dict[str, Any] = {}  # method -> response

        # Callback handlers (set by domain)
        self._incoming_handler: Optional[Callable] = None
        self._read_status_handler: Optional[Callable] = None
        self._chat_filter: Optional[Callable] = None

        # Auto-increment for message IDs
        self._next_message_id = 1

    # =========================================================================
    # Test Setup Methods
    # =========================================================================

    def set_message(self, message: FakeMessage) -> None:
        """Setup a message for testing."""
        self.messages.append(message)

    def set_topic(self, group_id: int, topic_id: int, title: str) -> None:
        """Setup a topic for testing."""
        key = f"{group_id}:{topic_id}"
        self.topics[key] = FakeTopicInfo(topic_id=topic_id, title=title)

    def configure_failure(self, method: str, error_message: str) -> None:
        """Configure a method to fail with an error."""
        self._should_fail[method] = error_message

    def configure_response(self, method: str, response: Any) -> None:
        """Configure a custom response for a method."""
        self._custom_responses[method] = response

    def clear(self) -> None:
        """Reset all state between tests."""
        self.messages.clear()
        self.topics.clear()
        self.read_positions.clear()
        self._calls.clear()
        self._should_fail.clear()
        self._custom_responses.clear()
        self._next_message_id = 1

    # =========================================================================
    # Test Verification Methods
    # =========================================================================

    def was_called(self, method: str) -> bool:
        """Check if a method was called."""
        return any(c.method == method for c in self._calls)

    def get_call_count(self, method: str) -> int:
        """Get number of times a method was called."""
        return sum(1 for c in self._calls if c.method == method)

    def get_calls(self, method: str) -> List[CallRecord]:
        """Get all calls to a specific method."""
        return [c for c in self._calls if c.method == method]

    def get_last_call(self, method: str) -> Optional[CallRecord]:
        """Get the last call to a specific method."""
        calls = self.get_calls(method)
        return calls[-1] if calls else None

    def get_all_calls(self) -> List[CallRecord]:
        """Get all recorded calls."""
        return self._calls.copy()

    # =========================================================================
    # Test Simulation Methods
    # =========================================================================

    async def simulate_incoming_message(
        self,
        chat_id: int,
        text: str,
        topic_id: Optional[int] = None
    ) -> None:
        """Simulate an incoming message from Telegram for testing event handlers."""
        if self._incoming_handler:
            # Create fake incoming message structure
            from dataclasses import dataclass

            @dataclass
            class FakeIncoming:
                chat_id: int
                text: str
                topic_id: Optional[int]
                message_id: int

            incoming = FakeIncoming(
                chat_id=chat_id,
                text=text,
                topic_id=topic_id,
                message_id=self._next_message_id,
            )
            self._next_message_id += 1
            await self._incoming_handler(incoming)

    async def simulate_read_event(
        self,
        chat_id: int,
        max_id: int,
        topic_id: Optional[int] = None
    ) -> None:
        """Simulate a read event from Telegram for testing read sync."""
        if self._read_status_handler:
            @dataclass
            class FakeReadEvent:
                chat_id: int
                max_id: int
                topic_id: Optional[int]

            event = FakeReadEvent(chat_id=chat_id, max_id=max_id, topic_id=topic_id)
            await self._read_status_handler(event)

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _record_call(self, method: str, *args, **kwargs) -> None:
        """Record a method call."""
        self._calls.append(CallRecord(method=method, args=args, kwargs=kwargs))

    def _check_failure(self, method: str) -> None:
        """Check if method should fail and raise exception."""
        if method in self._should_fail:
            raise Exception(self._should_fail[method])

    def _get_custom_response(self, method: str) -> Optional[Any]:
        """Get custom response if configured."""
        return self._custom_responses.get(method)

    def _create_message_result(self, success: bool = True, error: str = None) -> FakeSendMessageResult:
        """Create a message result."""
        msg_id = self._next_message_id if success else None
        if success:
            self._next_message_id += 1
        return FakeSendMessageResult(success=success, message_id=msg_id, error=error)

    # =========================================================================
    # TelegramMessagingPort Implementation - Message Sending
    # =========================================================================

    async def send_message(
        self,
        chat_id: int,
        text: str,
        topic_id: Optional[int] = None,
        reply_to: Optional[int] = None,
        parse_mode: str = "HTML"
    ) -> FakeSendMessageResult:
        """Send text message."""
        self._record_call("send_message", chat_id, text, topic_id=topic_id, reply_to=reply_to)
        self._check_failure("send_message")

        if custom := self._get_custom_response("send_message"):
            return custom

        result = self._create_message_result()
        if result.success:
            self.messages.append(FakeMessage(
                message_id=result.message_id,
                chat_id=chat_id,
                text=text,
                topic_id=topic_id,
            ))
        return result

    async def send_file(
        self,
        chat_id: int,
        file_url: str,
        file_name: Optional[str] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> FakeSendMessageResult:
        """Send file."""
        self._record_call("send_file", chat_id, file_url, file_name=file_name, caption=caption, topic_id=topic_id)
        self._check_failure("send_file")

        if custom := self._get_custom_response("send_file"):
            return custom

        return self._create_message_result()

    async def send_voice(
        self,
        chat_id: int,
        voice_url: str,
        duration: Optional[int] = None,
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> FakeSendMessageResult:
        """Send voice message."""
        self._record_call("send_voice", chat_id, voice_url, duration=duration, topic_id=topic_id)
        self._check_failure("send_voice")

        if custom := self._get_custom_response("send_voice"):
            return custom

        return self._create_message_result()

    async def send_file_by_id(
        self,
        chat_id: int,
        file_id: str,
        file_type: str = "document",
        caption: Optional[str] = None,
        topic_id: Optional[int] = None
    ) -> FakeSendMessageResult:
        """Send file by ID."""
        self._record_call("send_file_by_id", chat_id, file_id, file_type=file_type, topic_id=topic_id)
        self._check_failure("send_file_by_id")

        if custom := self._get_custom_response("send_file_by_id"):
            return custom

        return self._create_message_result()

    # =========================================================================
    # TelegramMessagingPort Implementation - Edit/Delete
    # =========================================================================

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str
    ) -> FakeSendMessageResult:
        """Edit message."""
        self._record_call("edit_message", chat_id, message_id, text)
        self._check_failure("edit_message")

        if custom := self._get_custom_response("edit_message"):
            return custom

        # Update stored message
        for msg in self.messages:
            if msg.chat_id == chat_id and msg.message_id == message_id:
                msg.text = text
                break

        return FakeSendMessageResult(success=True, message_id=message_id)

    async def delete_message(
        self,
        chat_id: int,
        message_id: int
    ) -> bool:
        """Delete message."""
        self._record_call("delete_message", chat_id, message_id)
        self._check_failure("delete_message")

        if custom := self._get_custom_response("delete_message"):
            return custom

        # Remove from stored messages
        self.messages = [m for m in self.messages if not (m.chat_id == chat_id and m.message_id == message_id)]
        return True

    # =========================================================================
    # TelegramMessagingPort Implementation - Read Status
    # =========================================================================

    async def mark_messages_read(
        self,
        chat_id: int,
        max_id: int = 0
    ) -> bool:
        """Mark messages as read."""
        self._record_call("mark_messages_read", chat_id, max_id)
        self._check_failure("mark_messages_read")

        if custom := self._get_custom_response("mark_messages_read"):
            return custom

        self.read_positions[str(chat_id)] = max_id
        return True

    async def mark_topic_messages_read(
        self,
        group_id: int,
        topic_id: int,
        max_id: int = 0
    ) -> bool:
        """Mark topic messages as read."""
        self._record_call("mark_topic_messages_read", group_id, topic_id, max_id)
        self._check_failure("mark_topic_messages_read")

        if custom := self._get_custom_response("mark_topic_messages_read"):
            return custom

        key = f"{group_id}:{topic_id}"
        self.read_positions[key] = max_id
        return True

    # =========================================================================
    # TelegramMessagingPort Implementation - Files
    # =========================================================================

    async def get_file_url(self, file_id: str) -> Optional[str]:
        """Get file URL."""
        self._record_call("get_file_url", file_id)
        self._check_failure("get_file_url")

        if custom := self._get_custom_response("get_file_url"):
            return custom

        return f"https://fake.telegram.org/file/{file_id}"

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file."""
        self._record_call("download_file", file_id)
        self._check_failure("download_file")

        if custom := self._get_custom_response("download_file"):
            return custom

        return b"fake file content"

    # =========================================================================
    # TelegramMessagingPort Implementation - Topics
    # =========================================================================

    async def create_chat_topic(
        self,
        group_id: int,
        topic_name: str,
        emoji: Optional[str] = None
    ) -> Optional[FakeTopicInfo]:
        """Create topic."""
        self._record_call("create_chat_topic", group_id, topic_name, emoji=emoji)
        self._check_failure("create_chat_topic")

        if custom := self._get_custom_response("create_chat_topic"):
            return custom

        topic_id = len(self.topics) + 1
        topic = FakeTopicInfo(topic_id=topic_id, title=topic_name)
        self.topics[f"{group_id}:{topic_id}"] = topic
        return topic

    async def update_chat_topic(
        self,
        group_id: int,
        topic_id: int,
        new_name: Optional[str] = None,
        new_emoji: Optional[str] = None
    ) -> bool:
        """Update topic."""
        self._record_call("update_chat_topic", group_id, topic_id, new_name=new_name)
        self._check_failure("update_chat_topic")

        if custom := self._get_custom_response("update_chat_topic"):
            return custom

        key = f"{group_id}:{topic_id}"
        if key in self.topics and new_name:
            self.topics[key] = FakeTopicInfo(topic_id=topic_id, title=new_name)
        return True

    async def delete_chat_topic(
        self,
        group_id: int,
        topic_id: int
    ) -> bool:
        """Delete topic."""
        self._record_call("delete_chat_topic", group_id, topic_id)
        self._check_failure("delete_chat_topic")

        if custom := self._get_custom_response("delete_chat_topic"):
            return custom

        key = f"{group_id}:{topic_id}"
        if key in self.topics:
            del self.topics[key]
        return True

    async def close_topic(
        self,
        group_id: int,
        topic_id: int,
        closed: bool = True
    ) -> bool:
        """Close or reopen topic."""
        self._record_call("close_topic", group_id, topic_id, closed=closed)
        self._check_failure("close_topic")

        if custom := self._get_custom_response("close_topic"):
            return custom

        return True

    # =========================================================================
    # TelegramMessagingPort Implementation - Callbacks
    # =========================================================================

    def set_incoming_message_handler(self, handler: Callable) -> None:
        """Set incoming message handler."""
        self._record_call("set_incoming_message_handler", handler)
        self._incoming_handler = handler

    def set_read_status_handler(self, handler: Callable) -> None:
        """Set read status handler."""
        self._record_call("set_read_status_handler", handler)
        self._read_status_handler = handler

    def set_chat_filter(self, filter_callback: Callable) -> None:
        """Set chat filter."""
        self._record_call("set_chat_filter", filter_callback)
        self._chat_filter = filter_callback

    async def notify_chat_linked(
        self,
        chat_id: int,
        topic_id: Optional[int] = None
    ) -> None:
        """Notify chat linked."""
        self._record_call("notify_chat_linked", chat_id, topic_id=topic_id)
        self._check_failure("notify_chat_linked")


# =============================================================================
# EOF
# =============================================================================
