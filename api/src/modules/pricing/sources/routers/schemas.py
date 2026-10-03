from datetime import datetime

from papilio.schemas.outputs import BaseOutput
from pydantic import Field, computed_field

from src.modules.pricing.assets.config.constants import AssetIDField
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.sources.config.constants import (
    SourceIDField,
)
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.domain.models import (
    AdminSourcePriceModel,
    SourceBase,
    SourceBubbleModel,
    SourceConfigBase,
    SourceMetaModel,
    SourcePriceDetailsBase,
    SourcePriceModel,
)
from src.modules.pricing.symbols.domain.enums import (
    SymbolCode,
)


class SourceConfigOut(SourceConfigBase):
    fetchers: dict
    login: dict
    source_id: SourceIDField
    headers_credentials: dict[str, str] | None = Field(
        default=None, exclude=True
    )
    auth_credentials: dict[str, str] | None = Field(default=None, exclude=True)
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def has_headers_credentials(self) -> bool:
        return self.headers_credentials is not None

    @computed_field
    @property
    def has_auth_credentials(self) -> bool:
        return self.auth_credentials is not None


class SourceOut(SourceBase):
    id: SourceIDField
    created_at: datetime
    updated_at: datetime


class SourceWithConfigOut(SourceOut):
    config: SourceConfigOut | None = None


class SourceWithPriceOut(SourceOut, SourcePriceDetailsBase):
    pass


class AdminSourcePriceOut(AdminSourcePriceModel):
    pass


class SymbolPricesOut(BaseOutput):
    symbol: SymbolCode
    prices: list[AdminSourcePriceOut]


class SourceBubbleOut(SourceBubbleModel):
    source_id: SourceIDField
    asset_id: AssetIDField


class AssetBubblesOut(BaseOutput):
    asset: AssetCode
    bubbles: list[SourceBubbleOut]


class SourceMetaOut(SourceMetaModel):
    pass


class SourcePriceOut(SourcePriceModel):
    pass


class RemovedSourceErrorOut(BaseOutput):
    source_id: SourceIDField
    error: SourceErrorInfo
