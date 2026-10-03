from papilio.api.responses.meta import BaseMeta
from papilio.infra.db.schema.entity import BaseEntity, PersistenceEntity
from papilio.infra.db.schema.fields import (
    CharField,
    EnumField,
    ForeignKeyField,
    TextField,
)

from src.modules.pricing.symbols.config.constants import SymbolIDField
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


class SymbolBase(BaseEntity):
    title: str = CharField(55)
    code: SymbolCode = EnumField(
        SymbolCode,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
        unique=True,
    )
    currency: CurrencyType = EnumField(
        CurrencyType,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=16,
    )
    description: str | None = TextField(default=None, nullable=True)
    primary_color: str = CharField(55)


class SymbolModel(SymbolBase, PersistenceEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )


class SymbolMetaModel(BaseEntity):
    id: SymbolIDField
    code: SymbolCode
    title: str
    currency: CurrencyType
    primary_color: str


class SymbolsMetaModel(BaseMeta):
    symbols: list[SymbolMetaModel]
