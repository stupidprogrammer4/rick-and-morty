from collections.abc import Awaitable
from typing import Protocol

from src.modules.pricing.candle.domain.models import CandleChartModel
from src.modules.pricing.charts.domain.models import (
    AssetChartCard,
    GlobalGoldChartCard,
)


class IAssetChartQuery(Protocol):
    def get(self, asset_id: int) -> Awaitable[AssetChartCard]: ...
    def get_all(self) -> Awaitable[list[AssetChartCard]]: ...


class IAssetChartRenderer(Protocol):
    def render(
        self, card: AssetChartCard | GlobalGoldChartCard
    ) -> Awaitable[bytes]: ...


class IGlobalGoldChartQuery(Protocol):
    async def get(self) -> GlobalGoldChartCard | None: ...


class IGlobalGoldSeries(Protocol):
    async def read(
        self, source_id: int, start: int, end: int
    ) -> CandleChartModel: ...
