import asyncio

import pytest
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import select

from portal_contracts.content import DraftCreate
from portal_contracts.enums import BotRole, Category
from src.modules.content.drafts.infra.tables import DraftTable
from src.modules.content.drafts.interfaces import IDraftService
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


def test_concurrent_empty_table_draft_creation_retains_idempotency(portal):
    async def create(key):
        async with portal.request() as scope:
            drafts = await scope.get(IDraftService)
            return await drafts.create(
                OWNER,
                BotRole.RICK,
                DraftCreate(
                    category=Category.TECH,
                    title=key,
                    text="Recorded draft",
                    publisher_bot=BotRole.RICK,
                ),
                key=key,
            )

    async def concurrent():
        first, second, replay = await asyncio.gather(
            create("first"), create("second"), create("first")
        )
        assert first.id == replay.id
        assert second.id != first.id
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            rows = (await uow.execute(select(DraftTable))).scalars().all()
            assert len(rows) == 2
            assert {row.idempotency_key for row in rows} == {"first", "second"}

    portal.run(concurrent())
