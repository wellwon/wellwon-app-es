# main.py - ФИНАЛЬНАЯ ВЕРСИЯ с полной поддержкой эмодзи

import os
import glob
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    InviteToChannelRequest,
    EditAdminRequest,
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.types import ChatAdminRights, ChatBannedRights
from dotenv import load_dotenv
import asyncio

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
SESSION_STRING = os.getenv("SESSION_STRING")

if not (API_ID and API_HASH and PHONE):
    raise RuntimeError("Не найдены API_ID, API_HASH или PHONE в окружении")

API_ID = int(API_ID)

# Создаем клиент с StringSession если есть, иначе обычный
if SESSION_STRING:
    print("🔑 Используем готовый session string")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    print("⚠️ SESSION_STRING не найден, создаем новый session")
    client = TelegramClient("main_session", API_ID, API_HASH)

BOTS_CONFIG = [
    {
        "username": "WellWonAssist_bot",
        "title": "Assistant",
        "rights": {
            "change_info": True,
            "delete_messages": True,
            "ban_users": True,
            "invite_users": True,
            "pin_messages": True,
            "manage_topics": True,
            "manage_call": True,
            "other": True,
            "post_stories": True,
            "edit_stories": True,
            "delete_stories": True,
            "add_admins": False,
            "anonymous": False
        }
    },
    {
        "username": "wellwon_app_bot",
        "title": "Manager",
        "rights": {
            "change_info": True,
            "delete_messages": True,
            "ban_users": True,
            "invite_users": True,
            "pin_messages": True,
            "manage_topics": True,
            "manage_call": True,
            "other": True,
            "post_stories": True,
            "edit_stories": True,
            "delete_stories": True,
            "add_admins": False,
            "anonymous": False
        }
    }
]


# Мапинг эмодзи для топиков
def get_emoji_id(emoji_char: str) -> Optional[int]:
    """Получает ID эмодзи по символу"""
    emoji_map = {
        # Основные эмодзи для организации
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

        # Статусы и состояния
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
    return emoji_map.get(emoji_char, None)


async def find_group_by_title(title: str):
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        if getattr(ent, "megagroup", False) and getattr(ent, "title", "") == title:
            return ent
    return None


async def create_group_telegram(title: str, description: str = ""):
    group = await find_group_by_title(title)
    if group:
        return group
    try:
        result = await client(CreateChannelRequest(
            title=title,
            about=description,
            megagroup=True,
            forum=True
        ))
        return result.chats[0]
    except Exception as e:
        print(f"Ошибка при создании супергруппы: {e!r}")
        return None


async def set_group_photo(group_ent, photo_url: str):
    try:
        import aiohttp
        import tempfile
        from telethon.tl.functions.channels import EditPhotoRequest

        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as response:
                if response.status != 200:
                    return False
                content = await response.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            uploaded_file = await client.upload_file(tmp_file_path)
            await client(EditPhotoRequest(channel=group_ent, photo=uploaded_file))
            return True
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        print(f"Ошибка установки фото: {e!r}")
        return False


async def rename_general_topic(group_ent):
    try:
        from telethon.tl.functions.channels import EditForumTopicRequest
        await client(EditForumTopicRequest(
            channel=group_ent,
            topic_id=1,
            title="Общие вопросы и заявки"
        ))
        return True
    except Exception as e:
        print(f"Ошибка переименования топика: {e!r}")
        return False


async def pin_general_topic(group_ent):
    try:
        from telethon.tl.functions.channels import UpdatePinnedForumTopicRequest
        await client(UpdatePinnedForumTopicRequest(
            channel=group_ent,
            topic_id=1,
            pinned=True
        ))
        return True
    except Exception as e:
        print(f"Ошибка закрепления топика: {e!r}")
        return False


async def set_group_permissions(group_ent):
    try:
        from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
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
            change_info=True,
            invite_users=False,
            pin_messages=True,
            manage_topics=False
        )
        await client(EditChatDefaultBannedRightsRequest(
            peer=group_ent,
            banned_rights=banned_rights
        ))
        return True
    except Exception as e:
        print(f"Ошибка установки разрешений: {e!r}")
        return False


