from datetime import datetime

from papilio.schemas.outputs import BaseOutput

from src.modules.pricing.assets.config.constants import (
    AssetIDField,
    AssetSwitchIDField,
)
from src.modules.pricing.assets.domain.models import (
    AssetBase,
    AssetConfigBase,
    AssetMetaModel,
    AssetPriceSummary,
    AssetSwitchBase,
)


class AssetConfigOut(AssetConfigBase):
    asset_id: AssetIDField
    created_at: datetime
    updated_at: datetime


class AssetOut(AssetBase):
    id: AssetIDField
    created_at: datetime
    updated_at: datetime


class AssetWithConfigOut(AssetOut):
    config: AssetConfigOut


class AssetSwitchOut(AssetSwitchBase):
    id: AssetSwitchIDField
    asset_id: AssetIDField
    created_at: datetime
    updated_at: datetime


class AssetPriceSummaryOut(AssetPriceSummary):
    pass


class AssetPriceOut(BaseOutput):
    asset_id: AssetIDField
    buy_price: int
    sell_price: int
    price: int
    buy_spread: int
    sell_spread: int
    buy_spread_rate: float
    sell_spread_rate: float
    priced_at: datetime


class RepriceOut(BaseOutput):
    task_id: str


class AssetMetaOut(AssetMetaModel):
    pass
