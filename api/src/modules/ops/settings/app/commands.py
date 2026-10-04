from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import SettingKey
from src.modules.ops.guards.interfaces import IPortalGuard
from src.modules.ops.settings.app.validation import SettingValueValidator
from src.modules.ops.settings.domain.dtos import (
    ConfigurationSeed,
    NewsSourceCreate,
)
from src.modules.ops.settings.domain.models import (
    NewsSourceConfigModel,
    NewsSourceModel,
    SettingDefinitionModel,
    SettingValueModel,
)
from src.modules.ops.settings.interfaces import (
    INewsSourceConfigService,
    INewsSourceService,
    ISettingDefinitionService,
    ISettingValueService,
)


class ConfigurationCommands:
    def __init__(
        self,
        definitions: ISettingDefinitionService,
        values: ISettingValueService,
        sources: INewsSourceService,
        source_configs: INewsSourceConfigService,
        guard: IPortalGuard,
    ):
        self.definitions = definitions
        self.values = values
        self.sources = sources
        self.source_configs = source_configs
        self.guard = guard

    async def create_source(self, data: NewsSourceCreate) -> int:
        async with transaction():
            await self.guard.lock("configuration")
            source = await self.sources.create(data)
            await self.source_configs.create(source.id, data.options)
        return source.id

    async def seed(self, data: ConfigurationSeed) -> None:
        validator = SettingValueValidator()
        prepared = [
            (
                item,
                validator.validate(
                    SettingKey(item.key), item.scope, item.value
                ),
            )
            for item in data.values
        ]
        async with transaction():
            await self.guard.lock("configuration")
            await self.definitions.seed_many(
                [
                    SettingDefinitionModel(**item.model_dump())
                    for item in data.definitions
                ]
            )
            definitions = await self.definitions.all()
            definition_ids = {item.key: item.id for item in definitions}
            await self.values.seed_many(
                [
                    SettingValueModel(
                        definition_id=definition_ids[SettingKey(item.key)],
                        scope=item.scope,
                        value=value,
                    )
                    for item, value in prepared
                ]
            )
            await self.sources.seed_many(
                [
                    NewsSourceModel(
                        code=item.code,
                        title=item.title,
                        kind=item.kind,
                        feed_url=str(item.feed_url),
                        enabled=item.enabled,
                    )
                    for item in data.sources
                ]
            )
            sources = await self.sources.all()
            source_ids = {item.code: item.id for item in sources}
            await self.source_configs.seed_many(
                [
                    NewsSourceConfigModel(
                        source_id=source_ids[item.code],
                        value=item.options.model_dump_json(),
                    )
                    for item in data.sources
                ]
            )
