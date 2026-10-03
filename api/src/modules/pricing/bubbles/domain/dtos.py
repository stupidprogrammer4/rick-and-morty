from typing import Annotated

from papilio.schemas.inputs import BaseDTO
from papilio.types.aliases import ContentType, StrType
from pydantic import Field

from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode

SecondType = Annotated[int, Field(ge=20, le=300)]


class BubbleCreate(BaseDTO):
    title: StrType
    code: AssetCode
    description: ContentType | None = None


class BubbleUpdate(BaseDTO):
    title: StrType | None = None
    description: ContentType | None = None


class BubbleConfigUpdate(BaseDTO):
    scheduler_on: bool | None = None
    scheduler_seconds: SecondType | None = None
    agg_type: AggregationType | None = None
