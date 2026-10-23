from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from portal_contracts.charts import AssetChartPolicy
from src.modules.pricing.assets.domain.models import AssetBase, AssetMetaModel
from src.modules.pricing.candle.domain.models import (
    CandleChartModel,
    CandleReadModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class ChartAsset(AssetBase):
    id: int


class ChartQuote(BaseModel):
    price: int = Field(gt=0)
    priced_at: datetime


class ChartContent(BaseModel):
    price_divisor: int = Field(default=10, ge=1, le=1000)
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


class GlobalGoldInstrument(BaseModel):
    code: Literal[SymbolCode.XAU_OUNCE] = SymbolCode.XAU_OUNCE
    title: str = "اونس جهانی طلا"
    primary_color: str = "#d4a72c"
    source_id: int


class GlobalGoldChartCard(ChartContent):
    kind: Literal["global_gold"] = "global_gold"
    instrument: GlobalGoldInstrument
    price_divisor: int = Field(default=100, ge=100, le=100)


class ChartGallery(BaseModel):
    kind: Literal["gallery"] = "gallery"
    cards: list[AssetChartCard | GlobalGoldChartCard] = Field(
        min_length=1, max_length=10
    )
