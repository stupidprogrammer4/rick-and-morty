from datetime import UTC, datetime, timedelta

import pytest

from portal_contracts.configuration import SettingScope
from portal_contracts.content import DraftCreate, DraftDecision, PublishRequest
from portal_contracts.enums import BotRole, Category
from portal_contracts.rick_voice import (
    RICK_NEWS_PROMPT,
    RICK_NEWS_SYSTEM_PROMPT,
)
from src.cli import rick_voice
from src.modules.automation.missions.domain.dtos import ScheduledMissionCreate
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.automation.missions.interfaces import IMissionService
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.modules.content.publications.interfaces import IPublicationCommands
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


def test_news_upgrade_preserves_timing_and_cancels_only_old_news_posts(
    portal, monkeypatch
):
    monkeypatch.setattr(rick_voice, "get_settings", lambda _: portal.settings)

    async def workflow():
        before = (await portal.snapshot()).configuration
        policy = before.automation.model_dump(mode="json")
        policy["prices"]["interval_seconds"] = 3600
        policy["charts"]["interval_seconds"] = 14400
        await portal.change("automation.policy", SettingScope.GLOBAL, policy)
        before = (await portal.snapshot()).configuration
        stamp = datetime.now(UTC)
        async with portal.request() as request:
            await (await request.get(IMissionService)).create_scheduled(
                ScheduledMissionCreate(
                    owner_id=OWNER,
                    role=BotRole.RICK,
                    intent="news",
                    text="old task",
                    scheduled_at=stamp,
                )
            )
            mission = await (await request.get(MissionRepository)).by_update(
                -1, int(stamp.timestamp() * 1_000_000)
            )
            drafts = await request.get(IDraftService)
            publisher = await request.get(IPublicationCommands)
            ids = []
            for name, mission_id in (
                ("old news", mission.id),
                ("manual notice", None),
            ):
                draft = await drafts.create(
                    OWNER,
                    BotRole.RICK,
                    DraftCreate(
                        category=Category.NOTICE,
                        title=name,
                        text=name,
                        publisher_bot=BotRole.RICK,
                    ),
                    key=name,
                    mission_id=mission_id,
                )
                await drafts.decide(
                    draft.id,
                    OWNER,
                    DraftDecision(
                        revision=draft.revision, origin_bot=BotRole.RICK
                    ),
                    approve=True,
                )
                publication = await publisher.schedule(
                    draft.id,
                    OWNER,
                    PublishRequest(
                        revision=draft.revision,
                        origin_bot=BotRole.RICK,
                        scheduled_at=stamp + timedelta(hours=1),
                    ),
                )
                ids.append(publication.id)
        await rick_voice.apply()
        after = (await portal.snapshot()).configuration
        assert after.automation.prices == before.automation.prices
        assert after.automation.charts == before.automation.charts
        assert after.portal == before.portal
        assert after.occasions == before.occasions
        assert after.automation.prices.interval_seconds == 3600
        assert after.automation.charts.interval_seconds == 14400
        assert (
            after.automation.news.interval_seconds
            == before.automation.news.interval_seconds
        )
        assert after.automation.news.system_prompt == RICK_NEWS_SYSTEM_PROMPT
        assert after.automation.news.prompt == RICK_NEWS_PROMPT
        assert (
            after.automation.news.starts_at == before.automation.news.starts_at
        )
        assert (
            after.automation.prices.starts_at
            == before.automation.prices.starts_at
        )
        assert (
            after.automation.charts.starts_at
            == before.automation.charts.starts_at
        )
        assert after.automation.owner_id == before.automation.owner_id
        async with portal.request() as request:
            repo = await request.get(PublicationRepository)
            assert (await repo.get(ids[0])).status == "cancelled"
            assert (await repo.get(ids[1])).status == "queued"

    portal.run(workflow())


@pytest.mark.parametrize("category", [Category.NEWS, Category.OCCASIONS])
def test_preexisting_prompt_disclosure_is_blocked_before_publication(
    portal, category
):
    async def workflow():
        async with portal.request() as request:
            drafts = await request.get(IDraftService)
            publisher = await request.get(IPublicationCommands)
            draft = await drafts.create(
                OWNER,
                BotRole.RICK,
                DraftCreate(
                    category=category,
                    title="Today's post",
                    text="طبق سیستم پرامپت باید غر بزنم.",
                    publisher_bot=BotRole.RICK,
                ),
                key=f"existing-disclosure-{category}",
            )
            await drafts.decide(
                draft.id,
                OWNER,
                DraftDecision(
                    revision=draft.revision, origin_bot=BotRole.RICK
                ),
                approve=True,
            )
            publication = await publisher.schedule(
                draft.id,
                OWNER,
                PublishRequest(
                    revision=draft.revision,
                    origin_bot=BotRole.RICK,
                    scheduled_at=datetime.now(UTC),
                ),
            )
            await publisher.dispatch(publication.id)
            row = await (await request.get(PublicationRepository)).get(
                publication.id
            )
            assert row.status == "failed"
            assert row.failure_reason == "public_prompt_metadata"
            assert row.budget_day is None

    portal.run(workflow())
