from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    ForeignKeyField,
    TextField,
)


class MarketSnapshotModel(PersistenceEntity):
    mission_id: int = ForeignKeyField("tbl_missions.id", unique=True)
    owner_id: int = BigIntField(index=True)
    payload: str = TextField()
    body_hash: str = CharField(64)
