# =============================================================================
# File: app/api/routers/telegram_router.py
# Description: FastAPI router for Telegram webhook and group management
# =============================================================================

from __future__ import annotations

import logging
import hmac
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Header

from app.infra.telegram.config import get_telegram_config
from app.infra.telegram.adapter import get_telegram_adapter, TelegramAdapter
from app.api.models.telegram_api_models import (
    WebhookResponse,
    WebhookInfoResponse,
    TelegramUpdateModel,
    CreateGroupRequest,
    CreateGroupResponse,
    GroupInfoResponse,
    CreateTopicRequest,
    CreateTopicResponse,
    UpdateTopicRequest,
    TopicActionRequest,
    TopicsListResponse,
    TopicInfoResponse,
    SendMessageRequest,
    SendMessageResponse,
    AvailableEmojisResponse,
)
from app.chat.commands import ProcessTelegramMessageCommand, CreateChatCommand, AddParticipantCommand
from app.chat.queries import GetChatByTelegramIdQuery
from app.company.queries import GetCompanyByTelegramGroupQuery

log = logging.getLogger("wellwon.telegram.webhook")

router = APIRouter(prefix="/telegram", tags=["telegram"])


def normalize_telegram_chat_id(chat_id: int) -> int:
    """
    Normalize Telegram chat ID to the supergroup ID format stored in database.

    Telegram uses different ID formats:
    - Supergroups: -100{group_id} (e.g., -1003190729022)
    - Groups: negative numbers
    - Users: positive numbers
    - Channels: -100{channel_id}

    Our database stores just the numeric part without -100 prefix for supergroups.

    Examples:
        -1003190729022 -> 3190729022  (supergroup)
        -1234567890 -> -1234567890    (regular group, keep as-is)
        123456789 -> 123456789        (user, keep as-is)
    """
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100") and len(chat_id_str) > 4:
        # It's a supergroup/channel - extract the ID part
        return int(chat_id_str[4:])
    return chat_id


# =============================================================================
# Dependencies
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


async def get_adapter() -> TelegramAdapter:
    """Dependency to get Telegram adapter"""
    return await get_telegram_adapter()


def verify_webhook_secret(
    x_telegram_bot_api_secret_token: Optional[str] = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
) -> bool:
    """
    Verify the webhook secret token from Telegram.

    Telegram sends this header when webhook has secret_token set.
    """
    config = get_telegram_config()

    # If no secret configured, skip verification
    if not config.webhook_secret:
        return True

    # If secret is configured, verify it
    if not x_telegram_bot_api_secret_token:
        return False

    return hmac.compare_digest(
        x_telegram_bot_api_secret_token,
        config.webhook_secret
    )


