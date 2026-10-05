from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from portal_bots.app.routing import MissionRouter
from portal_contracts.enums import Actor, BotRole, Intent
from portal_contracts.occasions import (
    OccasionComment,
    OccasionDraft,
    OccasionPolicy,
)
from src.modules.automation.agents.app.tools import (
    AgentToolCommands,
    calendar_evidence,
    occasion_text,
)
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AgentMessage,
    ToolCall,
    ToolFunction,
)
from src.modules.automation.missions.app.scheduled import occasion_slot
from src.modules.content.occasions.app.calendar import OccasionCalendar
from src.modules.content.publications.app.renderer import PostRenderer


def test_daily_slots_use_local_date_and_never_catch_up_yesterday():
    rule = OccasionPolicy(enabled=True, owner_id=1)
    before = datetime(2026, 10, 5, 6, 29, 59, tzinfo=UTC)
    at = before + timedelta(seconds=1)
    assert occasion_slot(rule, "Asia/Tehran", before) is None
    assert occasion_slot(rule, "Asia/Tehran", at) == at
    assert occasion_slot(rule, "Asia/Tehran", at + timedelta(hours=7)) == at
    assert (
        occasion_slot(rule, "Asia/Tehran", at + timedelta(hours=8, seconds=1))
        is None
    )
    assert occasion_slot(rule, "Asia/Tehran", at + timedelta(days=1)) == (
        at + timedelta(days=1)
    )
    assert (
        occasion_slot(
            rule.model_copy(update={"enabled": False}), "Asia/Tehran", at
        )
        is None
    )


@pytest.mark.parametrize("origin", list(BotRole))
def test_private_occasions_routes_to_rick(origin):
    routed = MissionRouter().route("/occasions 2026-10-05", origin)
    assert (routed.actor, routed.intent, routed.text) == (
        Actor.RICK,
        Intent.OCCASIONS,
        "2026-10-05",
    )
    assert MissionRouter().route("/occasions", origin).text == "today"


def test_draft_keeps_all_calendar_titles_and_rejects_omissions():
    day = OccasionCalendar(OccasionPolicy(), "Asia/Tehran").day(
        date(2026, 10, 5)
    )
    draft = OccasionDraft(
        date=day.date,
        intro="خب، تقویم این بُعد رو باز کنیم. 🧪",
        comments=[
            OccasionComment(
                event_id=event.id,
                text="مغزت هنوز منتظر تأیید یه موجود کراواتیه؟",
            )
            for event in day.events
        ],
        outro="بریم سراغ بُعد بعدی.",
    )
    text = occasion_text(day, draft)
    assert all(event.title in text for event in day.events)
    assert not any(event.source in text for event in day.events)
    assert day.events[0].type == "Informal"
    assert "روز مبارزه با تن‌فروشی" in text
    assert "غیررسمی" not in text
    assert not any(event.note in text for event in day.events if event.note)
    assert not any(warning in text for warning in day.warnings)
    for comments in [draft.comments[:-1], draft.comments + draft.comments[:1]]:
        with pytest.raises(ValueError, match="exactly once"):
            occasion_text(day, draft.model_copy(update={"comments": comments}))
    with pytest.raises(ValueError):
        occasion_text(
            day, draft.model_copy(update={"date": date(2026, 10, 6)})
        )


def test_empty_calendar_is_reported_without_inventing_an_event():
    day = (
        OccasionCalendar(OccasionPolicy(), "Asia/Tehran")
        .day(date(2026, 10, 5))
        .model_copy(update={"events": []})
    )
    with pytest.raises(ValueError, match="No selected occasions"):
        occasion_text(day, OccasionDraft(date=day.date, comments=[]))


