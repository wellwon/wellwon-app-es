# =============================================================================
# File: app/api/routers/chat_router.py
# Description: Chat domain API endpoints
# =============================================================================

from __future__ import annotations

import uuid
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field

from app.security.jwt_auth import get_current_user
from app.chat.commands import (
    CreateChatCommand,
    UpdateChatCommand,
    ArchiveChatCommand,
    AddParticipantCommand,
    RemoveParticipantCommand,
    ChangeParticipantRoleCommand,
    LeaveChatCommand,
    SendMessageCommand,
    EditMessageCommand,
    DeleteMessageCommand,
    MarkMessagesAsReadCommand,
    StartTypingCommand,
    StopTypingCommand,
    LinkTelegramChatCommand,
    UnlinkTelegramChatCommand,
)
from app.chat.queries import (
    GetChatByIdQuery,
    GetChatsByUserQuery,
    GetChatParticipantsQuery,
    GetChatMessagesQuery,
    GetUnreadMessagesCountQuery,
    GetUnreadChatsCountQuery,
    SearchChatsQuery,
    SearchMessagesQuery,
    ChatDetail,
    ChatSummary,
    ParticipantInfo,
    MessageDetail,
)

log = logging.getLogger("wellwon.api.chat")

router = APIRouter(prefix="/chats", tags=["chats"])


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_command_bus(request: Request):
    """Get command bus from application state"""
    if not hasattr(request.app.state, 'command_bus'):
        raise RuntimeError("Command bus not configured")
    return request.app.state.command_bus


async def get_query_bus(request: Request):
    """Get query bus from application state"""
    if not hasattr(request.app.state, 'query_bus'):
        raise RuntimeError("Query bus not configured")
    return request.app.state.query_bus


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateChatRequest(BaseModel):
    """Request to create a new chat"""
    name: Optional[str] = Field(None, max_length=255)
    chat_type: str = Field(default="direct", description="direct, group, or company")
    company_id: Optional[uuid.UUID] = None
    participant_ids: List[uuid.UUID] = Field(default_factory=list)
    telegram_chat_id: Optional[int] = None
    telegram_topic_id: Optional[int] = None


class UpdateChatRequest(BaseModel):
    """Request to update chat details"""
    name: Optional[str] = Field(None, max_length=255)


class AddParticipantRequest(BaseModel):
    """Request to add participant to chat"""
    user_id: uuid.UUID
    role: str = Field(default="member", description="member, admin, or observer")


class ChangeRoleRequest(BaseModel):
    """Request to change participant's role"""
    new_role: str = Field(..., description="member, admin, or observer")


class SendMessageRequest(BaseModel):
    """Request to send a message"""
    content: str = Field(..., max_length=10000)
    message_type: str = Field(default="text")
    reply_to_id: Optional[uuid.UUID] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    voice_duration: Optional[int] = None


class EditMessageRequest(BaseModel):
    """Request to edit a message"""
    content: str = Field(..., max_length=10000)


class MarkAsReadRequest(BaseModel):
    """Request to mark messages as read"""
    last_read_message_id: uuid.UUID


class LinkTelegramRequest(BaseModel):
    """Request to link Telegram chat"""
    telegram_chat_id: int
    telegram_topic_id: Optional[int] = None


class ChatResponse(BaseModel):
    """Generic chat response"""
    id: uuid.UUID
    message: str = "Success"


class MessageResponse(BaseModel):
    """Generic message response"""
    id: uuid.UUID
    status: str = "sent"


class UnreadCountResponse(BaseModel):
    """Unread count response"""
    count: int


# =============================================================================
# Chat Endpoints
# =============================================================================

