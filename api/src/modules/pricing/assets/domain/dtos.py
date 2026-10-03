from typing import Annotated

from papilio.schemas.inputs import BaseDTO
from papilio.types.aliases import ColorType, ContentType, StrType
from pydantic import Field

from src.modules.pricing.assets.config.constants import AssetSwitchIDInput
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.sources.domain.enums import SourceSwitch

SecondType = Annotated[int, Field(ge=20, le=300)]

PriorityType = Annotated[int, Field(ge=0, le=100)]


class AssetCreate(BaseDTO):
    title: StrType
    code: AssetCode
    primary_color: ColorType
    description: ContentType | None = None


class AssetUpdate(BaseDTO):
    title: StrType | None = None
    primary_color: ColorType | None = None
    description: ContentType | None = None


class AssetConfigUpdate(BaseDTO):
    scheduler_on: bool | None = None
    scheduler_seconds: SecondType | None = None
    agg_type: AggregationType | None = None


class AssetSwitchCreate(BaseDTO):
    switch: SourceSwitch
    priority: PriorityType


class AssetSwitchUpdate(BaseDTO):
    switch: SourceSwitch | None = None
    priority: PriorityType | None = None


class AssetSwitchBatchCreate(BaseDTO):
    items: list[AssetSwitchCreate]


class AssetSwitchBatchUpdate(BaseDTO):
    items: list[AssetSwitchCreate]


class AssetSwitchBatchDelete(BaseDTO):
    ids: list[AssetSwitchIDInput]


class AssetSwitchPriorityUpdate(BaseDTO):
    priority: PriorityType
    switches: list[SourceSwitch]
