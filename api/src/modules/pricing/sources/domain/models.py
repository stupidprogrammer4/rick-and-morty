from datetime import datetime
from typing import Literal, Optional

from papilio.api.responses.meta import BaseMeta
from papilio.infra.db.schema.entity import (
    BaseEntity,
    PersistenceEntity,
    TimestampEntity,
)
from papilio.infra.db.schema.fields import (
    BoolField,
    CharField,
    EnumField,
    ForeignKeyField,
    IntField,
    JSONField,
)

from src.modules.pricing.sources.config.constants import SourceIDField
from src.modules.pricing.sources.domain.enums import (
    SelectionReason,
    SourceCode,
    SourceSwitch,
    SourceUpdateType,
)
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.symbols.config.constants import SymbolIDField
from src.modules.pricing.symbols.domain.enums import CurrencyType
from src.modules.pricing.symbols.domain.models import SymbolMetaModel


class PriceModel(BaseEntity):
    timestamp_kind: Literal["source", "fetched"] = "fetched"
    buy_price: int
    sell_price: int
    price: int
    buy_spread: int
    sell_spread: int
    buy_spread_rate: float
    sell_spread_rate: float
    priced_at: datetime


class SourceBase(BaseEntity):
    title: str = CharField(55)
    code: SourceCode = EnumField(
        SourceCode,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
        unique=True,
    )
    website_url: str = CharField(255)
    icon_url: str = CharField(255)
    primary_color: str = CharField(16)
    source_type: SourceSwitch = EnumField(
        SourceSwitch,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
    )
    update_type: SourceUpdateType = EnumField(
        SourceUpdateType,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=35,
        default_factory=lambda: SourceUpdateType.SCHEDULER,
    )
    is_active: bool = BoolField(default=True)
    error: SourceErrorInfo | None = JSONField(default=None, nullable=True)


class SourceModel(SourceBase, PersistenceEntity):
    pass


class SourceConfigBase(BaseEntity):
    timeout: int = IntField()


class SourceConfigModel(SourceConfigBase, TimestampEntity):
    fetchers: dict = JSONField(default_factory=dict)
    login: dict = JSONField(default_factory=dict)
    source_id: int = ForeignKeyField(
        "tbl_sources.id",
        ondelete="CASCADE",
        primary_key=True,
        index=True,
    )
    headers_credentials: dict[str, str] | None = JSONField(
        default=None, nullable=True
    )
    auth_credentials: dict[str, str] | None = JSONField(
        default=None, nullable=True
    )


class SourceMetaModel(BaseEntity):
    id: SourceIDField
    code: SourceCode
    title: str
    primary_color: str


class SourcesMetaModel(BaseMeta):
    sources: list[SourceMetaModel]
    symbols: list[SymbolMetaModel]


class SourceOnlyMetaModel(BaseMeta):
    sources: list[SourceMetaModel]


class SourcePriceModel(PriceModel):
    source_id: SourceIDField
    symbol_id: SymbolIDField
    currency: CurrencyType


class AdminSourcePriceModel(SourcePriceModel):
    is_closed: bool
    is_selected: bool
    reason: SelectionReason | None = None


class SourcePriceDetailsBase(PriceModel):
    currency: CurrencyType
    is_closed: bool
    is_selected: bool
    reason: SelectionReason | None = None


class SourceWithPriceModel(SourceModel, SourcePriceDetailsBase):
    pass


class SourceBubbleModel(BaseEntity):
    source_id: int
    asset_id: int
    amount: int
    priced_at: datetime


class SourceWithConfigModel(SourceModel):
    config: Optional[SourceConfigModel] = None
