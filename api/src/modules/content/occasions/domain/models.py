from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BoolField,
    CharField,
    IntField,
    TextField,
)


class OccasionModel(PersistenceEntity):
    key: str = CharField(100, unique=True)
    definition: str = TextField()
    enabled: bool = BoolField(default=True)
    revision: int = IntField(default=1)
