from collections.abc import Awaitable
from typing import Protocol

from src.modules.pricing.charts.domain.models import AssetChartCard


class IAssetChartQuery(Protocol):
    def get(self, asset_id: int) -> Awaitable[AssetChartCard]: ...
    def get_all(self) -> Awaitable[list[AssetChartCard]]: ...


class IAssetChartRenderer(Protocol):
    def render(self, card: AssetChartCard) -> Awaitable[bytes]: ...
