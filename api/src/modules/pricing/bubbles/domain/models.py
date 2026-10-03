from typing import Optional

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
    TextField,
)

from src.modules.pricing.assets.domain.enums import AggregationType, AssetCode


class BubbleBase(BaseEntity):
    code: AssetCode = EnumField(
        AssetCode,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
        unique=True,
    )
    title: str = CharField(55)
    description: str | None = TextField(default=None, nullable=True)


class BubbleModel(BubbleBase, PersistenceEntity):
    pass


class BubbleConfigBase(BaseEntity):
    scheduler_on: bool = BoolField()
    scheduler_seconds: int = IntField()
    agg_type: AggregationType = EnumField(
        AggregationType,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        length=55,
    )


class BubbleConfigModel(BubbleConfigBase, TimestampEntity):
    bubble_id: int = ForeignKeyField(
        "tbl_bubbles.id",
        ondelete="CASCADE",
        primary_key=True,
        index=True,
    )


class BubbleWithConfigModel(BubbleModel):
    config: Optional[BubbleConfigModel] = None
