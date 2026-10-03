from dataclasses import dataclass

from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
    SourceOnlyMetaModel,
)


@dataclass
class BubbleSourcesResult:
    data: list[SourceBubbleModel]
    meta: SourceOnlyMetaModel
