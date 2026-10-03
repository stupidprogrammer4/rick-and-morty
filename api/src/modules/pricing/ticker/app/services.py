from collections import defaultdict

from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional
from papilio.utils import dates as date_utils
from sqlalchemy import inspect

from src.modules.pricing.assets.interfaces import IAssetMetaService
from src.modules.pricing.calculator.interfaces import (
    ICacheReaderService as IPriceCacheReaderService,
)
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService as IReadingCacheReaderService,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.interfaces import (
    ISourceMetaService,
    ISourceService,
)
from src.modules.pricing.symbols.domain.enums import CurrencyType
from src.modules.pricing.ticker.app.helpers import ChartBuilder
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import (
    BubbleTickerModel,
    PointOutputModel,
    PriceTickerModel,
    SourceBubbleTickerModel,
    SourceChartOutputModel,
    SourcePriceTickerModel,
)
from src.modules.pricing.ticker.domain.results import (
    BubbleTickerResult,
    PricedSourceModel,
    PriceTickerResult,
    SingleSourceBubbleResult,
    SingleSourcePriceResult,
    SourceBubbleModel,
)
from src.modules.pricing.ticker.infra.mysql import (
    BubbleTickerRepository,
    PriceTickerRepository,
    SourceBubbleTickerRepository,
    SourcePriceTickerRepository,
)
from src.modules.pricing.ticker.infra.readers import (
    BubbleTickerReader,
    PriceTickerReader,
    SourceBubbleTickerReader,
    SourcePriceTickerReader,
)


class PriceSnapshotService:
    def __init__(
        self,
        repo: PriceTickerRepository,
        prices: IPriceCacheReaderService,
    ) -> None:
        self.repo = repo
        self.prices = prices

    @handle_conflicts
    @transactional
    async def snapshot_all(self) -> bool:
        """
        Desc: Write down what every asset is priced at right now.
        Returns:
            return (bool): Whether anything was written.
        """
        priced = await self.prices.get_all_prices()
        rows = [
            PriceTickerModel(
                asset_id=price.asset_id,
                price=price.price,
                timestamp=int(price.priced_at.timestamp()),
            )
            for price in priced
            if price.price
        ]
        if rows:
            await self.repo.bulk_insert(
                rows,
                insert_columns={
                    name: inspect(self.repo.table).columns[name]
                    for name in rows[0].to_row()
                },
            )
        return bool(rows)


class SourcePriceSnapshotService:
    def __init__(
        self,
        repo: SourcePriceTickerRepository,
        readings: IReadingCacheReaderService,
    ) -> None:
        self.repo = repo
        self.readings = readings

    @handle_conflicts
    @transactional
    async def snapshot_all(self) -> bool:
        """
        Desc: Write down what every source last quoted, under the line it
        was quoted for.
        Returns:
            return (bool): Whether anything was written.
        """
        board = await self.readings.get_all()
        rows = [
            SourcePriceTickerModel(
                symbol_id=reading.symbol_id,
                source_id=reading.source_id,
                price=reading.price,
                timestamp=int(reading.priced_at.timestamp()),
            )
            for readings in board.values()
            for reading in readings
            if reading.price
        ]
        if rows:
            await self.repo.bulk_insert(
                rows,
                insert_columns={
                    name: inspect(self.repo.table).columns[name]
                    for name in rows[0].to_row()
                },
            )
        return bool(rows)


