from dataclasses import dataclass

from src.modules.pricing.sources.domain.models import (
    AdminSourcePriceModel,
    SourcesMetaModel,
)


@dataclass
class AssetSourcePriceResult:
    data: list[AdminSourcePriceModel]
    meta: SourcesMetaModel
