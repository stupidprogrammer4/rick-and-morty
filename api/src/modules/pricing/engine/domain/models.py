from datetime import datetime

from papilio.infra.db.schema.entity import BaseEntity

from src.modules.pricing.assets.domain.enums import AggregationType
from src.modules.pricing.sources.domain.enums import SelectionReason
from src.modules.pricing.sources.domain.models import (
    PriceModel,
    SourceWithPriceModel,
)
from src.modules.pricing.symbols.domain.enums import CurrencyType


class FeeModel(BaseEntity):
    buy_fee_rate: float
    sell_fee_rate: float
    buy_fee_rial: int
    sell_fee_rial: int


class SourceKeyedModel(BaseEntity):
    symbol_id: int
    source_id: int


class PricedSourceModel(PriceModel, SourceKeyedModel):
    currency: CurrencyType
    is_closed: bool = False
    is_selected: bool = False
    fee: FeeModel | None = None
    reason: SelectionReason | None = None


class SourceSelectionModel(SourceKeyedModel):
    is_selected: bool
    reason: SelectionReason | None = None
    priced_at: datetime


class AggValueModel(BaseEntity):
    agg_type: AggregationType
    result: int


class AggregatedPriceModel(BaseEntity):
    symbol_id: int
    result: int
    agg_type: AggregationType
    sources: list[SourceWithPriceModel]


class SymbolAggModel(BaseEntity):
    symbol_id: int
    agg_type: AggregationType
    aggs: list[AggValueModel]
    sources: list[SourceWithPriceModel]
