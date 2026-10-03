from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    ForeignKeyField,
    IntField,
    TextField,
)


class DraftModel(PersistenceEntity):
    owner_id: int = BigIntField(index=True)
    origin_bot: str = CharField(8)
    mission_id: int | None = BigIntField(default=None, nullable=True)
    idempotency_key: str = CharField(96, unique=True)
    category: str = CharField(16)
    title: str = CharField(160)
    text: str = TextField()
    revision: int = IntField(default=1)
    approved_revision: int | None = IntField(default=None, nullable=True)
    status: str = CharField(16, default="draft", index=True)
    publisher_bot: str = CharField(8)
    synthetic: bool = BoolField(default=False)
    market_snapshot_id: int | None = ForeignKeyField(
        "tbl_market_snapshots.id",
        default=None,
        nullable=True,
    )


class DraftEvidenceModel(PersistenceEntity):
    draft_id: int = BigIntField()
    article_id: int = BigIntField()
