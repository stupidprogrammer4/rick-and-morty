from dishka import Provider, Scope, alias, provide

from src.modules.pricing.sources.app.commands import CreateSource
from src.modules.pricing.sources.app.queries import (
    GetSourcesWithConfig,
    SearchSources,
)
from src.modules.pricing.sources.app.services import (
    SourceConfigService,
    SourceErrorService,
    SourceMetaService,
    SourcePriceService,
    SourceService,
)
from src.modules.pricing.sources.infra.mysql import (
    SourceConfigRepository,
    SourceRepository,
)
from src.modules.pricing.sources.infra.readers import SourceReader
from src.modules.pricing.sources.interfaces import (
    ICreateSource,
    IGetSourcesWithConfig,
    ISearchSources,
    ISourceConfigService,
    ISourceErrorService,
    ISourceMetaService,
    ISourcePriceService,
    ISourceService,
)


class SourceProvider(Provider):
    scope = Scope.REQUEST

    source_repo = provide(SourceRepository)
    source_config_repo = provide(SourceConfigRepository)
    source_config_service = provide(
        SourceConfigService, provides=ISourceConfigService
    )
    source_service = provide(SourceService, provides=ISourceService)
    source_error_service = provide(
        SourceErrorService, provides=ISourceErrorService
    )
    source_meta_service = provide(
        SourceMetaService, provides=ISourceMetaService
    )
    source_price_service = provide(
        SourcePriceService, provides=ISourcePriceService
    )

    reader = provide(SourceReader)
    create_source = provide(CreateSource)
    search = provide(SearchSources)
    get_with_config = provide(GetSourcesWithConfig)

    create_source_contract = alias(CreateSource, provides=ICreateSource)

    get_sources_with_config_contract = alias(
        GetSourcesWithConfig, provides=IGetSourcesWithConfig
    )

    search_sources_contract = alias(SearchSources, provides=ISearchSources)
