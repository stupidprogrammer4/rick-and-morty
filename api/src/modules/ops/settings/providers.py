from dishka import Provider, Scope, provide

from portal_contracts.configuration import (
    MarketEnginePolicy,
    PortalConfiguration,
)
from portal_contracts.presentation import PortalPresentation
from src.modules.ops.settings.app.commands import ConfigurationCommands
from src.modules.ops.settings.app.queries import ConfigurationQueries
from src.modules.ops.settings.app.services import (
    NewsSourceConfigService,
    NewsSourceService,
    SettingDefinitionService,
    SettingValueService,
)
from src.modules.ops.settings.domain.dtos import (
    ConfigurationSnapshot,
    NewsSourceCatalog,
)
from src.modules.ops.settings.infra.mysql import (
    NewsSourceConfigRepository,
    NewsSourceRepository,
    SettingDefinitionRepository,
    SettingValueRepository,
)
from src.modules.ops.settings.infra.readers import ConfigurationReader
from src.modules.ops.settings.interfaces import (
    IConfigurationCommands,
    IConfigurationQueries,
    INewsSourceConfigService,
    INewsSourceService,
    ISettingDefinitionService,
    ISettingValueService,
)
from src.modules.pricing.reports.domain.dtos import PriceMapping


class ConfigurationProvider(Provider):
    scope = Scope.REQUEST
    definitions = provide(SettingDefinitionRepository)
    values = provide(SettingValueRepository)
    sources = provide(NewsSourceRepository)
    source_configs = provide(NewsSourceConfigRepository)
    reader = provide(ConfigurationReader)
    definition_service = provide(
        SettingDefinitionService, provides=ISettingDefinitionService
    )
    value_service = provide(SettingValueService, provides=ISettingValueService)
    source_service = provide(NewsSourceService, provides=INewsSourceService)
    source_config_service = provide(
        NewsSourceConfigService, provides=INewsSourceConfigService
    )
    queries = provide(ConfigurationQueries, provides=IConfigurationQueries)
    commands = provide(ConfigurationCommands, provides=IConfigurationCommands)

    @provide
    async def snapshot(
        self, queries: IConfigurationQueries
    ) -> ConfigurationSnapshot:
        result = await queries.snapshot()
        return result

    @provide
    def configuration(
        self, snapshot: ConfigurationSnapshot
    ) -> PortalConfiguration:
        return snapshot.configuration

    @provide
    def presentation(
        self, snapshot: ConfigurationSnapshot
    ) -> PortalPresentation:
        return snapshot.presentation

    @provide
    def price_mapping(self, snapshot: ConfigurationSnapshot) -> PriceMapping:
        return snapshot.prices

    @provide
    def engine_policy(
        self, snapshot: ConfigurationSnapshot
    ) -> MarketEnginePolicy:
        return snapshot.engine

    @provide
    async def news_catalog(
        self, queries: IConfigurationQueries
    ) -> NewsSourceCatalog:
        result = await queries.news_catalog()
        return result
