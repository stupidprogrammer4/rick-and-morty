"""Disposable bot history, with explicit dependency-ordered deletion."""

from datetime import datetime

from papilio.infra.db.tools.decorators import transactional
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import delete, func, inspect, select
from sqlmodel import SQLModel

from src.modules.automation.agents.infra.tables import (
    AgentCheckpointTable,
    AIBudgetTable,
    LLMRunTable,
)
from src.modules.automation.missions.infra.tables import (
    MissionEventTable,
    MissionTable,
)
from src.modules.content.drafts.infra.tables import (
    DraftEvidenceTable,
    DraftTable,
)
from src.modules.content.news.infra.tables import ArticleTable
from src.modules.content.publications.infra.tables import (
    PublicationChartTable,
    PublicationTable,
)
from src.modules.content.replies.infra.tables import PrivateReplyTable
from src.modules.pricing.reports.infra.tables import MarketSnapshotTable

# Seed catalogues, definitions, credentials, policies and guards are excluded.
HISTORY_TABLES = (
    MissionTable,
    DraftTable,
    MarketSnapshotTable,
    PublicationTable,
    PublicationChartTable,
    ArticleTable,
    DraftEvidenceTable,
    MissionEventTable,
    LLMRunTable,
    PrivateReplyTable,
)
DEPENDENCIES: dict[type[SQLModel], tuple[tuple[type[SQLModel], str], ...]] = {
    MissionTable: (
        (DraftTable, "mission_id"),
        (MarketSnapshotTable, "mission_id"),
        (ArticleTable, "mission_id"),
        (PrivateReplyTable, "mission_id"),
        (MissionEventTable, "mission_id"),
        (LLMRunTable, "mission_id"),
        (AgentCheckpointTable, "mission_id"),
    ),
    MarketSnapshotTable: ((DraftTable, "market_snapshot_id"),),
    DraftTable: (
        (PublicationTable, "draft_id"),
        (DraftEvidenceTable, "draft_id"),
        (PrivateReplyTable, "draft_id"),
    ),
    ArticleTable: ((DraftEvidenceTable, "article_id"),),
    PublicationTable: ((PublicationChartTable, "publication_id"),),
}


class BotHistoryStore:
    def __init__(self, uow: MySQLUnitOfWork):
        self.uow = uow

    async def expired_counts(self, cutoff: datetime) -> dict[str, int]:
        counts = {}
        for table in HISTORY_TABLES:
            columns = inspect(table).columns
            result = await self.uow.execute(
                select(func.count())
                .select_from(table)
                .where(columns.created_at < cutoff)
            )
            counts[str(table.__tablename__)] = result.scalar_one()
        return counts

    async def _delete_tree(
        self, table: type[SQLModel], identifiers: list[int], removed: dict
    ) -> None:
        if not identifiers:
            return
        for child, foreign_key in DEPENDENCIES.get(table, ()):
            columns = inspect(child).columns
            key = next(iter(inspect(child).primary_key))
            rows = await self.uow.execute(
                select(key)
                .where(columns[foreign_key].in_(identifiers))
                .with_for_update()
            )
            await self._delete_tree(child, list(rows.scalars()), removed)
        key = next(iter(inspect(table).primary_key))
        await self.uow.execute(
            delete(table)
            .where(key.in_(identifiers))
            .execution_options(synchronize_session=False)
        )
        name = str(table.__tablename__)
        removed[name] = removed.get(name, 0) + len(identifiers)

    @transactional
    async def prune_batch(
        self, table: type[SQLModel], cutoff: datetime, batch_size: int
    ) -> tuple[int, dict[str, int]]:
        if table not in HISTORY_TABLES or not 1 <= batch_size <= 1000:
            raise ValueError("Only bounded bot history batches may be pruned")
        columns = inspect(table).columns
        result = await self.uow.execute(
            select(columns.id)
            .where(columns.created_at < cutoff)
            .order_by(columns.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        identifiers = list(result.scalars())
        removed = {}
        await self._delete_tree(table, identifiers, removed)
        return len(identifiers), removed

    @transactional
    async def prune_budgets(self, now: datetime) -> int:
        columns = inspect(AIBudgetTable).columns
        result = await self.uow.execute(
            select(columns.day)
            .where(columns.day < now.date())
            .limit(1000)
            .with_for_update(skip_locked=True)
        )
        days = list(result.scalars())
        if days:
            await self.uow.execute(
                delete(AIBudgetTable)
                .where(columns.day.in_(days))
                .execution_options(synchronize_session=False)
            )
        return len(days)
