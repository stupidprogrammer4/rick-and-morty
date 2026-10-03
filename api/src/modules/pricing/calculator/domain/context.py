from typing import Literal

from papilio.infra.db.schema.entity import BaseEntity

from src.modules.pricing.assets.domain.enums import (
    AggregationType,
    AssetCode,
)
from src.modules.pricing.sources.domain.enums import SourceSwitch
from src.modules.pricing.symbols.domain.enums import SymbolCode


class SymbolContext(BaseEntity):
    id: int
    code: AssetCode
    symbol: SymbolCode
    asset_id: int


class AssetContext(BaseEntity):
    code: AssetCode
    asset_id: int
    agg_type: AggregationType


class BubbleContext(BaseEntity):
    code: AssetCode
    bubble_id: int
    agg_type: AggregationType


class SwitchOrderContext(BaseEntity):
    code: AssetCode
    asset_id: int
    switch: SourceSwitch
    order: int


class ScheduleConfig(BaseEntity):
    kind: Literal["asset", "bubble"]
    id: int
    code: AssetCode
    scheduler_on: bool
    scheduler_seconds: int
