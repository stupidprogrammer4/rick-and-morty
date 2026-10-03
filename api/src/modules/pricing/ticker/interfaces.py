from collections.abc import Awaitable
from typing import Protocol

from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.results import (
    BubbleTickerResult,
    PricedSourceModel,
    PriceTickerResult,
    SingleSourceBubbleResult,
    SingleSourcePriceResult,
    SourceBubbleModel,
)


class IPriceTickerService(Protocol):
    def get_chart(
        self, asset_id: int, type: ChartType
    ) -> Awaitable[PriceTickerResult]: ...


class ISourcePriceTickerService(Protocol):
    def get_chart_by_symbol(
        self, symbol_id: int, type: ChartType
    ) -> Awaitable[PricedSourceModel]: ...

    def get_source_chart_by_symbol(
        self, source_id: int, symbol_id: int, type: ChartType
    ) -> Awaitable[SingleSourcePriceResult]: ...


class IPriceSnapshotService(Protocol):
    def snapshot_all(self) -> Awaitable[bool]: ...


class ISourcePriceSnapshotService(Protocol):
    def snapshot_all(self) -> Awaitable[bool]: ...


class IBubbleSnapshotService(Protocol):
    def snapshot_all(self) -> Awaitable[bool]: ...


class IBubbleTickerService(Protocol):
    def get_chart(
        self, asset_id: int, type: ChartType
    ) -> Awaitable[BubbleTickerResult]: ...


class ISourceBubbleSnapshotService(Protocol):
    def snapshot_all(self) -> Awaitable[bool]: ...


class ISourceBubbleTickerService(Protocol):
    def get_chart_by_asset(
        self, asset_id: int, type: ChartType
    ) -> Awaitable[SourceBubbleModel]: ...

    def get_source_chart_by_asset(
        self, source_id: int, asset_id: int, type: ChartType
    ) -> Awaitable[SingleSourceBubbleResult]: ...
