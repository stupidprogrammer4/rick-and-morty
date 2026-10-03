from dataclasses import dataclass

from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.candle.domain.models import CandleChartModel
from src.modules.pricing.sources.domain.models import SourcesMetaModel


@dataclass
class CandleResult:
    data: CandleChartModel
    meta: AssetsMetaModel


@dataclass
class SourceCandleResult:
    data: CandleChartModel
    meta: SourcesMetaModel
