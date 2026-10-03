from dishka import Provider, Scope, provide

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.presentation import PortalPresentation
from src.modules.configuration.app.commands import ConfigurationCommands
from src.modules.configuration.app.queries import ConfigurationQueries
from src.modules.configuration.app.services import (
    NewsSourceConfigService,
    NewsSourceService,
    SettingDefinitionService,
    SettingValueService,
)
from src.modules.configuration.domain.dtos import (
    ConfigurationSnapshot,
    NewsSourceCatalog,
)
from src.modules.configuration.infra.mysql import (
    NewsSourceConfigRepository,
    NewsSourceRepository,
    SettingDefinitionRepository,
    SettingValueRepository,
)
from src.modules.configuration.infra.readers import ConfigurationReader
from src.modules.configuration.interfaces import (
    IConfigurationCommands,
    IConfigurationQueries,
    INewsSourceConfigService,
    INewsSourceService,
    ISettingDefinitionService,
    ISettingValueService,
)
from src.modules.market.domain.dtos import PriceMapping


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
    async def news_catalog(
        self, queries: IConfigurationQueries
    ) -> NewsSourceCatalog:
        result = await queries.news_catalog()
        return result
