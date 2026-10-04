from datetime import datetime

from pydantic import BaseModel, Field

from portal_contracts.charts import AssetChartPolicy
from src.modules.pricing.assets.domain.models import AssetBase, AssetMetaModel
from src.modules.pricing.candle.domain.models import (
    CandleChartModel,
    CandleReadModel,
)


class ChartAsset(AssetBase):
    id: int


class ChartQuote(BaseModel):
    price: int = Field(gt=0)
    priced_at: datetime


class ChartContent(BaseModel):
    chart: CandleChartModel
    style: AssetChartPolicy
    timezone: str
    caption: str
    quote: ChartQuote | None = None


class ChartCandleSeries(BaseModel):
    interval_seconds: int
    candles: list[CandleReadModel]


class BrowserImageRequest(BaseModel):
    html: str
    script: str
    width: int
    height: int


class AssetChartCard(ChartContent):
    asset: ChartAsset


class AssetChartCardOut(ChartContent):
    asset: AssetMetaModel
