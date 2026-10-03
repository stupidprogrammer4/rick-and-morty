from dataclasses import dataclass

from src.modules.pricing.assets.domain.models import AssetsMetaModel
from src.modules.pricing.sources.domain.models import SourcesMetaModel
from src.modules.pricing.ticker.domain.models import (
    ChartOutputModel,
    SourceChartOutputModel,
)


@dataclass
class PriceTickerResult:
    data: ChartOutputModel
    meta: AssetsMetaModel


@dataclass
class PricedSourceModel:
    data: SourceChartOutputModel
    meta: SourcesMetaModel


@dataclass
class SingleSourcePriceResult:
    data: ChartOutputModel
    meta: SourcesMetaModel


@dataclass
class BubbleTickerResult:
    data: ChartOutputModel
    meta: AssetsMetaModel


@dataclass
class SourceBubbleModel:
    data: SourceChartOutputModel
    meta: SourcesMetaModel


@dataclass
class SingleSourceBubbleResult:
    data: ChartOutputModel
    meta: SourcesMetaModel
