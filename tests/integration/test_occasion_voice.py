from datetime import UTC, datetime, timedelta

import pytest

from portal_contracts.configuration import SettingScope
from portal_contracts.content import DraftCreate, DraftDecision, PublishRequest
from portal_contracts.enums import BotRole, Category
from portal_contracts.occasions import OccasionPolicy
from src.cli import occasion_voice
from src.modules.automation.missions.domain.dtos import ScheduledMissionCreate
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.automation.missions.interfaces import IMissionService
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.modules.content.publications.interfaces import IPublicationCommands
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


def test_voice_upgrade_preserves_timing_and_cancels_only_old_occasion_posts(
    portal, monkeypatch
):
    monkeypatch.setattr(
        occasion_voice, "get_settings", lambda _: portal.settings
    )

    async def workflow():
        old = OccasionPolicy(selection="all", max_events=5, prompt="Old voice")
        await portal.change(
            "occasions.policy",
            SettingScope.GLOBAL,
            old.model_dump(mode="json"),
        )
        before = (await portal.snapshot()).configuration
        stamp = datetime.now(UTC)
        async with portal.request() as request:
            await (await request.get(IMissionService)).create_scheduled(
                ScheduledMissionCreate(
                    owner_id=OWNER,
                    role=BotRole.RICK,
                    intent="occasions",
                    text="old task",
                    scheduled_at=stamp,
                )
            )
            mission = await (await request.get(MissionRepository)).by_update(
                -3, int(stamp.timestamp() * 1_000_000)
            )
            drafts = await request.get(IDraftService)
            publisher = await request.get(IPublicationCommands)
            ids = []
            for name, mission_id in (
                ("old occasion", mission.id),
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
        await occasion_voice.apply()
        after = (await portal.snapshot()).configuration
        assert after.automation == before.automation
        assert after.portal == before.portal
        assert after.occasions.enabled == old.enabled
        assert after.occasions.time == old.time
        assert after.occasions.publish_start == old.publish_start
        assert after.occasions.publish_end == old.publish_end
        assert after.occasions.selection == "youth"
        assert after.occasions.max_events == 3
        assert after.occasions.system_prompt == OccasionPolicy().system_prompt
        assert after.occasions.prompt == OccasionPolicy().prompt
        async with portal.request() as request:
            repo = await request.get(PublicationRepository)
            assert (await repo.get(ids[0])).status == "cancelled"
            assert (await repo.get(ids[1])).status == "queued"

    portal.run(workflow())
