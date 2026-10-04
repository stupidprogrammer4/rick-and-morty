from datetime import UTC, datetime

import pytest

from portal_bots.app.routing import MissionRouter
from portal_contracts.enums import Actor, BotRole, Intent
from src.modules.content.publications.app.policy import PublicationPolicy


@pytest.mark.parametrize(
    "text,role,actor,intent",
    [
        ("/prices", BotRole.RICK, Actor.MORTY, Intent.PRICES),
        ("/news python", BotRole.MORTY, Actor.TEAM, Intent.NEWS),
        ("/ask morty hi", BotRole.RICK, Actor.MORTY, Intent.CHAT),
        ("ریک، سلام", BotRole.MORTY, Actor.RICK, Intent.CHAT),
        ("مورتی: قیمت طلا", BotRole.RICK, Actor.MORTY, Intent.PRICES),
        (
            "/summarize https://example.com",
            BotRole.RICK,
            Actor.TEAM,
            Intent.SUMMARY,
        ),
    ],
)
def test_explicit_commands_keep_role_and_intent(text, role, actor, intent):
    result = MissionRouter().route(text, role)
    assert (result.actor, result.intent) == (actor, intent)


@pytest.mark.parametrize(
    "text", ["", "/unknown", "/ask rick", "/ask unknown hi"]
)
def test_missing_or_unknown_requests_are_rejected(text):
    with pytest.raises(ValueError):
        MissionRouter().route(text, BotRole.RICK)


@pytest.mark.parametrize(
    "hour,minute,quiet",
    [
        (19, 29, False),
        (19, 30, True),  # 22:59 / 23:00 Tehran
        (5, 29, True),
        (5, 30, False),  # 08:59 / 09:00 Tehran
    ],
)
def test_quiet_hours_use_tehran_and_exact_boundaries(
    snapshot, hour, minute, quiet
):
    now = datetime(2026, 10, 3, hour, minute, tzinfo=UTC)
    assert PublicationPolicy(snapshot[0].portal).quiet(now) is quiet