class PriceTickerService:
    def __init__(
        self,
        reader: PriceTickerReader,
        meta: IAssetMetaService,
    ) -> None:
        self.reader = reader
        self.meta = meta
        self.builder = ChartBuilder()

    async def get_chart(
        self,
        asset_id: int,
        type: ChartType,
    ) -> PriceTickerResult:
        """
        Desc: Draw one asset's chart, and say how far it moved over it.
        Args:
            asset_id (int): ID of the asset being charted.
            type (ChartType): The chart to draw.
        Returns:
            return (PriceTickerResult): The chart and the asset it is of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_asset_since_per_bucket(
            asset_id, since=now - type.span, step=type.step
        )
        data = self.builder.build(type, rows, now)
        meta = await self.meta.build(list({row.asset_id for row in rows}))
        return PriceTickerResult(data=data, meta=meta)


class BubbleSnapshotService:
    def __init__(
        self,
        repo: BubbleTickerRepository,
        prices: IPriceCacheReaderService,
    ) -> None:
        self.repo = repo
        self.prices = prices

    @handle_conflicts
    @transactional
    async def snapshot_all(self) -> bool:
        """
        Desc: Write down what every asset's premium stands at right now.
        Returns:
            return (bool): Whether anything was written.
        """
        settled = await self.prices.get_all_bubble_amounts()
        rows = [
            BubbleTickerModel(
                asset_id=bubble.asset_id,
                price=bubble.amount,
                timestamp=int(bubble.priced_at.timestamp()),
            )
            for bubble in settled
            if bubble.amount
        ]
        if rows:
            await self.repo.bulk_insert(
                rows,
                insert_columns={
                    name: inspect(self.repo.table).columns[name]
                    for name in rows[0].to_row()
                },
            )
        return bool(rows)


class BubbleTickerService:
    def __init__(
        self,
        reader: BubbleTickerReader,
        meta: IAssetMetaService,
    ) -> None:
        self.reader = reader
        self.meta = meta
        self.builder = ChartBuilder()

    async def get_chart(
        self,
        asset_id: int,
        type: ChartType,
    ) -> BubbleTickerResult:
        """
        Desc: Draw one asset's premium over time, and say how far it moved.
        Args:
            asset_id (int): ID of the asset whose premium is charted.
            type (ChartType): The chart to draw.
        Returns:
            return (BubbleTickerResult): The chart and the asset it is of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_asset_since_per_bucket(
            asset_id, since=now - type.span, step=type.step
        )
        data = self.builder.build(type, rows, now)
        meta = await self.meta.build(list({row.asset_id for row in rows}))
        return BubbleTickerResult(data=data, meta=meta)


class SourcePriceTickerService:
    def __init__(
        self,
        reader: SourcePriceTickerReader,
        sources: ISourceService,
        meta: ISourceMetaService,
    ) -> None:
        self.reader = reader
        self.sources = sources
        self.meta = meta
        self.builder = ChartBuilder()

    async def get_chart_by_symbol(
        self,
        symbol_id: int,
        type: ChartType,
    ) -> PricedSourceModel:
        """
        Desc: Draw one line as every source that quotes it saw it.
        Args:
            symbol_id (int): ID of the line being charted.
            type (ChartType): The chart to draw.
        Returns:
            return (PricedSourceModel): One series per source, and the
                sources and line they are of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_symbol_since_per_bucket(
            symbol_id, since=now - type.span, step=type.step
        )
        quoting = {row.source_id for row in rows}
        sources = await self.sources.get_by_ids(list(quoting))
        codes = {source.id: SourceCode(source.code) for source in sources}
        quoted: dict[SourceCode, list[PointOutputModel]] = defaultdict(list)
        for row in rows:
            code = codes.get(row.source_id)
            if code is not None:
                quoted[code].append(
                    PointOutputModel(price=row.price, timestamp=row.timestamp)
                )
        data = SourceChartOutputModel(
            type=type,
            points=[],
            from_timestamp=now - type.span,
            to_timestamp=now,
            source_points=quoted,
        )
        meta = await self.meta.build_by_sources(
            sources, list({row.symbol_id for row in rows})
        )
        return PricedSourceModel(data=data, meta=meta)

    async def get_source_chart_by_symbol(
        self,
        source_id: int,
        symbol_id: int,
        type: ChartType,
    ) -> SingleSourcePriceResult:
        """
        Desc: Draw one line as one source saw it, and say how far it moved.
        Args:
            source_id (int): ID of the source that quoted it.
            symbol_id (int): ID of the line being charted.
            type (ChartType): The chart to draw.
        Returns:
            return (SingleSourcePriceResult): The chart, and the source
                and line it is of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_source_symbol_since_per_bucket(
            source_id, symbol_id, since=now - type.span, step=type.step
        )
        charted = [source_id] if rows else []
        meta = await self.meta.build(
            charted, list({row.symbol_id for row in rows})
        )
        currency = (
            meta.symbols[0].currency if meta.symbols else CurrencyType.RIAL
        )
        data = self.builder.build(type, rows, now, currency)
        return SingleSourcePriceResult(data=data, meta=meta)