def test_calendar_evidence_accepts_only_matching_tool_call():
    day = OccasionCalendar(OccasionPolicy(), "Asia/Tehran").day(
        date(2026, 10, 5)
    )
    history = AgentHistory(
        messages=[
            AgentMessage(role="user", content=day.model_dump_json()),
            AgentMessage(
                role="tool",
                tool_call_id="wrong",
                content=day.model_dump_json(),
            ),
        ]
    )
    assert calendar_evidence(history) is None
    history.messages.extend(
        [
            AgentMessage(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="calendar-1",
                        function=ToolFunction(
                            name="get_calendar_occasions", arguments="{}"
                        ),
                    )
                ],
            ),
            AgentMessage(
                role="tool",
                tool_call_id="calendar-1",
                content=day.model_dump_json(),
            ),
        ]
    )
    assert calendar_evidence(history) == day


@pytest.mark.asyncio
async def test_scheduled_calendar_cannot_change_day(snapshot):
    settings = snapshot[0]
    slot = datetime(2026, 10, 5, 5, 30, tzinfo=UTC)
    commands = object.__new__(AgentToolCommands)
    commands.settings = settings
    commands.calendar = OccasionCalendar(OccasionPolicy(), "Asia/Tehran")
    commands.authorize = AsyncMock(
        return_value=SimpleNamespace(
            intent="occasions",
            automation_key=f"occasions:{int(slot.timestamp() * 1_000_000)}",
            text="today",
        )
    )
    assert (await commands.get_calendar_occasions()).date == date(2026, 10, 5)
    with pytest.raises(ValueError, match="mission's calendar date"):
        await commands.get_calendar_occasions("2026-10-06")


@pytest.mark.asyncio
async def test_draft_tool_requires_calendar_read_in_this_mission():
    commands = object.__new__(AgentToolCommands)
    commands.authorize = AsyncMock(
        return_value=SimpleNamespace(id=1, intent="occasions")
    )
    commands.checkpoints = SimpleNamespace(get=AsyncMock(return_value=None))
    with pytest.raises(ValueError, match="Read get_calendar_occasions"):
        await commands.create_occasion_draft(
            OccasionDraft(
                date=date(2026, 10, 5), intro="ریک", comments=[], outro="تمام"
            )
        )


@pytest.mark.parametrize(
    "text",
    [
        "دارم به سبک ریک حرف می‌زنم.",
        "برداشت ریک: یه چیزی.",
        "برداشت کوتاه ریک: یه چیزی.",
        "با لحن ریک اینو بخون.",
        "منبع تقویم: فلان",
        "https://example.com/day",
        "وضعیت تقویم: پوشش ناقص",
    ],
)
def test_public_text_rejects_sources_and_persona_announcements(text):
    day = OccasionCalendar(OccasionPolicy(), "Asia/Tehran").day(
        date(2026, 10, 5)
    )
    draft = OccasionDraft(
        date=day.date,
        comments=[
            OccasionComment(event_id=event.id, text=text)
            for event in day.events
        ],
    )
    with pytest.raises(ValueError, match="without sources or persona"):
        occasion_text(day, draft)


def test_occasion_caption_has_no_calendar_or_portal_wrapper(snapshot):
    presentation = snapshot[1]
    body = "روز آغوش\nمورتی، یه بغل بده؛ این یکی فرم مجوز نمی‌خواد."
    rendered = PostRenderer(presentation).render(
        "internal date metadata", body, "occasions"
    )
    assert rendered == body


@pytest.mark.asyncio
async def test_unselected_calendar_day_admits_no_mission(
    snapshot, monkeypatch
):
    from src.modules.automation.missions.app import scheduled

    settings = snapshot[0].model_copy(deep=True)
    settings.occasions = OccasionPolicy(enabled=True, owner_id=1234)
    settings.automation.owner_id = None
    settings.portal.channel_id = -1001234
    missions = SimpleNamespace(create_scheduled=AsyncMock())
    guard = SimpleNamespace(is_paused=AsyncMock(return_value=False))
    monkeypatch.setattr(
        scheduled,
        "utc_now",
        lambda: datetime(2026, 10, 7, 6, 30, tzinfo=UTC),
    )
    await scheduled.ScheduledMissionCommands(
        missions,
        guard,
        settings,
        SimpleNamespace(security=SimpleNamespace(admin_ids={1234})),
    ).tick()
    missions.create_scheduled.assert_not_awaited()
