import base64
import json
from datetime import UTC, datetime, timedelta
from html import unescape
from zoneinfo import ZoneInfo

import pytest
from dishka import Provider, Scope, make_async_container, provide

from portal_contracts.configuration import SettingScope
from portal_contracts.enums import BotRole
from portal_contracts.occasions import OccasionDay, OccasionPolicy
from src.config.providers import task_providers
from src.modules.automation.agents.domain.dtos import (
    AgentMessage,
    LLMReply,
    ToolCall,
    ToolFunction,
)
from src.modules.automation.agents.interfaces import ILLMClient
from src.modules.automation.missions.app import execution
from src.modules.automation.missions.domain.dtos import ScheduledMissionCreate
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.automation.missions.interfaces import (
    IMissionExecutor,
    IMissionService,
)
from src.modules.content.occasions.app.timing import occasion_publish_at
from src.modules.content.publications.app import commands
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.modules.content.publications.interfaces import IPublicationCommands
from tests.integration.conftest import OWNER, ExternalTelegramHandler

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("duplicate_comment", [False, True])
def test_rick_reads_calendar_then_drafts_every_occasion_and_publishes(
    portal, monkeypatch, duplicate_comment
):
    monkeypatch.setenv("PORTAL_DRY_RUN", "false")
    portal.environment["PORTAL_DRY_RUN"] = "false"
    portal.settings.portal.dry_run = False
    day_evidence = []
    stamp = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)
    monkeypatch.setattr(commands, "utc_now", lambda: stamp)
    monkeypatch.setattr(
        execution,
        "occasion_publish_at",
        lambda policy, zone, slot, now: occasion_publish_at(
            policy, zone, slot, stamp
        ),
    )

    class ExternalLLM:
        async def complete(self, history, tools):
            assert {tool["function"]["name"] for tool in tools} == {
                "get_calendar_occasions",
                "create_occasion_draft",
            }
            assert (
                history.messages[0].content == OccasionPolicy().system_prompt
            )
            assert history.messages[1].content.startswith(
                OccasionPolicy().prompt
            )
            assert "2026-10-05" in history.messages[1].content
            if history.messages[-1].role != "tool":
                name, arguments = "get_calendar_occasions", {}
            else:
                rejected = '"saved": false' in (
                    history.messages[-1].content or ""
                )
                if rejected:
                    assert "unique event IDs" in history.messages[-1].content
                    day = day_evidence[-1]
                else:
                    day = OccasionDay.model_validate_json(
                        history.messages[-1].content
                    )
                day_evidence.append(day)
                name = "create_occasion_draft"
                arguments = {
                    "draft": {
                        "date": day.date.isoformat(),
                        "intro": "خب، تقویم این بُعد هم شلوغه. 🧪",
                        "comments": [
                            {
                                "event_id": event.id,
                                "text": (
                                    "اگه با فقر کاری ندارن ولی برای بدن آدم‌ها "
                                    "قانون می‌نویسن، مشکل دو تا نورون نیست؛ "
                                    "خودِ دستگاه کنترله."
                                ),
                            }
                            for event in day.events
                        ],
                        "outro": "بریم سراغ بُعد بعدی.",
                    }
                }
                if duplicate_comment and not rejected:
                    arguments["draft"]["comments"] *= 2
            return LLMReply(
                message=AgentMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id=name,
                            function=ToolFunction(
                                name=name,
                                arguments=json.dumps(
                                    arguments, ensure_ascii=False
                                ),
                            ),
                        )
                    ],
                ),
                input_tokens=100,
                output_tokens=100,
                cost_usd="0.0002",
            )

    class ExternalProvider(Provider):
        @provide(scope=Scope.REQUEST, provides=ILLMClient, override=True)
        def llm(self) -> ExternalLLM:
            return ExternalLLM()

    async def workflow():
        await portal.change(
            "occasions.policy",
            SettingScope.GLOBAL,
            OccasionPolicy(enabled=True, owner_id=OWNER).model_dump(
                mode="json"
            ),
        )
        snapshot = await portal.snapshot()
        ai = snapshot.configuration.ai.model_dump(mode="json")
        ai.update(
            mode="openrouter",
            model="external-test-model",
            input_usd_per_million="0.4",
            output_usd_per_million="1.6",
        )
        await portal.change("ai.model", SettingScope.GLOBAL, ai)
        scheduled = ScheduledMissionCreate(
            owner_id=OWNER,
            role=BotRole.RICK,
            intent="occasions",
            text="Read the calendar and draft every occasion.",
            scheduled_at=stamp,
        )
        async with portal.request() as scope:
            service = await scope.get(IMissionService)
            await service.create_scheduled(scheduled)
            await service.create_scheduled(scheduled)
            mission = await (await scope.get(MissionRepository)).by_update(
                -3, int(stamp.timestamp() * 1_000_000)
            )
            mission_id = mission.id
        container = make_async_container(
            *task_providers(portal.settings), ExternalProvider()
        )
        try:
            for _ in range(3 if duplicate_comment else 2):
                async with container() as scope:
                    await (await scope.get(IMissionExecutor)).execute(
                        mission_id
                    )
        finally:
            await container.close()
        async with portal.request() as scope:
            mission = await (await scope.get(MissionRepository)).get(
                mission_id
            )
            assert mission.status == "draft_ready", mission.failure_reason
            repo = await scope.get(PublicationRepository)
            assert await repo.due(stamp, 20) == []
            rows = await repo.due(stamp + timedelta(hours=8), 20)
            assert len(rows) == 1
            assert rows[0].bot_role == "rick"
            chosen = rows[0].scheduled_at.replace(tzinfo=UTC)
            clock = chosen.astimezone(ZoneInfo("Asia/Tehran")).time()
            assert (
                snapshot.configuration.occasions.publish_start
                <= clock
                <= snapshot.configuration.occasions.publish_end
            )
            executor = await scope.get(IMissionExecutor)
            await executor.schedule_draft(
                mission, rows[0].draft_id, rows[0].revision
            )
            assert (await repo.get(rows[0].id)).scheduled_at.replace(
                tzinfo=UTC
            ) == chosen
            return rows[0].id, chosen

    publication_id, chosen = portal.run(workflow())

    async def published():
        async with portal.request() as scope:
            publisher = await scope.get(IPublicationCommands)
            await publisher.dispatch(publication_id)
            row = await (await scope.get(PublicationRepository)).get(
                publication_id
            )
            return row.status

    monkeypatch.setattr(
        commands, "utc_now", lambda: chosen - timedelta(seconds=1)
    )
    assert portal.run(published()) == "queued"
    assert ExternalTelegramHandler.messages == []
    monkeypatch.setattr(commands, "utc_now", lambda: chosen)
    assert portal.run(published()) == "sent"
    assert len(ExternalTelegramHandler.messages) == 1
    photo = base64.b64decode(
        ExternalTelegramHandler.messages[0]["png_base64"], validate=True
    )
    assert photo.startswith(b"\x89PNG\r\n\x1a\n")
    assert 0 < len(photo) <= 256 * 1024
    text = unescape(ExternalTelegramHandler.messages[0]["text"])
    assert all(event.title in text for event in day_evidence[0].events)
    assert "روز مبارزه با تن‌فروشی" in text

    assert len(day_evidence[0].events) == 1
    assert "http" not in text
    assert "منبع" not in text
    assert "غیررسمی" not in text
    assert "وضعیت تقویم" not in text
    assert "خبرهای پورتال" not in text
