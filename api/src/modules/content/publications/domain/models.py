from datetime import date, datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    DateField,
    ForeignKeyField,
    IntField,
    TextField,
    TimestampField,
)


class PublicationModel(PersistenceEntity):
    pages: str | None = TextField(default=None, nullable=True)
    owner_id: int = BigIntField(index=True)
    draft_id: int = BigIntField()
    revision: int = IntField()
    key: str = CharField(96, unique=True)
    bot_role: str = CharField(8)
    channel_id: int = BigIntField()
    status: str = CharField(16, default="queued", index=True)
    scheduled_at: datetime = TimestampField(index=True)
    deadline: datetime = TimestampField()
    budget_day: date | None = DateField(default=None, nullable=True)
    payload: str | None = TextField(default=None, nullable=True)
    message_id: int | None = BigIntField(default=None, nullable=True)
    lease_expires_at: datetime | None = TimestampField(
        default=None, nullable=True
    )
    failure_reason: str | None = CharField(500, default=None, nullable=True)


class PublicationChartModel(PersistenceEntity):
    publication_id: int = ForeignKeyField("tbl_publications.id", index=True)
    asset_id: int = ForeignKeyField("tbl_assets.id")
    owner_id: int = BigIntField()
    status: str = CharField(16, default="queued", index=True)
    payload: str = TextField()
    scheduled_at: datetime = TimestampField()
    deadline: datetime = TimestampField()
    message_id: int | None = BigIntField(default=None, nullable=True)
    lease_expires_at: datetime | None = TimestampField(
        default=None, nullable=True
    )
    failure_reason: str | None = CharField(500, default=None, nullable=True)
