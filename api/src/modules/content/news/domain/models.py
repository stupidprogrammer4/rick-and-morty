from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    TextField,
    TimestampField,
)


class ArticleModel(PersistenceEntity):
    mission_id: int = BigIntField(index=True)
    source_id: str = CharField(64)
    url_hash: str = CharField(64)
    content_hash: str = CharField(64)
    url: str = TextField()
    title: str = CharField(300)
    published_at: datetime | None = TimestampField(default=None, nullable=True)
    fetched_at: datetime = TimestampField()
    body: str = TextField()
    truncated: bool = BoolField(default=False)
