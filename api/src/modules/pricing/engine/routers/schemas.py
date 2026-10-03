from datetime import datetime

from papilio.api.responses.meta import BaseMeta
from papilio.schemas.outputs import BaseOutput

from src.modules.pricing.assets.config.constants import AssetIDField
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.sources.config.constants import SourceIDField
from src.modules.pricing.sources.routers.schemas import SourceWithPriceOut
from src.modules.pricing.symbols.config.constants import SymbolIDField
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


class PublicPriceOut(BaseOutput):
    symbol_id: SymbolIDField
    source_id: SourceIDField
    currency: CurrencyType
    buy_price: int
    sell_price: int
    price: int
    priced_at: datetime


class PublicSymbolPricesOut(BaseOutput):
    symbol: SymbolCode
    prices: list[PublicPriceOut]


class PublicBubbleOut(BaseOutput):
    asset_id: AssetIDField
    source_id: SourceIDField
    amount: int
    priced_at: datetime


class PublicAssetBubblesOut(BaseOutput):
    asset: AssetCode
    bubbles: list[PublicBubbleOut]


class AggregatedPriceOut(BaseOutput):
    symbol_id: SymbolIDField
    result: int
    agg_type: AggregationType
    sources: list[SourceWithPriceOut]


class AggValueOut(BaseOutput):
    agg_type: AggregationType
    result: int


class SymbolAggMeta(BaseMeta):
    symbol_id: SymbolIDField
    agg_type: AggregationType
    aggs: list[AggValueOut]
