import json
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from portal_bots.interfaces import IBackendClient
from portal_contracts.configuration import SettingScope
from portal_contracts.enums import BotRole

router = Router(name="settings")


@router.message(Command("settings", "set_setting"))
async def setting(message: Message, backend: IBackendClient):
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        raise ValueError("/settings key scope · /set_setting key scope JSON")
    command, key, scope = parts[:3]
    path = f"/configuration/values/{key}/{scope}"
    current = await backend.request("GET", path, message.from_user.id)
    if command.split("@")[0] == "/set_setting":
        if len(parts) != 4:
            raise ValueError("JSON is required")
        normalized = json.dumps(json.loads(parts[3]), ensure_ascii=False)
        current = await backend.request(
            "PUT",
            path,
            message.from_user.id,
            data={"revision": current["revision"], "value": normalized},
        )
    value = current.get("value") or "null"
    text = f"{key}/{scope} · revision {current['revision']}\n{value}"
    await message.answer(escape(text[:3800]))


@router.message(Command("prompt"))
async def prompt(message: Message, backend: IBackendClient, role: BotRole):
    if message.from_user is None:
        return
    _, _, text = (message.text or "").partition(" ")
    scope = SettingScope(role.value)
    path = f"/configuration/values/voice/{scope}"
    current = await backend.request("GET", path, message.from_user.id)
    profile = json.loads(current["value"])
    if text.strip():
        profile["system_prompt"] = text.strip()
        await backend.request(
            "PUT",
            path,
            message.from_user.id,
            data={
                "value": json.dumps(profile, ensure_ascii=False),
                "revision": current["revision"],
            },
        )
        await message.answer("System prompt updated.")
        return
    await message.answer(escape(profile["system_prompt"][:3800]))
