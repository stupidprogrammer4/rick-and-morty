from collections.abc import Awaitable
from typing import Mapping, Protocol, Sequence

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.candle.domain.dtos import ParamDTO, SourceParamDTO
from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.domain.results import (
    CandleResult,
    SourceCandleResult,
)
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class IWindowService(Protocol):
    def update_window(
        self, code: AssetCode, cached_prices: AssetPriceModel
    ) -> Awaitable[bool]: ...

    def update_windows(
        self, cached_prices: dict[AssetCode, AssetPriceModel]
    ) -> Awaitable[int]: ...


class ISourceWindowService(Protocol):
    def update_window(
        self, cached_prices: Mapping[SymbolCode, Sequence[PricedSourceModel]]
    ) -> Awaitable[int]: ...


class ISourceCandleService(Protocol):
    def build_timeframe_from_rolled(self, tf: TimeFrame) -> Awaitable[int]: ...

    def build_from_cache(self) -> Awaitable[int]: ...

    def get_candle(
        self, source_id: int, param: SourceParamDTO
    ) -> Awaitable[SourceCandleResult]: ...


class ICandleService(Protocol):
    def build_timeframe_from_rolled(self, tf: TimeFrame) -> Awaitable[int]: ...

    def build_from_cache(self) -> Awaitable[int]: ...

    def get_candle(
        self, asset_id: int, param: ParamDTO
    ) -> Awaitable[CandleResult]: ...
