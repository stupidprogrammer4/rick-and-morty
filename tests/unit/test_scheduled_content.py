from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from portal_contracts.configuration import AutomationPolicy
from src.modules.automation.missions.app.scheduled import current_slot


def test_database_cadence_does_not_reset_after_restart(snapshot):
    rule = snapshot[0].automation.news.model_copy(update={"enabled": True})
    anchor = rule.starts_at
    assert current_slot(rule, anchor - timedelta(seconds=1)) is None
    assert current_slot(rule, anchor) == anchor
    assert (
        current_slot(rule, anchor + timedelta(hours=4, minutes=59)) == anchor
    )
    assert current_slot(
        rule, anchor + timedelta(hours=5)
    ) == anchor + timedelta(hours=5)
    assert current_slot(
        rule, anchor + timedelta(hours=17)
    ) == anchor + timedelta(hours=15)
    assert (
        current_slot(rule.model_copy(update={"enabled": False}), anchor)
        is None
    )


def test_enabled_automation_requires_owner(snapshot):
    value = snapshot[0].automation.model_dump(mode="json")
    value["news"]["enabled"] = True
    with pytest.raises(ValidationError):
        AutomationPolicy.model_validate(value)


@pytest.mark.asyncio
async def test_rss_rejects_document_entities():
    from defusedxml.common import DefusedXmlException

    from src.modules.content.news.domain.dtos import NewsSource
    from src.modules.content.news.infra.sources import NewsCollector
    from src.modules.ops.settings.domain.dtos import NewsSourceCatalog

    class ExternalXML:
        async def get(self, *args, **kwargs):
            return (
                b'<!DOCTYPE rss [<!ENTITY unsafe "injected">]>'
                b"<rss><channel><item><title>&unsafe;</title></item>"
                b"</channel></rss>"
            )

    source = NewsSource(
        id="hn",
        feed_url="https://news.ycombinator.com/rss",
        allowed_hosts={"news.ycombinator.com"},
        topics={"ai"},
        enabled=True,
    )
    collector = NewsCollector(
        ExternalXML(), NewsSourceCatalog(sources=[source])
    )
    with pytest.raises(DefusedXmlException):
        await collector.feed(source, datetime.now(UTC))
