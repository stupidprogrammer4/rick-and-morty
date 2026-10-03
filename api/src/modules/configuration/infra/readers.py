from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import and_, func, select, true
from sqlmodel import col

from portal_contracts.configuration import SettingValueOut
from src.modules.configuration.domain.dtos import (
    NewsSourceOptions,
    NewsSourcePage,
    NewsSourceRead,
)
from src.modules.configuration.infra.tables import (
    NewsSourceConfigTable,
    NewsSourceTable,
    SettingDefinitionTable,
    SettingValueTable,
)


class ConfigurationReader(MySQLReader):
    async def settings(self) -> list[SettingValueOut]:
        result = await self.uow.execute(
            select(SettingDefinitionTable, SettingValueTable).join(
                SettingValueTable,
                col(SettingValueTable.definition_id)
                == col(SettingDefinitionTable.id),
            )
        )
        return [
            SettingValueOut(
                definition_id=definition.id,
                key=definition.key,
                scope=value.scope,
                value_id=value.id,
                value=value.value,
                revision=value.revision,
            )
            for definition, value in result.all()
        ]

    async def sources(
        self, page: int, per_page: int, enabled_only: bool = False
    ) -> NewsSourcePage:
        predicate = (
            col(NewsSourceTable.enabled).is_(True) if enabled_only else true()
        )
        result = await self.uow.execute(
            select(NewsSourceTable, NewsSourceConfigTable)
            .join(
                NewsSourceConfigTable,
                and_(
                    col(NewsSourceConfigTable.source_id)
                    == col(NewsSourceTable.id)
                ),
            )
            .where(predicate)
            .order_by(col(NewsSourceTable.id))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count = await self.uow.execute(
            select(func.count()).select_from(NewsSourceTable).where(predicate)
        )
        items = [
            NewsSourceRead(
                id=source.id,
                code=source.code,
                title=source.title,
                kind=source.kind,
                feed_url=source.feed_url,
                enabled=source.enabled,
                revision=source.revision,
                config_revision=config.revision,
                options=NewsSourceOptions.model_validate_json(config.value),
            )
            for source, config in result.all()
        ]
        return NewsSourcePage(
            items=items, total=count.scalar_one(), page=page, per_page=per_page
        )
