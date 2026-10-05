from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from portal_contracts.configuration import AutomationPolicy, SettingScope
from portal_contracts.enums import BotRole
from src.modules.automation.missions.app.scheduled import (
    ScheduledMissionCommands,
    current_slot,
)


def test_chart_schedule_is_backward_compatible_and_requires_owner(snapshot):
    policy = snapshot[0].automation.model_dump(mode="json")
    policy.pop("charts", None)
    restored = AutomationPolicy.model_validate(policy)
    assert not restored.charts.enabled
    assert restored.charts.interval_seconds == 7 * 3600
    policy["charts"] = restored.charts.model_dump(mode="json")
    policy["charts"]["enabled"] = True
    policy["owner_id"] = None
    with pytest.raises(ValidationError):
        AutomationPolicy.model_validate(policy)


def test_chart_and_price_slots_advance_independently(snapshot):
    anchor = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)
    prices = snapshot[0].automation.prices.model_copy(
        update={
            "enabled": True,
            "starts_at": anchor,
            "interval_seconds": 7200,
        }
    )
    charts = snapshot[0].automation.charts.model_copy(
        update={
            "enabled": True,
            "starts_at": anchor,
            "interval_seconds": 25200,
        }
    )
    assert current_slot(charts, anchor - timedelta(seconds=1)) is None
    assert current_slot(prices, anchor + timedelta(hours=6)) == (
        anchor + timedelta(hours=6)
    )
    assert current_slot(charts, anchor + timedelta(hours=6)) == anchor
    assert current_slot(charts, anchor + timedelta(hours=7)) == (
        anchor + timedelta(hours=7)
    )
    assert current_slot(prices, anchor + timedelta(hours=7)) == (
        anchor + timedelta(hours=6)
    )
    assert current_slot(charts, anchor + timedelta(hours=22)) == (
        anchor + timedelta(hours=21)
    )


@pytest.mark.asyncio
async def test_chart_admission_is_independent_of_price_reports(snapshot):
    settings = snapshot[0]
    settings.market.enabled = False
    settings.market.charts.enabled = True
    rule = settings.automation.charts.model_copy(
        update={
            "enabled": True,
            "starts_at": datetime(2026, 10, 5, 6, 30, tzinfo=UTC),
        }
    )
    missions = SimpleNamespace(create_scheduled=AsyncMock())
    commands = ScheduledMissionCommands(
        missions, SimpleNamespace(), settings, SimpleNamespace()
    )
    await commands.admit("charts", BotRole.MORTY, rule, 123)
    missions.create_scheduled.assert_awaited_once()
    event = missions.create_scheduled.await_args.args[0]
    assert event.intent == "charts"
    assert event.role == BotRole.MORTY
    settings.market.charts.enabled = False
    missions.create_scheduled.reset_mock()
    await commands.admit("charts", BotRole.MORTY, rule, 123)
    missions.create_scheduled.assert_not_awaited()


def test_chart_post_style_has_its_own_validated_scope(snapshot):
    from portal_contracts.configuration import SettingKey
    from src.modules.ops.settings.app.validation import SettingValueValidator

    style = snapshot[1].posts["market"].model_dump_json()
    parsed = SettingValueValidator().validate(
        SettingKey.POST, SettingScope.CHARTS, style
    )
    assert parsed == style
