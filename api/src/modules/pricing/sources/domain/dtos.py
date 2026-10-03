from typing import Annotated

from papilio.schemas.inputs import BaseDTO
from papilio.types.aliases import (
    ColorType,
    LStrType,
    MediaUrlType,
    PageType,
    PerPageType,
    StrType,
    ValueType,
)
from papilio.types.enums import SortOrder
from pydantic import Field

from src.modules.pricing.sources.domain.enums import (
    SourceCode,
    SourceSortBy,
    SourceSwitch,
    SourceUpdateType,
)

TimeoutType = Annotated[int, Field(ge=1, le=60)]


class SourceCreate(BaseDTO):
    title: StrType
    code: SourceCode
    website_url: LStrType
    icon_url: MediaUrlType
    primary_color: ColorType
    source_type: SourceSwitch
    update_type: SourceUpdateType = SourceUpdateType.SCHEDULER
    is_active: bool = True


class SourceUpdate(BaseDTO):
    title: StrType | None = None
    website_url: LStrType | None = None
    icon_url: MediaUrlType | None = None
    primary_color: ColorType | None = None
    source_type: SourceSwitch | None = None
    update_type: SourceUpdateType | None = None
    is_active: bool | None = None


class SourceSearch(BaseDTO):
    q: ValueType | None = None
    source_types: list[SourceSwitch] | None = None
    update_types: list[SourceUpdateType] | None = None
    is_active: bool | None = None
    has_error: bool | None = None
    sort_by: SourceSortBy = SourceSortBy.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    page: PageType = 1
    per_page: PerPageType = 20


class SourceConfigUpdate(BaseDTO):
    fetchers: dict | None = None
    login: dict | None = None
    timeout: TimeoutType | None = None
    headers_credentials: dict[str, str] | None = None
    auth_credentials: dict[str, str] | None = None
