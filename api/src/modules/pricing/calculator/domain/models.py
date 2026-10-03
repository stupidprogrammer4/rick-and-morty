from datetime import datetime

from papilio.infra.db.schema.entity import BaseEntity

from src.modules.pricing.sources.domain.models import PriceModel


class AssetPriceModel(PriceModel):
    asset_id: int


class AssetBubbleModel(BaseEntity):
    asset_id: int
    amount: int
    priced_at: datetime
