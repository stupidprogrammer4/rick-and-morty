from papilio.infra.db.table import BaseTable
from sqlalchemy import UniqueConstraint

from src.modules.ops.settings.domain.models import (
    NewsSourceConfigModel,
    NewsSourceModel,
    SettingDefinitionModel,
    SettingValueModel,
)


class SettingDefinitionTable(SettingDefinitionModel, BaseTable, table=True):
    pass


class SettingValueTable(SettingValueModel, BaseTable, table=True):
    __table_args__ = (UniqueConstraint("definition_id", "scope"),)


class NewsSourceTable(NewsSourceModel, BaseTable, table=True):
    pass


class NewsSourceConfigTable(NewsSourceConfigModel, BaseTable, table=True):
    pass
