from typing import Sequence

from papilio.infra.db.repositories.backends.mysql import (
    MySQLPersistenceRepository,
)
from sqlalchemy import inspect
from sqlmodel import col, select

from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.domain.models import (
    CandleModel,
    SourceCandleModel,
)
from src.modules.pricing.candle.infra.tables import (
    CandleTable,
    SourceCandleTable,
)


class CandleRepository(MySQLPersistenceRepository[CandleModel]):
    table = CandleTable

    async def upsert_candles(
        self,
        candles: Sequence[CandleModel],
    ) -> Sequence[CandleModel]:
        """
        Desc: Write candles down, rewriting the ones already written.
        Args:
            candles (Sequence[CandleTable]): The candles to write.
        Returns:
            return (Sequence[CandleModel]): The written candles.
        """
        if not candles:
            return []
        fields = candles[0].to_row()
        keys = [
            inspect(CandleTable).columns.asset_id,
            inspect(CandleTable).columns.timeframe,
            inspect(CandleTable).columns.st_ts,
        ]
        await self.bulk_upsert(
            candles,
            insert_columns={
                name: inspect(CandleTable).columns[name] for name in fields
            },
            update_columns=[
                inspect(CandleTable).columns[name]
                for name in fields
                if name not in {field.key for field in keys}
            ]
            or keys,
        )
        return candles

    async def get_by_timeframe(
        self,
        asset_id: int,
        timeframe: TimeFrame,
        from_ts: int,
        to_ts: int,
    ) -> Sequence[CandleModel]:
        """
        Desc: Read one asset's candles of one timeframe over a range.
        Args:
            asset_id (int): ID of the asset being charted.
            timeframe (TimeFrame): The timeframe the candles are cut on.
            from_ts (int): The moment the range opens at, included.
            to_ts (int): The moment the range closes at, excluded.
        Returns:
            return (Sequence[CandleModel]): The candles, oldest first.
        """
        stamp = col(CandleTable.st_ts)
        stmt = (
            select(CandleTable)
            .where(
                col(CandleTable.asset_id) == asset_id,
                col(CandleTable.timeframe) == timeframe,
                stamp >= from_ts,
                stamp < to_ts,
            )
            .order_by(stamp)
        )
        result = await self.uow.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_all_by_timeframe(
        self,
        timeframe: TimeFrame,
        from_ts: int,
        to_ts: int,
    ) -> Sequence[CandleModel]:
        """
        Desc: Read every asset's candles of one timeframe over a range.
        Args:
            timeframe (TimeFrame): The timeframe the candles are cut on.
            from_ts (int): The moment the range opens at, included.
            to_ts (int): The moment the range closes at, excluded.
        Returns:
            return (Sequence[CandleModel]): The candles, grouped by asset,
                oldest first within each.
        """
        stamp = col(CandleTable.st_ts)
        asset = col(CandleTable.asset_id)
        stmt = (
            select(CandleTable)
            .where(
                col(CandleTable.timeframe) == timeframe,
                stamp >= from_ts,
                stamp < to_ts,
            )
            .order_by(asset, stamp)
        )
        result = await self.uow.execute(stmt)
        rows = result.scalars().all()
        return rows


class SourceCandleRepository(MySQLPersistenceRepository[SourceCandleModel]):
    table = SourceCandleTable

    async def upsert_candles(
        self,
        candles: Sequence[SourceCandleModel],
    ) -> Sequence[SourceCandleModel]:
        """
        Desc: Write source candles down, rewriting the written ones.
        Args:
            candles (Sequence[SourceCandleTable]): The candles to write.
        Returns:
            return (Sequence[SourceCandleModel]): The written candles.
        """
        if not candles:
            return []
        fields = candles[0].to_row()
        keys = [
            inspect(SourceCandleTable).columns.symbol_id,
            inspect(SourceCandleTable).columns.source_id,
            inspect(SourceCandleTable).columns.timeframe,
            inspect(SourceCandleTable).columns.st_ts,
        ]
        await self.bulk_upsert(
            candles,
            insert_columns={
                name: inspect(SourceCandleTable).columns[name]
                for name in fields
            },
            update_columns=[
                inspect(SourceCandleTable).columns[name]
                for name in fields
                if name not in {field.key for field in keys}
            ]
            or keys,
        )
        return candles

    async def get_by_timeframe(
        self,
        source_id: int,
        symbol_id: int,
        timeframe: TimeFrame,
        from_ts: int,
        to_ts: int,
    ) -> Sequence[SourceCandleModel]:
        """
        Desc: Read what one source quoted one line at, candle by candle.
        Args:
            source_id (int): ID of the source that quoted it.
            symbol_id (int): ID of the line being charted.
            timeframe (TimeFrame): The timeframe the candles are cut on.
            from_ts (int): The moment the range opens at, included.
            to_ts (int): The moment the range closes at, excluded.
        Returns:
            return (Sequence[SourceCandleModel]): The candles, oldest
                first.
        """
        stamp = col(SourceCandleTable.st_ts)
        stmt = (
            select(SourceCandleTable)
            .where(
                col(SourceCandleTable.source_id) == source_id,
                col(SourceCandleTable.symbol_id) == symbol_id,
                col(SourceCandleTable.timeframe) == timeframe,
                stamp >= from_ts,
                stamp < to_ts,
            )
            .order_by(stamp)
        )
        result = await self.uow.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_all_by_timeframe(
        self,
        timeframe: TimeFrame,
        from_ts: int,
        to_ts: int,
    ) -> Sequence[SourceCandleModel]:
        """
        Desc: Read every source's candles of one timeframe over a range.
        Args:
            timeframe (TimeFrame): The timeframe the candles are cut on.
            from_ts (int): The moment the range opens at, included.
            to_ts (int): The moment the range closes at, excluded.
        Returns:
            return (Sequence[SourceCandleModel]): The candles, grouped by
                source and line, oldest first within each.
        """
        stamp = col(SourceCandleTable.st_ts)
        source = col(SourceCandleTable.source_id)
        symbol = col(SourceCandleTable.symbol_id)
        stmt = (
            select(SourceCandleTable)
            .where(
                col(SourceCandleTable.timeframe) == timeframe,
                stamp >= from_ts,
                stamp < to_ts,
            )
            .order_by(source, symbol, stamp)
        )
        result = await self.uow.execute(stmt)
        rows = result.scalars().all()
        return rows
