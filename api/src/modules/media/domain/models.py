from datetime import datetime
from typing import Literal

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    ForeignKeyField,
    IntField,
    TextField,
    TimestampField,
)


class MediaJobModel(PersistenceEntity):
    owner_id: int = BigIntField(index=True)
    chat_id: int = BigIntField()
    bot_id: int = BigIntField()
    update_id: int = BigIntField()
    url: str = CharField(2048)
    mode: Literal["media", "audio"] = CharField(16)
    provider: str = CharField(24)
    status: str = CharField(24, default="queued")
    total: int = IntField(default=0)
    sent: int = IntField(default=0)
    failed: int = IntField(default=0)
    error: str | None = CharField(500, default=None, nullable=True)
    lease_until: datetime | None = TimestampField(default=None, nullable=True)
    available_at: datetime | None = TimestampField(default=None, nullable=True)


class MediaItemModel(PersistenceEntity):
    job_id: int = ForeignKeyField("tbl_media_jobs.id", ondelete="CASCADE")
    position: int = IntField()
    title: str = CharField(200)
    payload: str = TextField()
    source_url: str = CharField(2048)
    status: str = CharField(24, default="queued")
    filename: str | None = CharField(100, default=None, nullable=True)
    message_id: int | None = BigIntField(default=None, nullable=True)
    file_id: str | None = CharField(512, default=None, nullable=True)
    error: str | None = CharField(500, default=None, nullable=True)
    lease_until: datetime | None = TimestampField(default=None, nullable=True)
    available_at: datetime | None = TimestampField(default=None, nullable=True)
    downloaded_payload: str | None = TextField(default=None, nullable=True)
