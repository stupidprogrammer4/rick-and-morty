from datetime import date
from decimal import Decimal

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from src.modules.rick.domain.models import (
    AgentCheckpointModel,
    AIBudgetModel,
    LLMRunModel,
)
from src.modules.rick.infra.tables import (
    AgentCheckpointTable,
    AIBudgetTable,
    LLMRunTable,
)


class CheckpointRepository(MySQLRepository[AgentCheckpointModel]):
    table = AgentCheckpointTable

    async def get(self, mission_id: int) -> AgentCheckpointModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.mission_id) == mission_id)
        )
        return result.scalar_one_or_none()

    async def save(self, data: AgentCheckpointModel) -> None:
        stmt = insert(self.table).values(**data.to_row(exclude_unset=False))
        await self.uow.execute(
            stmt.on_duplicate_key_update(
                history=stmt.inserted.history,
                requests=stmt.inserted.requests,
                tools=stmt.inserted.tools,
                reactions=stmt.inserted.reactions,
                input_tokens=stmt.inserted.input_tokens,
            )
        )


class AIBudgetRepository(MySQLRepository[AIBudgetModel]):
    table = AIBudgetTable

    async def lock(self, day: date) -> AIBudgetModel:
        stmt = insert(self.table).values(day=day, reserved_usd=Decimal("0"))
        await self.uow.execute(
            stmt.on_duplicate_key_update(day=stmt.inserted.day)
        )
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.day) == day)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def adjust(self, day: date, delta: Decimal) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.day) == day)
            .values(reserved_usd=col(self.table.reserved_usd) + delta)
        )


class LLMRunRepository(MySQLRepository[LLMRunModel]):
    table = LLMRunTable

    async def save(self, row: LLMRunModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == row.id)
            .values(**row.model_dump(exclude={"id", "created_at"}))
        )
