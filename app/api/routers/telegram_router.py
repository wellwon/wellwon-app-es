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

log = logging.getLogger("wellwon.telegram.webhook")

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


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
) -> WebhookResponse:
    """
    Main webhook endpoint for Telegram Bot updates.

    This endpoint receives updates from Telegram when messages are sent to the bot.
    It parses the update and routes it to the appropriate handler.

    Flow:
    1. Receive update from Telegram
    2. Parse and validate update
    3. Process message through adapter
    4. (Future) Dispatch command to Chat Domain
    5. Return success response

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
        log.debug(f"Received Telegram update: {update_data.get('update_id')}")

        # Process through adapter
        telegram_message = await adapter.process_webhook_update(update_data)

        if telegram_message:
            log.info(
                f"Processed message from chat {telegram_message.chat_id}, "
                f"topic {telegram_message.topic_id}, "
                f"user {telegram_message.from_username}"
            )

            # TODO: Dispatch to Chat Domain via Command Bus
            # command = ReceiveExternalMessageCommand(
            #     chat_id=find_chat_by_telegram_id(telegram_message.chat_id, telegram_message.topic_id),
            #     external_sender_id=str(telegram_message.from_user_id),
            #     external_sender_name=telegram_message.from_username,
            #     content=telegram_message.text or "",
            #     file_url=telegram_message.file_url,
            #     external_message_id=str(telegram_message.message_id)
            # )
            # await command_bus.dispatch(command)

        return WebhookResponse(ok=True)

    except Exception as e:
        log.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        # Return ok=True to prevent Telegram from retrying
        # (errors should be handled internally)
        return WebhookResponse(ok=True, message="Error logged")


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