@router.post("/webhook", response_model=WebhookResponse)
async def telegram_webhook(
    request: Request,
    adapter: TelegramAdapter = Depends(get_adapter),
    command_bus=Depends(get_command_bus),
    query_bus=Depends(get_query_bus),
) -> WebhookResponse:
    """
    Main webhook endpoint for Telegram Bot updates.

    This endpoint receives updates from Telegram when messages are sent to the bot.
    It parses the update and routes it to the appropriate handler.

    Flow:
    1. Receive update from Telegram
    2. Parse and validate update
    3. Process message through adapter
    4. Find WellWon chat by Telegram ID via Query Bus
    5. Dispatch ProcessTelegramMessageCommand via Command Bus
    6. Return success response

    Security:
    - Validates X-Telegram-Bot-Api-Secret-Token header if configured
    """
    # Verify secret token
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not verify_webhook_secret(secret_header):
        log.warning("Invalid webhook secret token received")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        # Parse update data
        update_data = await request.json()
        log.info(f"Received Telegram webhook update: {update_data.get('update_id')}, chat_id: {update_data.get('message', {}).get('chat', {}).get('id')}")

        # Process through adapter
        telegram_message = await adapter.process_webhook_update(update_data)
        log.info(f"Adapter processed message: {telegram_message is not None}")

        if telegram_message:
            log.info(
                f"Processed message from chat {telegram_message.chat_id}, "
                f"topic {telegram_message.topic_id}, "
                f"user {telegram_message.from_username}"
            )

            # Normalize chat ID (convert -100{id} to just {id} for supergroups)
            normalized_chat_id = normalize_telegram_chat_id(telegram_message.chat_id)

            # Check if this is a topic creation event
            is_topic_creation = (
                telegram_message.text and
                telegram_message.text.startswith("__TOPIC_CREATED__:")
            )

            if is_topic_creation:
                # Extract topic name from special marker
                topic_name = telegram_message.text.replace("__TOPIC_CREATED__:", "")
                log.info(f"Processing topic creation: name='{topic_name}', topic_id={telegram_message.topic_id}")

                # Find company by Telegram group ID
                company_query = GetCompanyByTelegramGroupQuery(telegram_group_id=normalized_chat_id)
                company = await query_bus.query(company_query)

                if company:
                    import uuid
                    # Create new chat for this topic
                    # The creator (owner_id) will be automatically added as admin by CreateChatHandler
                    creator_id = company.owner_id or uuid.UUID('00000000-0000-0000-0000-000000000000')
                    create_cmd = CreateChatCommand(
                        chat_id=uuid.uuid4(),
                        name=topic_name,
                        chat_type="company",
                        created_by=creator_id,
                        company_id=company.id,
                        participant_ids=[],  # Creator is added automatically as admin
                        telegram_supergroup_id=normalized_chat_id,
                        telegram_topic_id=telegram_message.topic_id,
                    )
                    await command_bus.send(create_cmd)
                    log.info(f"Created chat '{topic_name}' for topic {telegram_message.topic_id} in company {company.id}, creator={creator_id}")
                else:
                    log.warning(f"No company found for Telegram group {normalized_chat_id}, cannot create topic chat")

                return WebhookResponse(ok=True)

            # Find WellWon chat by Telegram ID via Query Bus
            query = GetChatByTelegramIdQuery(
                telegram_chat_id=normalized_chat_id,
                telegram_topic_id=telegram_message.topic_id,
            )
            chat_detail = await query_bus.query(query)

            if chat_detail:
                # Determine message type
                if telegram_message.file_type == "voice":
                    message_type = "voice"
                elif telegram_message.file_type == "photo":
                    message_type = "image"
                elif telegram_message.file_url or telegram_message.file_id:
                    message_type = "file"
                else:
                    message_type = "text"

                # Dispatch to Chat Domain via Command Bus
                command = ProcessTelegramMessageCommand(
                    chat_id=chat_detail.id,
                    telegram_message_id=telegram_message.message_id,
                    telegram_user_id=telegram_message.from_user_id,
                    sender_id=None,  # TODO: Map telegram user to WellWon user if exists
                    content=telegram_message.text or "",
                    message_type=message_type,
                    file_url=telegram_message.file_url,
                    file_name=telegram_message.file_name,
                    file_size=telegram_message.file_size,
                    file_type=telegram_message.file_type,
                    voice_duration=telegram_message.voice_duration,
                    telegram_topic_id=telegram_message.topic_id,
                    telegram_user_data={
                        "first_name": telegram_message.from_first_name,
                        "last_name": telegram_message.from_last_name,
                        "username": telegram_message.from_username,
                        "is_bot": telegram_message.from_is_bot,
                    },
                )
                await command_bus.send(command)
                log.info(f"Dispatched ProcessTelegramMessageCommand for chat {chat_detail.id}")
            else:
                log.warning(
                    f"No WellWon chat found for Telegram chat_id={telegram_message.chat_id} "
                    f"(normalized: {normalized_chat_id}), topic_id={telegram_message.topic_id}"
                )

        return WebhookResponse(ok=True)

    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}"
        tb = traceback.format_exc()
        log.error(f"Error processing Telegram webhook: {error_detail}\n{tb}")
        # Return ok=True to prevent Telegram from retrying
        # (errors should be handled internally)
        # DEBUG: Include error detail in response for debugging
        return WebhookResponse(ok=True, message=f"Error: {error_detail}")


