import json
from datetime import timedelta
from html import unescape

import pytest
from dishka import Provider, Scope, make_async_container, provide
from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import SettingScope
from portal_contracts.enums import BotRole
from portal_contracts.rick_voice import RICK_NEWS_SYSTEM_PROMPT
from src.config.providers import task_providers
from src.modules.automation.agents.domain.dtos import (
    AgentMessage,
    LLMReply,
    ToolCall,
    ToolFunction,
)
from src.modules.automation.agents.infra.mysql import CheckpointRepository
from src.modules.automation.agents.interfaces import ILLMClient
from src.modules.automation.missions.domain.dtos import (
    MissionChange,
    ScheduledMissionCreate,
)
from src.modules.automation.missions.infra.mysql import MissionRepository
from src.modules.automation.missions.interfaces import (
    IMissionExecutor,
    IMissionService,
)
from src.modules.content.news.domain.models import ArticleModel
from src.modules.content.news.infra.mysql import ArticleRepository
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.shared.dates import utc_now
from tests.integration.conftest import OWNER, ExternalTelegramHandler

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("parallel_reply", "unfinished_summary"),
    [(False, False), (True, False), (False, True)],
)
def test_news_corrects_parallel_model_calls_before_publication(
    portal, parallel_reply, unfinished_summary, monkeypatch
):
    monkeypatch.setenv("PORTAL_DRY_RUN", "false")
    portal.environment["PORTAL_DRY_RUN"] = "false"
    portal.settings.portal.dry_run = False

    class ExternalLLM:
        def __init__(self):
            self.responses = 0

        async def complete(self, history, tools):
            self.responses += 1
            assert history.tool_choice == "required"
            assert history.messages[0].content == RICK_NEWS_SYSTEM_PROMPT
            assert len(history.messages) >= 3
            assert "با یک غر کوتاه" not in str(history.model_dump())
            assert {tool["function"]["name"] for tool in tools} == {
                "create_post_draft"
            }
            evidence = json.loads(history.messages[2].content)[
                "untrusted_article_evidence"
            ][0]
            arguments = json.dumps(
                {
                    "draft": {
                        "title": "Verified news",
                        "items": [
                            {
                                "title": "Verified article",
                                "summary": (
                                    "Rick's evidence-based summary cut mid"
                                    if unfinished_summary
                                    and self.responses == 1
                                    else "Rick's evidence-based summary. 🧪"
                                ),
                                "evidence_ids": [evidence["id"]],
                            }
                        ],
                    }
                }
            )
            duplicate = parallel_reply and self.responses == 1
            if self.responses == 2:
                if parallel_reply:
                    feedback = history.messages[-2:]
                    assert all(item.role == "tool" for item in feedback)
                    assert all(
                        "one tool call" in item.content for item in feedback
                    )
                else:
                    feedback = history.messages[-1]
                    assert feedback.role == "tool"
                    assert "complete sentence" in (feedback.content or "")
            return LLMReply(
                message=AgentMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id=f"call-{self.responses}-{index}",
                            function=ToolFunction(
                                name="create_post_draft", arguments=arguments
                            ),
                        )
                        for index in range(2 if duplicate else 1)
                    ],
                ),
                input_tokens=100,
                output_tokens=100,
                cost_usd="0",
            )

    external = ExternalLLM()

    class ExternalProvider(Provider):
        @provide(scope=Scope.REQUEST, provides=ILLMClient, override=True)
        def llm(self) -> ExternalLLM:
            return external

    async def workflow():
        snapshot = await portal.snapshot()
        ai = snapshot.configuration.ai.model_dump(mode="json")
        ai.update(
            mode="openrouter",
            model="external-test-model",
            input_usd_per_million="0",
            output_usd_per_million="0",
        )
        await portal.change("ai.model", SettingScope.GLOBAL, ai)
        automation = snapshot.configuration.automation.model_dump(mode="json")
        automation["owner_id"] = OWNER
        automation["news"].update(
            enabled=True,
            starts_at=(utc_now() + timedelta(days=1)).isoformat(),
        )
        await portal.change(
            "automation.policy", SettingScope.GLOBAL, automation
        )
        stamp = utc_now()
        slot = int(stamp.timestamp() * 1_000_000)
        async with portal.request() as scope:
            await (await scope.get(IMissionService)).create_scheduled(
                ScheduledMissionCreate(
                    owner_id=OWNER,
                    role=BotRole.RICK,
                    intent="news",
                    text="Create one verified news draft.",
                    scheduled_at=stamp,
                )
            )
        async with portal.request() as scope:
            repository = await scope.get(MissionRepository)
            mission = await repository.by_update(-1, slot)
            mission_id = mission.id
            async with transaction():
                await (await scope.get(ArticleRepository)).save_many(
                    [
                        ArticleModel(
                            mission_id=mission_id,
                            source_id="hackernews",
                            url="https://news.ycombinator.com/item?id=1",
                            title="Verified article",
                            body="Recorded article evidence. " * 20,
                            fetched_at=stamp,
                            content_hash="a" * 64,
                            url_hash="b" * 64,
                        )
                    ]
                )
                await repository.change(
                    mission_id, MissionChange(status="queued", stage="model")
                )
        container = make_async_container(
            *task_providers(portal.settings), ExternalProvider()
        )
        try:
            async with container() as scope:
                await (await scope.get(IMissionExecutor)).execute(mission_id)
            if parallel_reply or unfinished_summary:
                async with portal.request() as scope:
                    mission = await (await scope.get(MissionRepository)).get(
                        mission_id
                    )
                    assert mission.status == "queued", mission.failure_reason
                    assert mission.stage == "model"
                    assert mission.tool_executions == 0
                    checkpoint = await (
                        await scope.get(CheckpointRepository)
                    ).get(mission_id)
                    assert checkpoint.tools == int(unfinished_summary)
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
            rows = await (await scope.get(PublicationRepository)).due(
                utc_now(), 20
            )
            assert len(rows) == 1
            return rows[0].id

    publication_id = portal.run(workflow())
    portal.start_workers()

    async def publication():
        async with portal.request() as scope:
            row = await (await scope.get(PublicationRepository)).get(
                publication_id
            )
            if row.status == "sent":
                published = await (
                    await scope.get(ArticleRepository)
                ).published_url_hashes()
                assert "b" * 64 in published
            return row.status, row.message_id

    result = portal.until(publication, lambda row: row[0] == "sent")
    assert result[1] is not None
    assert len(ExternalTelegramHandler.messages) == 1
    text = unescape(ExternalTelegramHandler.messages[0]["text"])
    assert "Rick's evidence-based summary" in text
    assert "https://news.ycombinator.com/item?id=1" in text
    assert "برداشت ریک" not in text
    assert "منبع:" in text
    assert "🧪🚀 ریک | پورتال خبرهای کد و AI" in text
