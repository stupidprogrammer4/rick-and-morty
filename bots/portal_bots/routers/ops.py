from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from portal_bots.app.voice import BotVoice
from portal_bots.interfaces import IBackendClient
from portal_contracts.enums import BotRole

router = Router(name="ops")


@router.message(Command("start"))
async def start(message: Message, role: BotRole, voice: BotVoice):
    await message.answer(voice.welcome(role))


@router.message(Command("help"))
async def help_message(message: Message):
    await message.answer(
        "/ask rick متن · /ask morty متن\n/team python ai · /news python ai\n"
        "/summarize https://… · /prices · /occasions [YYYY-MM-DD]\n"
        "/jobs [صفحه] · /job شناسه · /cancel شناسه\n"
        "/drafts [صفحه] · /draft شناسه\n"
        "/approve شناسه [نسخه] · /reject شناسه [نسخه]\n"
        "/publish شناسه · /schedule شناسه زمان-ISO\n"
        "/add_music متن · /add_tech متن · /notice متن\n"
        "/status · /pause · /resume\n"
        "/resolve شناسه پیام یا /resolve شناسه resend\n"
        "/settings key scope · /set_setting key scope JSON\n/prompt [متن]"
    )


@router.message(Command("status", "pause", "resume"))
async def status(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    command = (message.text or "").split("@")[0]
    if command in {"/pause", "/resume"}:
        await backend.request(
            "PUT",
            "/pause",
            message.from_user.id,
            data={"paused": command == "/pause"},
        )
        await message.answer(
            "نشر متوقف شد." if command == "/pause" else "نشر فعال شد."
        )
        return
    result = await backend.request("GET", "/status", message.from_user.id)
    labels = {
        "database": "دیتابیس",
        "paused": "توقف نشر",
        "dry_run": "اجرای آزمایشی",
        "ai_mode": "حالت ریک",
        "model_configured": "مدل تنظیم شده",
        "market_enabled": "بازار فعال",
        "daily_post_cap": "سقف مشترک روزانه",
        "queues": "صف‌ها و بودجهٔ مدل",
    }
    await message.answer(
        escape(
            "\n".join(
                f"{labels[key]}: {value}"
                for key, value in result.items()
                if key in labels
            )
        )
    )


@router.message(Command("resolve"))
async def resolve(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    words = (message.text or "").split()
    if len(words) != 3:
        await message.answer("/resolve شناسه‌ارسال شناسه‌پیام یا resend")
        return
    data = (
        {"resend": True}
        if words[2] == "resend"
        else {"message_id": int(words[2])}
    )
    result = await backend.request(
        "POST",
        f"/publications/{int(words[1])}/resolve",
        message.from_user.id,
        data=data,
    )
    await message.answer(escape(f"ارسال #{result['id']}: {result['status']}"))
