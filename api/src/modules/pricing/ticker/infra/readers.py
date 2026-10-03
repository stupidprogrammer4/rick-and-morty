from typing import Sequence

from papilio.infra.db.repositories.backends.mysql import (
    MySQLReader,
)
from sqlalchemy import select
from sqlmodel import col

from src.modules.pricing.ticker.domain.models import (
    AssetPointReadModel,
    SourceBubblePointReadModel,
    SourcePricePointReadModel,
)
from src.modules.pricing.ticker.infra.tables import (
    BubbleTickerTable,
    PriceTickerTable,
    SourceBubbleTickerTable,
    SourcePriceTickerTable,
)


class PriceTickerReader(MySQLReader):
    async def get_latest_by_asset_since_per_bucket(
        self, asset_id: int, since: int, step: int
    ) -> Sequence[AssetPointReadModel]:
        """
        Desc: Read one asset's points over a chart's window, the last of
        each step.
        Args:
            asset_id (int): ID of the asset being charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[AssetPointReadModel]): The points, oldest first.
        """
        stamp = col(PriceTickerTable.timestamp)
        bucket = stamp - stamp % step
        stmt = (
            select(
                col(PriceTickerTable.asset_id),
                col(PriceTickerTable.price),
                col(PriceTickerTable.timestamp),
            )
            .distinct(bucket)
            .where(
                col(PriceTickerTable.asset_id) == asset_id,
                col(PriceTickerTable.timestamp) >= since,
            )
            .order_by(bucket, col(PriceTickerTable.timestamp).desc())
        )
        result = await self.uow.execute(stmt)
        return [
            AssetPointReadModel.model_validate(row)
            for row in result.mappings()
        ]


class BubbleTickerReader(MySQLReader):
    async def get_latest_by_asset_since_per_bucket(
        self, asset_id: int, since: int, step: int
    ) -> Sequence[AssetPointReadModel]:
        """
        Desc: Read one asset's premiums over a chart's window, the last of
        each step.
        Args:
            asset_id (int): ID of the asset whose premium is charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[AssetPointReadModel]): The points, oldest first.
        """
        stamp = col(BubbleTickerTable.timestamp)
        bucket = stamp - stamp % step
        stmt = (
            select(
                col(BubbleTickerTable.asset_id),
                col(BubbleTickerTable.price),
                col(BubbleTickerTable.timestamp),
            )
            .distinct(bucket)
            .where(
                col(BubbleTickerTable.asset_id) == asset_id,
                col(BubbleTickerTable.timestamp) >= since,
            )
            .order_by(bucket, col(BubbleTickerTable.timestamp).desc())
        )
        result = await self.uow.execute(stmt)
        return [
            AssetPointReadModel.model_validate(row)
            for row in result.mappings()
        ]


