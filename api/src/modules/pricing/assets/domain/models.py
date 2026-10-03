from typing import Optional

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
    SmallIntField,
    TextField,
)

from src.modules.pricing.assets.config.constants import AssetIDField
from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode
from src.modules.pricing.sources.domain.enums import SourceSwitch


class AssetPriceSummary(BaseEntity):
    asset_code: AssetCode
    price: int


class AssetBase(BaseEntity):
    title: str = CharField(55)
    code: AssetCode = EnumField(
        AssetCode,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
        unique=True,
    )
    description: str | None = TextField(default=None, nullable=True)
    primary_color: str = CharField(55)


class AssetModel(AssetBase, PersistenceEntity):
    pass


class AssetConfigBase(BaseEntity):
    scheduler_on: bool = BoolField()
    scheduler_seconds: int = IntField()
    agg_type: AggregationType = EnumField(
        AggregationType,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
    )


class AssetConfigModel(AssetConfigBase, TimestampEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        primary_key=True,
        index=True,
    )


class AssetSwitchBase(BaseEntity):
    switch: SourceSwitch = EnumField(
        SourceSwitch,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
    )
    priority: int = SmallIntField()


class AssetSwitchModel(AssetSwitchBase, PersistenceEntity):
    asset_id: int = ForeignKeyField(
        "tbl_assets.id",
        ondelete="CASCADE",
        index=True,
    )


class AssetMetaModel(BaseEntity):
    id: AssetIDField
    code: AssetCode
    title: str
    primary_color: str


class AssetsMetaModel(BaseMeta):
    assets: list[AssetMetaModel]


class AssetWithConfigModel(AssetModel):
    config: Optional[AssetConfigModel] = None
