import asyncio
import json
from pathlib import Path

import pytest
from papilio.errors.exceptions import ConflictException

from portal_contracts.configuration import SettingScope, SettingValueWrite
from portal_contracts.content import (
    DraftCreate,
    DraftDecision,
    DraftEdit,
    PublicationResolution,
    PublishRequest,
)
from portal_contracts.enums import Actor, BotRole, Category, Intent
from portal_contracts.missions import MissionCreate
from src.modules.automation.missions.interfaces import (
    IMissionAdmission,
    IMissionService,
)
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.content.publications.interfaces import IPublicationCommands
from src.modules.ops.settings.domain.dtos import ConfigurationSeed
from src.modules.ops.settings.interfaces import (
    IConfigurationCommands,
    ISettingValueService,
)

OWNER = 140001
pytestmark = pytest.mark.integration


def test_edit_revoke_and_stale_approval(portal):
    async def workflow():
        async with portal.request() as request:
            drafts = await request.get(IDraftService)
            draft = await drafts.create(
                OWNER,
                BotRole.RICK,
                DraftCreate(
                    category=Category.TECH,
                    title="Test",
                    text="Review me",
                    publisher_bot=BotRole.RICK,
                ),
                key="test-edit",
            )
            await drafts.decide(
                draft.id,
                OWNER,
                DraftDecision(
                    revision=1,
                    origin_bot=BotRole.RICK,
                ),
                approve=True,
            )
        async with portal.request() as request:
            drafts = await request.get(IDraftService)
            edited = await drafts.edit(
                draft.id,
                OWNER,
                DraftEdit(
                    revision=1,
                    title="Updated",
                    text="Review again",
                ),
            )
            assert edited.status == "draft"
            assert edited.revision == 2
        async with portal.request() as request:
            publications = await request.get(IPublicationCommands)
            with pytest.raises(ConflictException):
                await publications.schedule(
                    draft.id,
                    OWNER,
                    PublishRequest(
                        revision=1,
                        origin_bot=BotRole.RICK,
                    ),
                )
        async with portal.request() as request:
            drafts = await request.get(IDraftService)
            saved = await drafts.get(draft.id, OWNER)
            assert saved.text == "Review again"
            assert saved.status == "draft"

    portal.run(workflow())


def test_seed_preserves_edited_prompt_and_revision_conflict(portal):
    async def workflow():
        async with portal.request() as request:
            values = await request.get(ISettingValueService)
            original = await values.get("voice", SettingScope.RICK)
            voice = json.loads(original.value)
            voice["welcome"] = "Changed database greeting 🧪"
            await values.write(
                "voice",
                SettingScope.RICK,
                SettingValueWrite(
                    value=json.dumps(voice),
                    revision=original.revision,
                ),
            )
        async with portal.request() as request:
            commands = await request.get(IConfigurationCommands)
            await commands.seed(
                ConfigurationSeed.model_validate_json(
                    Path("api/seeds/defaults.json").read_text()
                )
            )
        async with portal.request() as request:
            values = await request.get(ISettingValueService)
            saved = await values.get("voice", SettingScope.RICK)
            assert saved.revision == original.revision + 1
            assert json.loads(saved.value)["welcome"] == voice["welcome"]
            with pytest.raises(ConflictException):
                await values.write(
                    "voice",
                    SettingScope.RICK,
                    SettingValueWrite(
                        value=original.value,
                        revision=original.revision,
                    ),
                )
        snapshot = await portal.snapshot()
        assert (
            snapshot.presentation.voices[BotRole.RICK].welcome
            == voice["welcome"]
        )

    portal.run(workflow())


def test_concurrent_updates_are_deduplicated_and_concurrency_is_bounded(
    portal,
):
    data = MissionCreate(
        owner_id=OWNER,
        origin_chat_id=OWNER,
        origin_bot=BotRole.RICK,
        origin_message_id=1,
        bot_id=140001,
        update_id=1,
        actor=Actor.RICK,
        intent=Intent.CHAT,
        text="Hello",
    )

    async def accept(item):
        async with portal.request() as request:
            service = await request.get(IMissionAdmission)
            result = await service.accept(item)
        return result

    async def together():
        results = await asyncio.gather(accept(data), accept(data))
        assert len({item.mission.id for item in results}) == 1
        assert sorted(item.duplicate for item in results) == [False, True]
        await accept(data.model_copy(update={"update_id": 2}))
        with pytest.raises(ConflictException):
            await accept(data.model_copy(update={"update_id": 3}))

    portal.run(together())