class SourcePriceTickerReader(MySQLReader):
    async def get_latest_by_source_symbol_since_per_bucket(
        self,
        source_id: int,
        symbol_id: int,
        since: int,
        step: int,
    ) -> Sequence[SourcePricePointReadModel]:
        """
        Desc: Read what one source quoted one line at over a chart's
        window, the last of each step.
        Args:
            source_id (int): ID of the source that quoted it.
            symbol_id (int): ID of the line being charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[SourcePricePointReadModel]): The points, oldest
                first.
        """
        stamp = col(SourcePriceTickerTable.timestamp)
        bucket = stamp - stamp % step
        stmt = (
            select(
                col(SourcePriceTickerTable.source_id),
                col(SourcePriceTickerTable.symbol_id),
                col(SourcePriceTickerTable.price),
                col(SourcePriceTickerTable.timestamp),
            )
            .distinct(bucket)
            .where(
                col(SourcePriceTickerTable.source_id) == source_id,
                col(SourcePriceTickerTable.symbol_id) == symbol_id,
                stamp >= since,
            )
            .order_by(bucket, stamp.desc())
        )
        result = await self.uow.execute(stmt)
        return [
            SourcePricePointReadModel.model_validate(row)
            for row in result.mappings()
        ]

    async def get_latest_by_symbol_since_per_bucket(
        self,
        symbol_id: int,
        since: int,
        step: int,
    ) -> Sequence[SourcePricePointReadModel]:
        """
        Desc: Read what every source quoted one line at over a chart's
        window, the last of each step of each source.
        Args:
            symbol_id (int): ID of the line being charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[SourcePricePointReadModel]): The points, grouped
                by source, oldest first within each.
        """
        stamp = col(SourcePriceTickerTable.timestamp)
        bucket = stamp - stamp % step
        source = col(SourcePriceTickerTable.source_id)
        stmt = (
            select(
                col(SourcePriceTickerTable.source_id),
                col(SourcePriceTickerTable.symbol_id),
                col(SourcePriceTickerTable.price),
                col(SourcePriceTickerTable.timestamp),
            )
            .distinct(source, bucket)
            .where(
                col(SourcePriceTickerTable.symbol_id) == symbol_id,
                stamp >= since,
            )
            .order_by(source, bucket, stamp.desc())
        )
        result = await self.uow.execute(stmt)
        return [
            SourcePricePointReadModel.model_validate(row)
            for row in result.mappings()
        ]


class SourceBubbleTickerReader(MySQLReader):
    async def get_latest_by_asset_since_per_bucket(
        self, asset_id: int, since: int, step: int
    ) -> Sequence[SourceBubblePointReadModel]:
        """
        Desc: Read every source's premiums on one asset over a chart's
        window, the last of each step per source.
        Args:
            asset_id (int): ID of the asset being charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[SourceBubblePointReadModel]): The points, by
                source and oldest first.
        """
        stamp = col(SourceBubbleTickerTable.timestamp)
        bucket = stamp - stamp % step
        source = col(SourceBubbleTickerTable.source_id)
        stmt = (
            select(
                col(SourceBubbleTickerTable.source_id),
                col(SourceBubbleTickerTable.asset_id),
                col(SourceBubbleTickerTable.price),
                col(SourceBubbleTickerTable.timestamp),
            )
            .distinct(source, bucket)
            .where(
                col(SourceBubbleTickerTable.asset_id) == asset_id,
                stamp >= since,
            )
            .order_by(source, bucket, stamp.desc())
        )
        result = await self.uow.execute(stmt)
        return [
            SourceBubblePointReadModel.model_validate(row)
            for row in result.mappings()
        ]

    async def get_latest_by_source_asset_since_per_bucket(
        self,
        source_id: int,
        asset_id: int,
        since: int,
        step: int,
    ) -> Sequence[SourceBubblePointReadModel]:
        """
        Desc: Read one source's premiums on one asset over a chart's
        window, the last of each step.
        Args:
            source_id (int): ID of the source that published them.
            asset_id (int): ID of the asset being charted.
            since (int): Inclusive lower timestamp bound.
            step (int): SQL bucket width in seconds.
        Returns:
            return (Sequence[SourceBubblePointReadModel]): The points, oldest
                first.
        """
        stamp = col(SourceBubbleTickerTable.timestamp)
        bucket = stamp - stamp % step
        stmt = (
            select(
                col(SourceBubbleTickerTable.source_id),
                col(SourceBubbleTickerTable.asset_id),
                col(SourceBubbleTickerTable.price),
                col(SourceBubbleTickerTable.timestamp),
            )
            .distinct(bucket)
            .where(
                col(SourceBubbleTickerTable.source_id) == source_id,
                col(SourceBubbleTickerTable.asset_id) == asset_id,
                stamp >= since,
            )
            .order_by(bucket, stamp.desc())
        )
        result = await self.uow.execute(stmt)
        return [
            SourceBubblePointReadModel.model_validate(row)
            for row in result.mappings()
        ]
