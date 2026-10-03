from pydantic import BaseModel

from portal_contracts.charts import AssetChartPolicy
from src.modules.pricing.assets.domain.models import AssetBase, AssetMetaModel
from src.modules.pricing.candle.domain.models import CandleChartModel


class ChartAsset(AssetBase):
    id: int


class ChartContent(BaseModel):
    chart: CandleChartModel
    style: AssetChartPolicy
    timezone: str
    caption: str


class AssetChartCard(ChartContent):
    asset: ChartAsset


class AssetChartCardOut(ChartContent):
    asset: AssetMetaModel
