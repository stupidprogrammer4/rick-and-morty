from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReactionTypeEmoji

from portal_bots.app.routing import MissionRouter
from portal_bots.app.voice import BotVoice
from portal_bots.interfaces import IBackendClient
from portal_contracts.enums import BotRole
from portal_contracts.missions import (
    MissionAccepted,
    MissionCreate,
    MissionPage,
)

router = Router(name="missions")


@router.message(Command("jobs"))
async def jobs(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    words = (message.text or "").split()
    page = int(words[1]) if len(words) > 1 else 1
    raw = await backend.request(
        "GET", f"/missions?page={page}", message.from_user.id
    )
    data = MissionPage.model_validate(raw)
    text = (
        "\n".join(
            f"#{item.id} · {item.status} · {item.stage}" for item in data.items
        )
        or "فعلاً مأموریتی نداریم."
    )
    await message.answer(escape(f"صفحه {page} · مجموع {data.total}\n{text}"))


@router.message(Command("job", "cancel"))
async def job(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    words = (message.text or "").split()
    if len(words) != 2:
        await message.answer("/job شناسه یا /cancel شناسه")
        return
    id = int(words[1])
    cancel = words[0].split("@")[0] == "/cancel"
    raw = await backend.request(
        "POST" if cancel else "GET",
        f"/missions/{id}" + ("/cancel" if cancel else ""),
        message.from_user.id,
    )
    detail = raw.get("result") or raw.get("failure_reason") or raw["stage"]
    text = f"#{id} · {raw['status']}\n{detail}"
    await message.answer(escape(text))


@router.message(F.text)
async def mission(
    message: Message,
    backend: IBackendClient,
    role: BotRole,
    update_id: int,
    voice: BotVoice,
):
    if message.from_user is None or message.bot is None:
        return
    routed = MissionRouter().route(message.text or "", role)
    data = MissionCreate(
        owner_id=message.from_user.id,
        origin_chat_id=message.chat.id,
        origin_bot=role,
        origin_message_id=message.message_id,
        bot_id=message.bot.id,
        update_id=update_id,
        actor=routed.actor,
        intent=routed.intent,
        text=routed.text,
    )
    raw = await backend.request(
        "POST",
        "/missions",
        message.from_user.id,
        data=data.model_dump(mode="json"),
    )
    accepted = MissionAccepted.model_validate(raw)
    if accepted.duplicate:
        return
    await message.answer(voice.accepted(role, accepted.mission.id))
    try:
        await message.react(
            [
                ReactionTypeEmoji(
                    emoji=voice.presentation.interactions.accepted.value
                )
            ]
        )
    except Exception:
        pass
