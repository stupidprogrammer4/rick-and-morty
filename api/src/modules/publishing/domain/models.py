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

from src.shared.dates import utc_now


class PublicationModel(PersistenceEntity):
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


class PrivateReplyModel(PersistenceEntity):
    mission_id: int = ForeignKeyField("tbl_missions.id", unique=True)
    owner_id: int = BigIntField()
    origin_bot: str = CharField(8)
    text: str = TextField()
    draft_id: int | None = BigIntField(default=None, nullable=True)
    revision: int | None = IntField(default=None, nullable=True)
    status: str = CharField(16, default="queued", index=True)
    message_id: int | None = BigIntField(default=None, nullable=True)
    scheduled_at: datetime = TimestampField(default_factory=utc_now)
    lease_expires_at: datetime | None = TimestampField(
        default=None, nullable=True
    )
    failure_reason: str | None = CharField(500, default=None, nullable=True)
