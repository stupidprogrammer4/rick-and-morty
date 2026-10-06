from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from portal_contracts.configuration import (
    AutomationPolicy,
    MarketPolicy,
    PortalPolicy,
    SettingKey,
)
from portal_contracts.occasions import OccasionPolicy
from src.cli.content_schedule import cadence_values
from src.modules.content.occasions.app import timing


@pytest.mark.parametrize("offset,expected", [(0, 15), (10800, 18)])
def test_random_publication_includes_both_window_boundaries(
    monkeypatch, offset, expected
):
    monkeypatch.setattr(timing, "randbelow", lambda count: offset)
    stamp = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)
    chosen = timing.occasion_publish_at(
        OccasionPolicy(), "Asia/Tehran", stamp, stamp
    )
    assert chosen is not None
    assert chosen.astimezone(ZoneInfo("Asia/Tehran")).time() == time(expected)


def test_late_preparation_uses_remaining_window_and_never_yesterday(
    monkeypatch,
):
    monkeypatch.setattr(timing, "randbelow", lambda count: 0)
    stamp = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)
    late = datetime(2026, 10, 5, 13, 31, 7, 1, tzinfo=UTC)
    assert timing.occasion_publish_at(
        OccasionPolicy(), "Asia/Tehran", stamp, late
    ) == late.replace(microsecond=0) + timedelta(seconds=1)
    assert (
        timing.occasion_publish_at(
            OccasionPolicy(), "Asia/Tehran", stamp, stamp + timedelta(hours=9)
        )
        is None
    )
    assert (
        timing.occasion_publish_at(
            OccasionPolicy(), "Asia/Tehran", stamp, stamp + timedelta(days=1)
        )
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"publish_start": time(18), "publish_end": time(15)},
        {"time": time(16)},
        {"publish_start": time(15, tzinfo=UTC)},
    ],
)
def test_invalid_clock_windows_are_rejected(changes):
    with pytest.raises(ValidationError):
        OccasionPolicy(**changes)


@pytest.mark.parametrize("daily_cap", [30, 45])
def test_requested_cadence_preserves_user_content_and_has_capacity(
    snapshot, daily_cap
):
    current = snapshot[0].model_copy(deep=True)
    current.portal.channel_id = -1001234
    current.portal.daily_post_cap = daily_cap
    current.occasions.excluded_ids = ["kept"]
    current.automation.news.prompt = "Keep my Rick prompt"
    changes = cadence_values(
        current, 1234, datetime(2026, 10, 5, 6, 30, tzinfo=UTC)
    )
    automation = AutomationPolicy.model_validate_json(
        changes[SettingKey.AUTOMATION]
    )
    assert automation.prices.interval_seconds == 3600
    assert (
        automation.news.interval_seconds
        == automation.news.lookback_seconds
        == 7200
    )
    assert automation.charts.interval_seconds == 10800
    assert automation.news.prompt == current.automation.news.prompt
    assert all(
        rule.enabled
        for rule in [automation.news, automation.prices, automation.charts]
    )
    assert all(
        rule.starts_at.hour == 10
        for rule in [automation.news, automation.prices, automation.charts]
    )
    occasions = OccasionPolicy.model_validate_json(
        changes[SettingKey.OCCASIONS]
    )
    assert occasions.enabled and occasions.owner_id == 1234
    assert occasions.excluded_ids == ["kept"]
    assert (
        occasions.time,
        occasions.publish_start,
        occasions.publish_end,
    ) == (time(10), time(15), time(18))
    portal = PortalPolicy.model_validate_json(changes[SettingKey.PORTAL])
    assert portal.channel_id == -1001234
    assert portal.daily_post_cap == max(45, daily_cap)
    assert portal.quiet_start == portal.quiet_end
    assert MarketPolicy.model_validate_json(
        changes[SettingKey.MARKET]
    ).charts.enabled