@router.get("/webhook/info", response_model=WebhookInfoResponse)
async def get_webhook_info(
    adapter: TelegramAdapter = Depends(get_adapter),
) -> WebhookInfoResponse:
    """Get current webhook configuration info"""
    config = get_telegram_config()

    return WebhookInfoResponse(
        webhook_url=config.full_webhook_url or "",
        webhook_configured=bool(config.webhook_url),
        bot_api_available=config.bot_api_available,
        mtproto_available=config.mtproto_available,
    )


@router.post("/webhook/setup")
async def setup_webhook(
    adapter: TelegramAdapter = Depends(get_adapter),
) -> WebhookResponse:
    """Set up webhook with Telegram"""
    success = await adapter.setup_webhook()

    if success:
        return WebhookResponse(ok=True, message="Webhook configured successfully")
    else:
        raise HTTPException(status_code=500, detail="Failed to configure webhook")


@router.post("/webhook/remove")
async def remove_webhook(
    adapter: TelegramAdapter = Depends(get_adapter),
) -> WebhookResponse:
    """Remove webhook from Telegram"""
    success = await adapter.remove_webhook()

    if success:
        return WebhookResponse(ok=True, message="Webhook removed")
    else:
        raise HTTPException(status_code=500, detail="Failed to remove webhook")


# =============================================================================
# Group Management Endpoints (MTProto)
# =============================================================================

