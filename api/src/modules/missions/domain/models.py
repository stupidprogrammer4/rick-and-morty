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


class MissionModel(PersistenceEntity):
    owner_id: int = BigIntField(index=True)
    origin_chat_id: int = BigIntField()
    origin_bot: str = CharField(8)
    origin_message_id: int = BigIntField()
    bot_id: int = BigIntField()
    update_id: int = BigIntField()
    actor: str = CharField(8)
    intent: str = CharField(16)
    text: str = TextField()
    automation_key: str | None = CharField(100, default=None, nullable=True)
    status: str = CharField(24, default="queued", index=True)
    stage: str = CharField(32, default="accepted")
    deadline: datetime = TimestampField()
    lease_expires_at: datetime | None = TimestampField(
        default=None, nullable=True
    )
    version: int = IntField(default=1)
    model_requests: int = IntField(default=0)
    tool_executions: int = IntField(default=0)
    input_tokens: int = IntField(default=0)
    result: str | None = TextField(default=None, nullable=True)
    failure_reason: str | None = CharField(500, default=None, nullable=True)


class MissionEventModel(PersistenceEntity):
    mission_id: int = ForeignKeyField("tbl_missions.id", index=True)
    event: str = CharField(32)
    detail: str = CharField(500)
