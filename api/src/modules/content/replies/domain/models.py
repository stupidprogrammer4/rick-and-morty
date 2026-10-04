from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    ForeignKeyField,
    IntField,
    TextField,
    TimestampField,
)

from src.shared.dates import utc_now


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
