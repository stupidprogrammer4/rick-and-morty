import re
from dataclasses import dataclass

from portal_contracts.enums import Actor, BotRole, Intent


@dataclass(frozen=True)
class RoutedMission:
    actor: Actor
    intent: Intent
    text: str


class MissionRouter:
    def route(self, text: str, origin: BotRole) -> RoutedMission:
        text = text.strip()
        actor = Actor(origin.value)
        intent = Intent.CHAT
        command, _, body = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        if command == "/prices":
            return RoutedMission(Actor.MORTY, Intent.PRICES, "prices")
        if command in {"/team", "/news"}:
            return RoutedMission(Actor.TEAM, Intent.NEWS, body or "news")
        if command == "/summarize":
            return RoutedMission(Actor.TEAM, Intent.SUMMARY, body)
        if command == "/ask":
            role, _, request = body.partition(" ")
            if role not in {"rick", "morty"} or not request:
                raise ValueError("/ask rick متن یا /ask morty متن")
            actor = Actor(role)
            text = request
        elif text.startswith("/"):
            raise ValueError("فرمان را از /help انتخاب کن.")
        else:
            prefixes = [
                (
                    r"^(?:ریک\s*(?:و|&)\s*مورتی|مورتی\s*و\s*ریک)[،,:\s]+",
                    Actor.TEAM,
                ),
                (r"^ریک[،,:\s]+", Actor.RICK),
                (r"^مورتی[،,:\s]+", Actor.MORTY),
            ]
            for pattern, candidate in prefixes:
                match = re.match(pattern, text)
                if match:
                    actor = candidate
                    text = text[match.end() :].strip()
                    break
        if actor == Actor.TEAM or any(
            word in text for word in ["خبر", "news"]
        ):
            intent = Intent.NEWS
            actor = Actor.TEAM
        if "https://" in text and any(
            word in text for word in ["خلاصه", "summarize"]
        ):
            intent = Intent.SUMMARY
            actor = Actor.TEAM
        if actor == Actor.MORTY and "قیمت" in text:
            intent = Intent.PRICES
        if not text:
            raise ValueError("متن مأموریت خالی است.")
        return RoutedMission(actor, intent, text)
