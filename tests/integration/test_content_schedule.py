from datetime import time

import pytest

from src.cli import content_schedule
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


def test_activate_requested_cadence_on_existing_database(portal, monkeypatch):
    monkeypatch.setattr(
        content_schedule, "get_settings", lambda _: portal.settings
    )
    before = portal.run(portal.snapshot()).configuration
    portal.run(content_schedule.apply(OWNER))
    after = portal.run(portal.snapshot()).configuration
    assert after.portal.channel_id == before.portal.channel_id
    assert after.portal.quiet_start == after.portal.quiet_end
    assert after.portal.daily_post_cap >= 45
    assert after.automation.owner_id == after.occasions.owner_id == OWNER
    assert after.automation.prices.enabled
    assert after.automation.prices.interval_seconds == 3600
    assert after.automation.news.enabled
    assert after.automation.news.interval_seconds == 7200
    assert after.automation.charts.enabled
    assert after.automation.charts.interval_seconds == 10800
    assert after.automation.news.prompt == before.automation.news.prompt
    assert after.market.enabled and after.market.charts.enabled
    assert after.occasions.enabled
    assert (
        after.occasions.time,
        after.occasions.publish_start,
        after.occasions.publish_end,
    ) == (time(10), time(15), time(18))


def test_rejected_owner_does_not_change_configuration(portal, monkeypatch):
    monkeypatch.setattr(
        content_schedule, "get_settings", lambda _: portal.settings
    )
    before = portal.run(portal.snapshot()).configuration.model_dump_json()
    with pytest.raises(ValueError, match="administrator"):
        portal.run(content_schedule.apply(OWNER + 1))
    assert (
        portal.run(portal.snapshot()).configuration.model_dump_json() == before
    )