async def add_bots_to_group(group_ent):
    results = []
    for bot_config in BOTS_CONFIG:
        try:
            ru = await client(ResolveUsernameRequest(bot_config["username"]))
            bot_user = ru.users[0]

            await client(InviteToChannelRequest(
                channel=group_ent.id,
                users=[bot_user.id]
            ))

            await asyncio.sleep(1)

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

            await client(EditAdminRequest(
                channel=group_ent.id,
                user_id=bot_user.id,
                admin_rights=rights,
                rank=bot_config["title"]
            ))

            results.append({
                "username": bot_config["username"],
                "title": bot_config["title"],
                "status": "success"
            })

        except Exception as e:
            results.append({
                "username": bot_config["username"],
                "title": bot_config.get("title", "Unknown"),
                "status": "error",
                "reason": str(e)
            })

    return results


async def get_invite_link(group_ent):
    try:
        inv = await client(ExportChatInviteRequest(group_ent.id))
        return inv.link
    except Exception as e:
        print(f"Ошибка получения ссылки: {e!r}")
        return None


async def update_group_title(group_id: int, new_title: str):
    try:
        from telethon.tl.functions.channels import EditTitleRequest
        group = await client.get_entity(group_id)
        await client(EditTitleRequest(channel=group, title=new_title))
        return True
    except Exception as e:
        return False


async def update_group_description(group_id: int, new_description: str):
    try:
        from telethon.tl.functions.channels import EditAboutRequest
        group = await client.get_entity(group_id)
        await client(EditAboutRequest(channel=group, about=new_description))
        return True
    except Exception as e:
        return False


# ОБНОВЛЕННЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ЭМОДЗИ В ТОПИКАХ

async def create_forum_topic_with_emoji(group_id: int, topic_name: str, icon_emoji: str = None):
    """Создает новый топик в форуме с эмодзи"""
    try:
        from telethon.tl.functions.channels import CreateForumTopicRequest

        group = await client.get_entity(group_id)

        # Получаем ID эмодзи если передан символ
        icon_emoji_id = None
        if icon_emoji:
            icon_emoji_id = get_emoji_id(icon_emoji)
            print(f"Эмодзи '{icon_emoji}' -> ID: {icon_emoji_id}")

        result = await client(CreateForumTopicRequest(
            channel=group,
            title=topic_name,
            icon_emoji_id=icon_emoji_id,
            send_as=None,
            random_id=None
        ))

        topic_id = result.updates[0].message.id if result.updates else None
        print(f"Топик '{topic_name}' создан с ID: {topic_id} и эмодзи: {icon_emoji}")

        return {
            "topic_id": topic_id,
            "name": topic_name,
            "emoji": icon_emoji,
            "emoji_id": icon_emoji_id
        }

    except Exception as e:
        print(f"Ошибка при создании топика с эмодзи: {e!r}")
        return None


async def update_forum_topic(group_id: int, topic_id: int, new_name: str = None, new_emoji: str = None):
    """Обновляет название и/или эмодзи топика"""
    try:
        from telethon.tl.functions.channels import EditForumTopicRequest

        group = await client.get_entity(group_id)

        # Получаем ID эмодзи если передан новый символ
        icon_emoji_id = None
        if new_emoji:
            icon_emoji_id = get_emoji_id(new_emoji)
            print(f"Новый эмодзи '{new_emoji}' -> ID: {icon_emoji_id}")

        # Обновляем топик
        await client(EditForumTopicRequest(
            channel=group,
            topic_id=topic_id,
            title=new_name,
            icon_emoji_id=icon_emoji_id
        ))

        updated_fields = []
        if new_name:
            updated_fields.append("название")
        if new_emoji:
            updated_fields.append("эмодзи")

        print(f"Топик {topic_id} обновлен: {', '.join(updated_fields)}")
        return True

    except Exception as e:
        print(f"Ошибка при обновлении топика: {e!r}")
        return False


async def get_forum_topics_list(group_id: int):
    """Получает список всех топиков форума с информацией"""
    try:
        from telethon.tl.functions.channels import GetForumTopicsRequest

        group = await client.get_entity(group_id)

        result = await client(GetForumTopicsRequest(
            channel=group,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=100
        ))

        topics = []
        for message in result.messages:
            if hasattr(message, 'action'):
                action = message.action
                if hasattr(action, 'title'):
                    topic_info = {
                        "topic_id": message.id,
                        "title": action.title,
                        "created_date": message.date.isoformat(),
                        "pinned": getattr(message, 'pinned', False)
                    }

                    if hasattr(action, 'icon_emoji_id') and action.icon_emoji_id:
                        topic_info["emoji_id"] = action.icon_emoji_id

                    topics.append(topic_info)

        return topics

    except Exception as e:
        print(f"Ошибка при получении топиков: {e!r}")
        return []


