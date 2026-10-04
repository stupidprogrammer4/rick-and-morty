from papilio.infra.db.schema.entity import BaseEntity
from papilio.infra.db.schema.fields import BoolField, CharField


class PortalGuardModel(BaseEntity):
    key: str = CharField(96, primary_key=True)
    paused: bool = BoolField(default=False)