@router.post("/group/create", response_model=CreateGroupResponse)
async def create_group(
    req: CreateGroupRequest,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> CreateGroupResponse:
    """
    Create a new Telegram supergroup with forum support.

    This creates a group configured for WellWon:
    - Forum enabled (topics)
    - Bots added as administrators
    - Default permissions set
    """
    result = await adapter.create_company_group(
        company_name=req.title,
        description=req.description or "",
        photo_url=req.photo_url,
        setup_bots=req.setup_bots
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Failed to create group")

    return CreateGroupResponse(
        success=True,
        group_id=result.group_id,
        group_title=result.group_title,
        invite_link=result.invite_link,
        bots_results=result.bots_results,
    )


@router.get("/group/{group_id}", response_model=GroupInfoResponse)
async def get_group_info(
    group_id: int,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> GroupInfoResponse:
    """Get information about a Telegram group"""
    info = await adapter.get_group_info(group_id)

    if not info:
        raise HTTPException(status_code=404, detail="Group not found")

    return GroupInfoResponse(
        success=True,
        group_id=info.group_id,
        title=info.title,
        description=info.description,
        invite_link=info.invite_link,
        members_count=info.members_count,
    )


@router.get("/group/{group_id}/topics", response_model=TopicsListResponse)
async def get_group_topics(
    group_id: int,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> TopicsListResponse:
    """Get all topics in a forum group"""
    topics = await adapter.get_group_topics(group_id)

    return TopicsListResponse(
        success=True,
        topics=[
            TopicInfoResponse(
                topic_id=t.topic_id,
                title=t.title,
                emoji=t.emoji,
                pinned=t.pinned,
            )
            for t in topics
        ]
    )


@router.post("/group/topic/create", response_model=CreateTopicResponse)
async def create_topic(
    req: CreateTopicRequest,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> CreateTopicResponse:
    """Create a new forum topic"""
    topic = await adapter.create_chat_topic(
        group_id=req.group_id,
        topic_name=req.topic_name,
        emoji=req.icon_emoji
    )

    if not topic:
        raise HTTPException(status_code=500, detail="Failed to create topic")

    return CreateTopicResponse(
        success=True,
        topic_id=topic.topic_id,
        title=topic.title,
        emoji=topic.emoji,
    )


@router.put("/group/topic/update")
async def update_topic(
    req: UpdateTopicRequest,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> WebhookResponse:
    """Update a forum topic (name and/or emoji)"""
    success = await adapter.update_chat_topic(
        group_id=req.group_id,
        topic_id=req.topic_id,
        new_name=req.new_name,
        new_emoji=req.new_emoji
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update topic")

    return WebhookResponse(ok=True, message="Topic updated")


@router.delete("/group/topic/delete")
async def delete_topic(
    req: TopicActionRequest,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> WebhookResponse:
    """Delete a forum topic"""
    success = await adapter.delete_chat_topic(req.group_id, req.topic_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete topic")

    return WebhookResponse(ok=True, message="Topic deleted")


# =============================================================================
# Utility Endpoints
# =============================================================================

@router.get("/emojis", response_model=AvailableEmojisResponse)
async def get_available_emojis() -> AvailableEmojisResponse:
    """Get list of available emojis for topics"""
    from app.infra.telegram.mtproto_client import EMOJI_MAP

    return AvailableEmojisResponse(
        emojis=list(EMOJI_MAP.keys()),
        emoji_map=EMOJI_MAP,
    )


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    req: SendMessageRequest,
    adapter: TelegramAdapter = Depends(get_adapter),
) -> SendMessageResponse:
    """
    Send a message to a Telegram chat.

    Primarily for testing and admin use.
    """
    result = await adapter.send_message(
        chat_id=req.chat_id,
        text=req.text,
        topic_id=req.topic_id
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Failed to send message")

    return SendMessageResponse(
        success=True,
        message_id=result.message_id,
    )


# =============================================================================
# Supergroups Endpoints (for Frontend)
# =============================================================================

from typing import List, Annotated
from pydantic import BaseModel
from datetime import datetime
import uuid as uuid_module
from app.security.jwt_auth import get_current_user
from app.infra.read_repos.company_read_repo import CompanyReadRepo


class SupergroupResponse(BaseModel):
    """Telegram supergroup info"""
    id: int
    company_id: Optional[uuid_module.UUID] = None  # FK to companies.id (UUID)
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    member_count: int = 0
    is_forum: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None


class SupergroupWithChatCountResponse(BaseModel):
    """Telegram supergroup with chat count"""
    id: int
    company_id: Optional[uuid_module.UUID] = None  # FK to companies.id (UUID)
    company_name: str = ""
    title: str
    username: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    member_count: int = 0
    is_forum: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    chat_count: int = 0


class VerifyTopicsResponse(BaseModel):
    """Response from topic verification"""
    success: bool
    verified_count: int = 0
    created_count: int = 0
    errors: List[str] = []
    dry_run: bool = False


@router.get("/supergroups", response_model=List[SupergroupResponse])
async def get_all_supergroups(
    current_user: Annotated[dict, Depends(get_current_user)],
    active_only: bool = True,
) -> List[SupergroupResponse]:
    """
    Get all Telegram supergroups.

    Returns list of all supergroups from the database.
    """
    try:
        supergroups = await CompanyReadRepo.get_all_telegram_supergroups(active_only=active_only)

        return [
            SupergroupResponse(
                id=sg.id if hasattr(sg, 'id') else sg.telegram_group_id,
                company_id=sg.company_id,
                title=sg.title,
                username=sg.username,
                description=sg.description,
                invite_link=sg.invite_link,
                member_count=sg.member_count if hasattr(sg, 'member_count') else 0,
                is_forum=sg.is_forum if hasattr(sg, 'is_forum') else False,
                is_active=sg.is_active if hasattr(sg, 'is_active') else True,
                created_at=sg.created_at if hasattr(sg, 'created_at') else None,
            )
            for sg in supergroups
        ]

    except Exception as e:
        log.error(f"Failed to get supergroups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get supergroups")


class UpdateSupergroupRequest(BaseModel):
    """Request to update supergroup"""
    is_active: Optional[bool] = None
    title: Optional[str] = None
    description: Optional[str] = None


@router.patch("/supergroups/{supergroup_id}", response_model=SupergroupResponse)
async def update_supergroup(
    supergroup_id: int,
    request: UpdateSupergroupRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SupergroupResponse:
    """
    Update a Telegram supergroup (archive/unarchive, update title, etc.)
    """
    try:
        # Build update dict with only provided fields
        updates = {}
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        if request.title is not None:
            updates["title"] = request.title
        if request.description is not None:
            updates["description"] = request.description

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updated = await CompanyReadRepo.update_telegram_supergroup(supergroup_id, updates_dict=updates)

        if not updated:
            raise HTTPException(status_code=404, detail="Supergroup not found")

        return SupergroupResponse(
            id=updated.id if hasattr(updated, 'id') else updated.telegram_group_id,
            company_id=updated.company_id,
            title=updated.title,
            username=updated.username,
            description=updated.description,
            invite_link=updated.invite_link,
            member_count=updated.member_count if hasattr(updated, 'member_count') else 0,
            is_forum=updated.is_forum if hasattr(updated, 'is_forum') else False,
            is_active=updated.is_active if hasattr(updated, 'is_active') else True,
            created_at=updated.created_at if hasattr(updated, 'created_at') else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to update supergroup {supergroup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update supergroup")


@router.delete("/supergroups/{supergroup_id}")
async def delete_supergroup(
    supergroup_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    command_bus=Depends(get_command_bus),
    cascade: bool = Query(True, description="If True, trigger GroupDeletionSaga to cascade delete chats/messages/company"),
) -> dict:
    """
    Delete a Telegram supergroup via GroupDeletionSaga (cascade delete).

    If cascade=True (default), triggers GroupDeletionSaga which:
    1. Deletes all chats linked to the company (with messages)
    2. Deletes the Telegram supergroup record
    3. Deletes the company record

    If cascade=False, only deletes the supergroup record (orphans chats/company).

    TRUE SAGA Pattern: RequestCompanyDeletionCommand enriches event with all data,
    saga uses ONLY enriched event data (no queries in saga).
    """
    from app.company.commands import RequestCompanyDeletionCommand, DeleteTelegramSupergroupCommand

    try:
        # Check if supergroup exists and get company_id
        supergroup = await CompanyReadRepo.get_telegram_supergroup(supergroup_id)
        if not supergroup:
            raise HTTPException(status_code=404, detail="Supergroup not found")

        company_id = supergroup.get("company_id")

        if cascade and company_id:
            # TRUE SAGA: Trigger GroupDeletionSaga via company deletion
            # This cascades: chats (with messages) -> telegram -> company
            command = RequestCompanyDeletionCommand(
                company_id=company_id,
                deleted_by=current_user["user_id"],
                cascade=True,
            )
            await command_bus.send(command)

            log.info(f"GroupDeletionSaga triggered for supergroup {supergroup_id} (company {company_id})")
            return {"success": True, "message": "Group deletion saga triggered (cascade delete)"}

        else:
            # No cascade or no company - just delete supergroup record
            command = DeleteTelegramSupergroupCommand(
                telegram_group_id=supergroup_id,
                deleted_by=current_user["user_id"],
                reason="Deleted via admin interface (no cascade)",
            )
            await command_bus.send(command)

            log.info(f"Supergroup {supergroup_id} deleted (no cascade)")
            return {"success": True, "message": "Supergroup deleted (no cascade)"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete supergroup {supergroup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete supergroup")


@router.get("/supergroups/chat-counts", response_model=List[SupergroupWithChatCountResponse])
async def get_supergroup_chat_counts(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> List[SupergroupWithChatCountResponse]:
    """
    Get all Telegram supergroups with their chat counts.

    Returns list of supergroups with the number of active chats in each.
    """
    try:
        results = await CompanyReadRepo.get_telegram_supergroups_with_chat_counts()

        return [
            SupergroupWithChatCountResponse(
                id=row["id"],
                company_id=row.get("company_id"),
                company_name=row.get("company_name", ""),
                title=row["title"],
                username=row.get("username"),
                description=row.get("description"),
                invite_link=row.get("invite_link"),
                member_count=row.get("member_count", 0),
                is_forum=row.get("is_forum", False),
                is_active=row.get("is_active", True),
                created_at=row.get("created_at"),
                chat_count=row.get("chat_count", 0),
            )
            for row in results
        ]

    except Exception as e:
        log.error(f"Failed to get supergroups with chat counts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get supergroups")


# =============================================================================
# Member Management Endpoints
# =============================================================================


class GroupMemberResponse(BaseModel):
    """Telegram group member info"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: bool = False
    status: str = "member"  # creator, administrator, member, restricted, left, kicked


class MembersListResponse(BaseModel):
    """Response with list of group members"""
    success: bool
    members: List[GroupMemberResponse] = []
    total_count: int = 0
    error: Optional[str] = None


class UpdateMemberRoleRequest(BaseModel):
    """Request to update member role"""
    role: str  # administrator, member, restricted


class UpdateMemberRoleResponse(BaseModel):
    """Response for role update"""
    success: bool
    error: Optional[str] = None


@router.get("/groups/{group_id}/members", response_model=MembersListResponse)
async def get_group_members(
    group_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    adapter: TelegramAdapter = Depends(get_adapter),
) -> MembersListResponse:
    """
    Get members of a Telegram group.

    Returns list of members with their roles and status.
    Uses MTProto client for full member list access.
    """
    try:
        members = await adapter.get_group_members(group_id)

        return MembersListResponse(
            success=True,
            members=[
                GroupMemberResponse(
                    user_id=m.user_id,
                    username=m.username,
                    first_name=m.first_name,
                    last_name=m.last_name,
                    is_bot=m.is_bot,
                    status=m.status,
                )
                for m in members
            ],
            total_count=len(members),
        )

    except Exception as e:
        log.error(f"Failed to get members for group {group_id}: {e}", exc_info=True)
        return MembersListResponse(
            success=False,
            members=[],
            total_count=0,
            error=str(e),
        )


@router.patch("/groups/{group_id}/members/{user_id}/role", response_model=UpdateMemberRoleResponse)
async def update_member_role(
    group_id: int,
    user_id: int,
    request: UpdateMemberRoleRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    adapter: TelegramAdapter = Depends(get_adapter),
) -> UpdateMemberRoleResponse:
    """
    Update a member's role in a Telegram group.

    Roles: administrator, member, restricted
    """
    try:
        success = await adapter.update_member_role(group_id, user_id, request.role)

        if success:
            log.info(f"Updated role for user {user_id} in group {group_id} to {request.role}")
            return UpdateMemberRoleResponse(success=True)
        else:
            return UpdateMemberRoleResponse(
                success=False,
                error="Failed to update member role"
            )

    except Exception as e:
        log.error(f"Failed to update role for user {user_id} in group {group_id}: {e}", exc_info=True)
        return UpdateMemberRoleResponse(
            success=False,
            error=str(e),
        )


@router.post("/groups/{group_id}/verify-topics", response_model=VerifyTopicsResponse)
async def verify_group_topics(
    group_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    adapter: TelegramAdapter = Depends(get_adapter),
    dry_run: bool = False,
) -> VerifyTopicsResponse:
    """
    Verify and sync topics for a Telegram supergroup.

    Checks topics in Telegram and syncs them with the database.
    If dry_run=True, only reports what would be done without making changes.
    """
    try:
        # Get group info and topics from Telegram
        topics = await adapter.get_group_topics(group_id)

        if not topics:
            return VerifyTopicsResponse(
                success=True,
                verified_count=0,
                created_count=0,
                errors=[],
                dry_run=dry_run,
            )

        # For now, just return the count of topics found
        # TODO: Implement full sync with database when needed
        return VerifyTopicsResponse(
            success=True,
            verified_count=len(topics),
            created_count=0,
            errors=[],
            dry_run=dry_run,
        )

    except Exception as e:
        log.error(f"Failed to verify topics for group {group_id}: {e}", exc_info=True)
        return VerifyTopicsResponse(
            success=False,
            verified_count=0,
            created_count=0,
            errors=[str(e)],
            dry_run=dry_run,
        )