async def delete_forum_topic(group_id: int, topic_id: int):
    try:
        from telethon.tl.functions.channels import DeleteTopicHistoryRequest
        group = await client.get_entity(group_id)
        await client(DeleteTopicHistoryRequest(channel=group, top_msg_id=topic_id))
        return True
    except Exception as e:
        return False


async def invite_user_to_group(group_id: int, username: str):
    try:
        group = await client.get_entity(group_id)
        user = await client.get_entity(username)
        await client(InviteToChannelRequest(channel=group, users=[user]))
        return True
    except Exception as e:
        return False


async def remove_user_from_group(group_id: int, username: str):
    try:
        from telethon.tl.functions.channels import EditBannedRequest
        group = await client.get_entity(group_id)
        user = await client.get_entity(username)
        await client(EditBannedRequest(
            channel=group,
            participant=user,
            banned_rights=ChatBannedRights(until_date=None, view_messages=True)
        ))
        return True
    except Exception as e:
        return False


# ОБНОВЛЕННЫЕ PYDANTIC МОДЕЛИ

class CreateGroupRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    photo_url: Optional[str] = None


class CreateGroupResponse(BaseModel):
    success: bool
    group_id: Optional[int] = None
    group_title: Optional[str] = None
    invite_link: Optional[str] = None
    bots_results: Optional[List[dict]] = []
    permissions_set: Optional[bool] = False
    topic_renamed: Optional[bool] = False
    topic_pinned: Optional[bool] = False
    photo_set: Optional[bool] = False
    error: Optional[str] = None


class UpdateGroupRequest(BaseModel):
    group_id: int
    title: Optional[str] = None
    description: Optional[str] = None


class CreateTopicRequest(BaseModel):
    """Запрос на создание топика с эмодзи"""
    group_id: int
    topic_name: str
    icon_emoji: Optional[str] = None


class UpdateTopicRequest(BaseModel):
    """Запрос на обновление топика (название и/или эмодзи)"""
    group_id: int
    topic_id: int
    new_name: Optional[str] = None
    new_emoji: Optional[str] = None


class TopicActionRequest(BaseModel):
    """Запрос для действий с топиком (удаление)"""
    group_id: int
    topic_id: int


class UserActionRequest(BaseModel):
    group_id: int
    username: str


class StandardResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None
    error: Optional[str] = None


# FASTAPI ПРИЛОЖЕНИЕ

