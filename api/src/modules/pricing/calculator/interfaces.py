from collections.abc import Awaitable
from typing import Mapping, Protocol, Sequence

from taskiq import ScheduledTask

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.domain.models import (
    AssetBubbleModel,
    AssetPriceModel,
)
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class ICalculatorService(Protocol):
    def calculate_all(self) -> Awaitable[int]: ...

    def calculate_usd(self) -> Awaitable[int]: ...

    def calculate(self, asset_id: int) -> Awaitable[int]: ...


class IBubbleCalculatorService(Protocol):
    def calculate_all(self) -> Awaitable[int]: ...

    def calculate(self, bubble_id: int) -> Awaitable[int]: ...


class ICacheReaderService(Protocol):
    def get_price(
        self, asset_code: AssetCode
    ) -> Awaitable[AssetPriceModel | None]: ...

    def get_prices(
        self, asset_codes: Sequence[AssetCode]
    ) -> Awaitable[Mapping[AssetCode, AssetPriceModel]]: ...

    def get_bubble_amount(
        self, bubble_code: AssetCode
    ) -> Awaitable[AssetBubbleModel | None]: ...

    def get_all_bubble_amounts(
        self,
    ) -> Awaitable[Sequence[AssetBubbleModel]]: ...

    def get_all_prices(self) -> Awaitable[Sequence[AssetPriceModel]]: ...


class ISchedulerService(Protocol):
    def sync(
        self,
        asset_id: int,
        scheduler_on: bool,
        scheduler_seconds: int,
    ) -> Awaitable[bool]: ...


class IBubbleSchedulerService(Protocol):
    def sync(
        self,
        bubble_id: int,
        scheduler_on: bool,
        scheduler_seconds: int,
    ) -> Awaitable[bool]: ...


class ISymbolConverterService(Protocol):
    def convert_asset(
        self,
        asset_id: int,
        to_symbol_code: SymbolCode,
    ) -> Awaitable[AssetPriceModel]: ...

    def convert_all_sources_of_asset(
        self,
        asset_id: int,
        to_symbol_code: SymbolCode,
    ) -> Awaitable[Sequence[PricedSourceModel]]: ...


class IReconcileSchedules(Protocol):
    def execute(self) -> Awaitable[int]: ...

    def repair(
        self, id: str, schedule: ScheduledTask | None
    ) -> Awaitable[None]: ...