class SourceBubbleSnapshotService:
    def __init__(
        self,
        repo: SourceBubbleTickerRepository,
        readings: IReadingCacheReaderService,
    ) -> None:
        self.repo = repo
        self.readings = readings

    @handle_conflicts
    @transactional
    async def snapshot_all(self) -> bool:
        """
        Desc: Write down what every source last published as a premium,
        under the asset it was published for.
        Returns:
            return (bool): Whether anything was written.
        """
        board = await self.readings.get_all_bubbles()
        rows = [
            SourceBubbleTickerModel(
                asset_id=bubble.asset_id,
                source_id=bubble.source_id,
                price=bubble.amount,
                timestamp=int(bubble.priced_at.timestamp()),
            )
            for bubbles in board.values()
            for bubble in bubbles
            if bubble.amount
        ]
        if rows:
            await self.repo.bulk_insert(
                rows,
                insert_columns={
                    name: inspect(self.repo.table).columns[name]
                    for name in rows[0].to_row()
                },
            )
        return bool(rows)


class SourceBubbleTickerService:
    def __init__(
        self,
        reader: SourceBubbleTickerReader,
        sources: ISourceService,
        meta: ISourceMetaService,
    ) -> None:
        self.reader = reader
        self.sources = sources
        self.meta = meta
        self.builder = ChartBuilder()

    async def get_chart_by_asset(
        self,
        asset_id: int,
        type: ChartType,
    ) -> SourceBubbleModel:
        """
        Desc: Draw one asset's premium as every source that publishes it
        saw it.
        Args:
            asset_id (int): ID of the asset being charted.
            type (ChartType): The chart to draw.
        Returns:
            return (SourceBubbleModel): One series per source, and the
                sources they are of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_asset_since_per_bucket(
            asset_id, since=now - type.span, step=type.step
        )
        publishing = {row.source_id for row in rows}
        sources = await self.sources.get_by_ids(list(publishing))
        codes = {source.id: SourceCode(source.code) for source in sources}
        published: dict[SourceCode, list[PointOutputModel]] = defaultdict(list)
        for row in rows:
            code = codes.get(row.source_id)
            if code is not None:
                published[code].append(
                    PointOutputModel(price=row.price, timestamp=row.timestamp)
                )
        data = SourceChartOutputModel(
            type=type,
            points=[],
            from_timestamp=now - type.span,
            to_timestamp=now,
            source_points=published,
        )
        meta = await self.meta.build_by_sources(sources, [])
        return SourceBubbleModel(data=data, meta=meta)

    async def get_source_chart_by_asset(
        self,
        source_id: int,
        asset_id: int,
        type: ChartType,
    ) -> SingleSourceBubbleResult:
        """
        Desc: Draw one asset's premium as one source published it, and say
        how far it moved.
        Args:
            source_id (int): ID of the source that published it.
            asset_id (int): ID of the asset being charted.
            type (ChartType): The chart to draw.
        Returns:
            return (SingleSourceBubbleResult): The chart and the source it
                is of.
        """
        now = int(date_utils.utc_now().timestamp())
        rows = await self.reader.get_latest_by_source_asset_since_per_bucket(
            source_id, asset_id, since=now - type.span, step=type.step
        )
        charted = [source_id] if rows else []
        data = self.builder.build(type, rows, now)
        meta = await self.meta.build(charted, [])
        return SingleSourceBubbleResult(data=data, meta=meta)