def test_native_scheduler_queue_worker_and_private_delivery(portal):
    async def prepare():
        snapshot = await portal.snapshot()
        ai = snapshot.configuration.ai.model_dump(mode="json")
        ai["mode"] = "fake"
        await portal.change("ai.model", SettingScope.GLOBAL, ai)
        async with portal.request() as request:
            admission = await request.get(IMissionAdmission)
            accepted = await admission.accept(
                MissionCreate(
                    owner_id=OWNER,
                    origin_chat_id=OWNER,
                    origin_bot=BotRole.MORTY,
                    origin_message_id=1,
                    bot_id=140002,
                    update_id=1,
                    actor=Actor.MORTY,
                    intent=Intent.CHAT,
                    text="Hello through the actual worker",
                )
            )
        return accepted.mission.id

    mission_id = portal.run(prepare())
    portal.start_workers()

    async def read():
        async with portal.request() as request:
            missions = await request.get(IMissionService)
            result = await missions.get(mission_id, OWNER)
        return result

    result = portal.until(read, lambda item: item.status == "completed")
    assert "[آزمایشی]" in result.result

    async def reply():
        from papilio.infra.db.uow import MySQLUnitOfWork
        from sqlalchemy import select

        from src.modules.content.replies.infra.tables import PrivateReplyTable

        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            rows = await unit.execute(
                select(PrivateReplyTable).where(
                    PrivateReplyTable.mission_id == mission_id
                )
            )
            row = rows.scalar_one_or_none()
            return row.status if row else None

    assert portal.until(reply, lambda item: item == "sent") == "sent"
    from tests.integration.conftest import ExternalTelegramHandler

    sent = ExternalTelegramHandler.messages
    assert len(sent) == 1
    assert sent[0]["role"] == "morty"
    assert sent[0]["chat_id"] == OWNER


async def approved_publication(portal, key):
    async with portal.request() as request:
        drafts = await request.get(IDraftService)
        draft = await drafts.create(
            OWNER,
            BotRole.RICK,
            DraftCreate(
                category=Category.TECH,
                title="Reviewed post",
                text="An approved publication through the real database.",
                publisher_bot=BotRole.RICK,
            ),
            key=key,
        )
        await drafts.decide(
            draft.id,
            OWNER,
            DraftDecision(revision=1, origin_bot=BotRole.RICK),
            approve=True,
        )
    async with portal.request() as request:
        publications = await request.get(IPublicationCommands)
        result = await publications.schedule(
            draft.id,
            OWNER,
            PublishRequest(revision=1, origin_bot=BotRole.RICK),
        )
    return result


async def dispatch_publication(portal, id):
    async with portal.request() as request:
        publications = await request.get(IPublicationCommands)
        await publications.dispatch(id)


async def publication_status(portal, id):
    from src.modules.content.publications.infra.mysql import (
        PublicationRepository,
    )

    async with portal.request() as request:
        repo = await request.get(PublicationRepository)
        row = await repo.get(id)
        return row.status


def test_concurrent_publication_uses_one_shared_daily_slot(portal):
    from tests.integration.conftest import ExternalTelegramHandler

    portal.settings.portal.dry_run = False

    async def workflow():
        first = await approved_publication(portal, "quota-first")
        second = await approved_publication(portal, "quota-second")
        await asyncio.gather(
            dispatch_publication(portal, first.id),
            dispatch_publication(portal, second.id),
        )
        statuses = await asyncio.gather(
            publication_status(portal, first.id),
            publication_status(portal, second.id),
        )
        assert sorted(statuses) == ["queued", "sent"]

    portal.run(workflow())
    assert len(ExternalTelegramHandler.messages) == 1
    assert ExternalTelegramHandler.messages[0]["chat_id"] == -100140001


def test_large_unicode_evidence_checkpoint_round_trip(portal):
    from papilio.infra.db.transaction import transaction

    from src.modules.automation.agents.domain.dtos import (
        AgentHistory,
        AgentMessage,
    )
    from src.modules.automation.agents.domain.models import (
        AgentCheckpointModel,
    )
    from src.modules.automation.agents.infra.mysql import CheckpointRepository

    history = AgentHistory(
        messages=[AgentMessage(role="tool", content="متن مقاله 🧪" * 6000)]
    ).model_dump_json()
    assert len(history.encode()) > 65535

    async def workflow():
        async with portal.request() as request:
            admission = await request.get(IMissionAdmission)
            accepted = await admission.accept(
                MissionCreate(
                    owner_id=OWNER,
                    origin_chat_id=OWNER,
                    origin_bot=BotRole.RICK,
                    origin_message_id=1,
                    bot_id=140001,
                    update_id=1,
                    actor=Actor.RICK,
                    intent=Intent.CHAT,
                    text="Checkpoint storage",
                )
            )
            repo = await request.get(CheckpointRepository)
            async with transaction():
                await repo.save(
                    AgentCheckpointModel(
                        mission_id=accepted.mission.id, history=history
                    )
                )
        async with portal.request() as request:
            repo = await request.get(CheckpointRepository)
            saved = await repo.get(accepted.mission.id)
            assert saved is not None
            assert saved.history == history

    portal.run(workflow())


def test_unknown_delivery_is_not_replayed_and_owner_resolves(portal):
    from tests.integration.conftest import ExternalTelegramHandler

    portal.settings.portal.dry_run = False
    ExternalTelegramHandler.delivery_status = "unknown"

    async def workflow():
        publication = await approved_publication(portal, "unknown-delivery")
        await dispatch_publication(portal, publication.id)
        assert (await publication_status(portal, publication.id)) == "unknown"
        await dispatch_publication(portal, publication.id)
        async with portal.request() as request:
            commands = await request.get(IPublicationCommands)
            resolved = await commands.resolve(
                publication.id,
                OWNER,
                PublicationResolution(message_id=321),
            )
            assert resolved.status == "sent"
        await dispatch_publication(portal, publication.id)
        assert (await publication_status(portal, publication.id)) == "sent"

    portal.run(workflow())
    assert len(ExternalTelegramHandler.messages) == 1