app = FastAPI(title="Telegram Group Manager with Emoji Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        if not SESSION_STRING:
            patterns = ["*.session", "session_*", "*session*"]
            for pattern in patterns:
                for file_path in glob.glob(pattern):
                    try:
                        os.remove(file_path)
                    except:
                        pass

        await client.start(phone=PHONE)
        me = await client.get_me()
        print(f"✅ Авторизован: {me.first_name}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise e


@app.on_event("shutdown")
async def shutdown_event():
    await client.disconnect()


@app.get("/")
async def root():
    return {"message": "Telegram Group Manager API with Emoji Support", "status": "running"}


@app.post("/create_group", response_model=CreateGroupResponse)
async def create_group_endpoint(req: CreateGroupRequest):
    """Создание Telegram супергруппы с настройкой ботов и разрешений"""
    try:
        group = await create_group_telegram(req.title, req.description)
        if not group:
            return CreateGroupResponse(success=False, error="Не удалось создать группу")

        permissions_set = await set_group_permissions(group)
        topic_renamed = await rename_general_topic(group)
        topic_pinned = await pin_general_topic(group)
        bots_results = await add_bots_to_group(group)

        photo_set = False
        if req.photo_url:
            await asyncio.sleep(2)
            photo_set = await set_group_photo(group, req.photo_url)

        invite_link = await get_invite_link(group)

        return CreateGroupResponse(
            success=True,
            group_id=group.id,
            group_title=group.title,
            invite_link=invite_link,
            bots_results=bots_results,
            permissions_set=permissions_set,
            topic_renamed=topic_renamed,
            topic_pinned=topic_pinned,
            photo_set=photo_set
        )

    except Exception as e:
        return CreateGroupResponse(success=False, error=str(e))


@app.get("/group/{group_id}")
async def get_group_info(group_id: int):
    """Получение информации о группе"""
    try:
        group = await client.get_entity(group_id)
        invite_link = await get_invite_link(group)
        return {
            "success": True,
            "group_id": group.id,
            "title": group.title,
            "description": getattr(group, 'about', ''),
            "invite_link": invite_link,
            "members_count": getattr(group, 'participants_count', 0)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/group/{group_id}/topics", response_model=StandardResponse)
async def get_topics_list(group_id: int):
    """Получение списка всех топиков группы"""
    try:
        topics = await get_forum_topics_list(group_id)
        return StandardResponse(
            success=True,
            message=f"Найдено {len(topics)} топиков",
            data={"topics": topics}
        )
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.put("/group/update", response_model=StandardResponse)
async def update_group(req: UpdateGroupRequest):
    """Обновление названия и/или описания группы"""
    try:
        updated_fields = []
        if req.title and await update_group_title(req.group_id, req.title):
            updated_fields.append("title")
        if req.description and await update_group_description(req.group_id, req.description):
            updated_fields.append("description")

        if updated_fields:
            return StandardResponse(success=True, message=f"Обновлены: {', '.join(updated_fields)}")
        else:
            return StandardResponse(success=False, error="Ничего не обновлено")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.post("/group/topic/create", response_model=StandardResponse)
async def create_topic(req: CreateTopicRequest):
    """Создание нового топика в форуме с эмодзи"""
    try:
        topic = await create_forum_topic_with_emoji(req.group_id, req.topic_name, req.icon_emoji)
        if topic:
            return StandardResponse(
                success=True,
                message="Топик успешно создан с эмодзи" if req.icon_emoji else "Топик успешно создан",
                data=topic
            )
        else:
            return StandardResponse(success=False, error="Не удалось создать топик")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.put("/group/topic/update", response_model=StandardResponse)
async def update_topic(req: UpdateTopicRequest):
    """Обновление названия и/или эмодзи топика"""
    try:
        if not req.new_name and not req.new_emoji:
            return StandardResponse(
                success=False,
                error="Укажите новое название (new_name) или новый эмодзи (new_emoji)"
            )

        updated = await update_forum_topic(req.group_id, req.topic_id, req.new_name, req.new_emoji)

        if updated:
            updated_fields = []
            if req.new_name:
                updated_fields.append(f"название на '{req.new_name}'")
            if req.new_emoji:
                updated_fields.append(f"эмодзи на '{req.new_emoji}'")

            return StandardResponse(
                success=True,
                message=f"Топик обновлен: {', '.join(updated_fields)}",
                data={
                    "topic_id": req.topic_id,
                    "new_name": req.new_name,
                    "new_emoji": req.new_emoji
                }
            )
        else:
            return StandardResponse(success=False, error="Не удалось обновить топик")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.put("/group/topic/rename", response_model=StandardResponse)
async def rename_topic(req: UpdateTopicRequest):
    """[УСТАРЕЛ] Переименование топика - используйте /group/topic/update"""
    try:
        if not req.new_name:
            return StandardResponse(success=False, error="Не указано новое название топика")

        updated = await update_forum_topic(req.group_id, req.topic_id, req.new_name, None)

        if updated:
            return StandardResponse(success=True, message="Топик успешно переименован")
        else:
            return StandardResponse(success=False, error="Не удалось переименовать топик")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.delete("/group/topic/delete", response_model=StandardResponse)
async def delete_topic(req: TopicActionRequest):
    """Удаление топика"""
    try:
        if await delete_forum_topic(req.group_id, req.topic_id):
            return StandardResponse(success=True, message="Топик удален")
        else:
            return StandardResponse(success=False, error="Не удалось удалить")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.post("/group/user/invite", response_model=StandardResponse)
async def invite_user(req: UserActionRequest):
    """Приглашение пользователя в группу"""
    try:
        if await invite_user_to_group(req.group_id, req.username):
            return StandardResponse(success=True, message=f"@{req.username} приглашен")
        else:
            return StandardResponse(success=False, error="Не удалось пригласить")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


@app.delete("/group/user/remove", response_model=StandardResponse)
async def remove_user(req: UserActionRequest):
    """Удаление пользователя из группы"""
    try:
        if await remove_user_from_group(req.group_id, req.username):
            return StandardResponse(success=True, message=f"@{req.username} удален")
        else:
            return StandardResponse(success=False, error="Не удалось удалить")
    except Exception as e:
        return StandardResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)