from datetime import date

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import func, select, text
from sqlmodel import col

from src.modules.missions.infra.tables import MissionTable
from src.modules.ops.domain.dtos import QueueStatus
from src.modules.publishing.infra.tables import (
    PrivateReplyTable,
    PublicationTable,
)
from src.modules.rick.infra.tables import AIBudgetTable


class DatabaseHealthReader(MySQLReader):
    async def available(self) -> bool:
        result = await self.uow.execute(text("SELECT 1"))
        return result.scalar_one() == 1


class QueueStatusReader(MySQLReader):
    async def read(self, day: date) -> QueueStatus:
        result = await self.uow.execute(
            select(
                select(func.count())
                .select_from(MissionTable)
                .where(col(MissionTable.status) == "queued")
                .scalar_subquery()
                .label("queued_missions"),
                select(func.count())
                .select_from(MissionTable)
                .where(col(MissionTable.status) == "running")
                .scalar_subquery()
                .label("running_missions"),
                select(func.count())
                .select_from(PublicationTable)
                .where(col(PublicationTable.status) == "queued")
                .scalar_subquery()
                .label("queued_publications"),
                select(func.count())
                .select_from(PublicationTable)
                .where(col(PublicationTable.status) == "unknown")
                .scalar_subquery()
                .label("unknown_publications"),
                select(func.count())
                .select_from(PrivateReplyTable)
                .where(col(PrivateReplyTable.status) == "unknown")
                .scalar_subquery()
                .label("unknown_private_replies"),
                select(func.min(col(MissionTable.created_at)))
                .where(col(MissionTable.status) == "queued")
                .scalar_subquery()
                .label("oldest_queued_mission"),
                func.coalesce(
                    select(col(AIBudgetTable.reserved_usd))
                    .where(col(AIBudgetTable.day) == day)
                    .scalar_subquery(),
                    0,
                ).label("ai_reserved_usd"),
            )
        )
        return QueueStatus.model_validate(result.mappings().one())
