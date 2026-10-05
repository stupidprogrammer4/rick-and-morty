from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    TextField,
    TimestampField,
)


class MediaAssetModel(PersistenceEntity):
    cache_key: str = CharField(64)
    bot_id: int = BigIntField()
    file_id: str = CharField(512)
    payload: str = TextField()
    expires_at: datetime = TimestampField()
