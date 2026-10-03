from papilio.infra.db.schema.entity import BaseEntity, PersistenceEntity
from papilio.infra.db.schema.fields import (
    BoolField,
    CharField,
    ForeignKeyField,
    IntField,
    TextField,
)

from portal_contracts.configuration import SettingKey, SettingScope


class SettingDefinitionModel(PersistenceEntity):
    key: SettingKey = CharField(100, unique=True)
    title: str = CharField(100)
    kind: str = CharField(20, default="json")


class SettingValueModel(PersistenceEntity):
    definition_id: int = ForeignKeyField(
        "tbl_setting_definitions.id", ondelete="CASCADE"
    )
    scope: SettingScope = CharField(20)
    value: str = TextField()
    revision: int = IntField(default=1)


class NewsSourceModel(PersistenceEntity):
    code: str = CharField(64, unique=True)
    title: str = CharField(100)
    kind: str = CharField(20)
    feed_url: str = CharField(2048)
    enabled: bool = BoolField(default=False)
    revision: int = IntField(default=1)


class NewsSourceConfigModel(BaseEntity):
    source_id: int = ForeignKeyField(
        "tbl_news_sources.id", primary_key=True, ondelete="CASCADE"
    )
    value: str = TextField()
    revision: int = IntField(default=1)
