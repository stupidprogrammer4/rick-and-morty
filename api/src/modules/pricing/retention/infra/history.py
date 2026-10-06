"""A strict allowlist of disposable pricing time series, never bot audit."""

from dataclasses import dataclass

from papilio.infra.db.tools.decorators import transactional
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import delete, func, inspect, select
from sqlmodel import SQLModel

from src.modules.pricing.candle.infra.tables import (
    CandleTable,
    SourceCandleTable,
)
from src.modules.pricing.ticker.infra.tables import (
    BubbleTickerTable,
    PriceTickerTable,
    SourceBubbleTickerTable,
    SourcePriceTickerTable,
)


@dataclass(frozen=True)
class HistoryTarget:
    table: type[SQLModel]
    clock_column: str

    @property
    def name(self) -> str:
        return str(self.table.__tablename__)


HISTORY_TARGETS = (
    HistoryTarget(PriceTickerTable, "timestamp"),
    HistoryTarget(SourcePriceTickerTable, "timestamp"),
    HistoryTarget(BubbleTickerTable, "timestamp"),
    HistoryTarget(SourceBubbleTickerTable, "timestamp"),
    # Start time excludes aggregates containing observations older than 24h.
    HistoryTarget(CandleTable, "st_ts"),
    HistoryTarget(SourceCandleTable, "st_ts"),
)


class PricingHistoryStore:
    def __init__(self, uow: MySQLUnitOfWork):
        self.uow = uow

    async def expired_counts(self, cutoff: int) -> dict[str, int]:
        counts = {}
        for target in HISTORY_TARGETS:
            clock = inspect(target.table).columns[target.clock_column]
            result = await self.uow.execute(
                select(func.count())
                .select_from(target.table)
                .where(clock < cutoff)
            )
            counts[target.name] = result.scalar_one()
        return counts

    @transactional
    async def prune_batch(
        self, target: HistoryTarget, cutoff: int, batch_size: int
    ) -> int:
        if target not in HISTORY_TARGETS:
            raise ValueError("Only pricing history tables may be pruned")
        if not 1 <= batch_size <= 10000:
            raise ValueError("Pricing cleanup batches must be 1..10000 rows")
        columns = inspect(target.table).columns
        result = await self.uow.execute(
            select(columns.id)
            .where(columns[target.clock_column] < cutoff)
            .order_by(columns.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        identifiers = result.scalars().all()
        if identifiers:
            await self.uow.execute(
                delete(target.table)
                .where(columns.id.in_(identifiers))
                .execution_options(synchronize_session=False)
            )
        return len(identifiers)