@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    request: CreateChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Create a new chat"""
    try:
        command = CreateChatCommand(
            chat_id=uuid.uuid4(),
            name=request.name,
            chat_type=request.chat_type,
            created_by=current_user["user_id"],
            company_id=request.company_id,
            participant_ids=request.participant_ids,
            telegram_chat_id=request.telegram_chat_id,
            telegram_topic_id=request.telegram_topic_id,
        )

        chat_id = await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Chat created")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Failed to create chat: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create chat")


@router.get("", response_model=List[ChatSummary])
async def get_my_chats(
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all chats for current user"""
    query = GetChatsByUserQuery(
        user_id=current_user["user_id"],
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    return await query_bus.query(query)


@router.get("/search", response_model=List[ChatSummary])
async def search_chats(
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
):
    """Search chats by name"""
    query = SearchChatsQuery(
        user_id=current_user["user_id"],
        search_term=q,
        limit=limit,
    )

    return await query_bus.query(query)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_chats_count(
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get count of chats with unread messages"""
    query = GetUnreadChatsCountQuery(user_id=current_user["user_id"])
    count = await query_bus.query(query)
    return UnreadCountResponse(count=count)


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get chat details"""
    query = GetChatByIdQuery(chat_id=chat_id)
    chat = await query_bus.query(query)

    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    return chat


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: uuid.UUID,
    request: UpdateChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Update chat details"""
    try:
        command = UpdateChatCommand(
            chat_id=chat_id,
            name=request.name,
            updated_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Chat updated")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chat_id}", response_model=ChatResponse)
async def archive_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Archive (soft delete) a chat"""
    try:
        command = ArchiveChatCommand(
            chat_id=chat_id,
            archived_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Chat archived")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Participant Endpoints
# =============================================================================

@router.get("/{chat_id}/participants", response_model=List[ParticipantInfo])
async def get_chat_participants(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    include_inactive: bool = Query(False),
):
    """Get participants of a chat"""
    query = GetChatParticipantsQuery(
        chat_id=chat_id,
        include_inactive=include_inactive,
    )

    return await query_bus.query(query)


@router.post("/{chat_id}/participants", response_model=ChatResponse)
async def add_participant(
    chat_id: uuid.UUID,
    request: AddParticipantRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Add participant to chat"""
    try:
        command = AddParticipantCommand(
            chat_id=chat_id,
            user_id=request.user_id,
            role=request.role,
            added_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Participant added")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chat_id}/participants/{user_id}", response_model=ChatResponse)
async def remove_participant(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Remove participant from chat"""
    try:
        command = RemoveParticipantCommand(
            chat_id=chat_id,
            user_id=user_id,
            removed_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Participant removed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{chat_id}/participants/{user_id}/role", response_model=ChatResponse)
async def change_participant_role(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    request: ChangeRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Change participant's role"""
    try:
        command = ChangeParticipantRoleCommand(
            chat_id=chat_id,
            user_id=user_id,
            new_role=request.new_role,
            changed_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Role changed")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{chat_id}/leave", response_model=ChatResponse)
async def leave_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Leave a chat"""
    try:
        command = LeaveChatCommand(
            chat_id=chat_id,
            user_id=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Left chat")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Message Endpoints
# =============================================================================

@router.get("/{chat_id}/messages", response_model=List[MessageDetail])
async def get_messages(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    before_id: Optional[uuid.UUID] = Query(None),
    after_id: Optional[uuid.UUID] = Query(None),
):
    """Get messages from a chat"""
    query = GetChatMessagesQuery(
        chat_id=chat_id,
        limit=limit,
        offset=offset,
        before_id=before_id,
        after_id=after_id,
    )

    return await query_bus.query(query)


@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    chat_id: uuid.UUID,
    request: SendMessageRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Send a message to chat"""
    try:
        command = SendMessageCommand(
            message_id=uuid.uuid4(),
            chat_id=chat_id,
            sender_id=current_user["user_id"],
            content=request.content,
            message_type=request.message_type,
            reply_to_id=request.reply_to_id,
            file_url=request.file_url,
            file_name=request.file_name,
            file_size=request.file_size,
            file_type=request.file_type,
            voice_duration=request.voice_duration,
            source="web",
        )

        message_id = await command_bus.dispatch(command)
        return MessageResponse(id=message_id, status="sent")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{chat_id}/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    request: EditMessageRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Edit a message"""
    try:
        command = EditMessageCommand(
            message_id=message_id,
            chat_id=chat_id,
            edited_by=current_user["user_id"],
            new_content=request.content,
        )

        await command_bus.dispatch(command)
        return MessageResponse(id=message_id, status="edited")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chat_id}/messages/{message_id}", response_model=MessageResponse)
async def delete_message(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Delete a message"""
    try:
        command = DeleteMessageCommand(
            message_id=message_id,
            chat_id=chat_id,
            deleted_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return MessageResponse(id=message_id, status="deleted")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}/messages/search", response_model=List[MessageDetail])
async def search_messages(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
):
    """Search messages in chat"""
    query = SearchMessagesQuery(
        chat_id=chat_id,
        search_term=q,
        limit=limit,
    )

    return await query_bus.query(query)


@router.post("/{chat_id}/read", response_model=ChatResponse)
async def mark_messages_as_read(
    chat_id: uuid.UUID,
    request: MarkAsReadRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Mark messages as read"""
    try:
        command = MarkMessagesAsReadCommand(
            chat_id=chat_id,
            user_id=current_user["user_id"],
            last_read_message_id=request.last_read_message_id,
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Messages marked as read")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Get unread messages count in chat"""
    query = GetUnreadMessagesCountQuery(
        chat_id=chat_id,
        user_id=current_user["user_id"],
    )

    result = await query_bus.query(query)
    return UnreadCountResponse(count=result.count)


# =============================================================================
# Typing Indicators
# =============================================================================

@router.post("/{chat_id}/typing/start", status_code=status.HTTP_204_NO_CONTENT)
async def start_typing(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Send typing indicator start"""
    command = StartTypingCommand(
        chat_id=chat_id,
        user_id=current_user["user_id"],
    )

    await command_bus.dispatch(command)


@router.post("/{chat_id}/typing/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_typing(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Send typing indicator stop"""
    command = StopTypingCommand(
        chat_id=chat_id,
        user_id=current_user["user_id"],
    )

    await command_bus.dispatch(command)


# =============================================================================
# Telegram Integration
# =============================================================================

@router.post("/{chat_id}/telegram/link", response_model=ChatResponse)
async def link_telegram_chat(
    chat_id: uuid.UUID,
    request: LinkTelegramRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Link a Telegram chat"""
    try:
        command = LinkTelegramChatCommand(
            chat_id=chat_id,
            telegram_chat_id=request.telegram_chat_id,
            telegram_topic_id=request.telegram_topic_id,
            linked_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Telegram chat linked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chat_id}/telegram/link", response_model=ChatResponse)
async def unlink_telegram_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
):
    """Unlink Telegram chat"""
    try:
        command = UnlinkTelegramChatCommand(
            chat_id=chat_id,
            unlinked_by=current_user["user_id"],
        )

        await command_bus.dispatch(command)
        return ChatResponse(id=chat_id, message="Telegram chat unlinked")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
