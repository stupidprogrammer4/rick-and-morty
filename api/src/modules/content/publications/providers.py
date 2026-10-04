from dishka import Provider, Scope, provide

from src.modules.content.publications.app.charts import (
    PublicationChartCommands,
    PublicationChartQuery,
    PublicationChartRecovery,
)
from src.modules.content.publications.app.commands import PublicationCommands
from src.modules.content.publications.app.pages import PublishedPageQuery
from src.modules.content.publications.app.recovery import PublicationRecovery
from src.modules.content.publications.app.renderer import PostRenderer
from src.modules.content.publications.infra.charts import (
    PublicationChartReader,
    PublicationChartRepository,
)
from src.modules.content.publications.infra.gateway import TelegramGateway
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.modules.content.publications.interfaces import (
    IPublicationChartCommands,
    IPublicationChartQuery,
    IPublicationChartRecovery,
    IPublicationCommands,
    IPublicationRecovery,
    IPublishedPageQuery,
    ITelegramGateway,
)
from src.modules.content.publications.tasks.schedulers.dispatch import (
    DispatchChart,
    DispatchPublication,
    RecoverCharts,
    RecoverPublications,
)


class PublicationProvider(Provider):
    scope = Scope.REQUEST
    chart_repo = provide(PublicationChartRepository)
    chart_reader = provide(PublicationChartReader)
    chart_query = provide(
        PublicationChartQuery, provides=IPublicationChartQuery
    )
    chart_commands = provide(
        PublicationChartCommands, provides=IPublicationChartCommands
    )
    chart_recovery = provide(
        PublicationChartRecovery, provides=IPublicationChartRecovery
    )
    pages = provide(PublishedPageQuery, provides=IPublishedPageQuery)
    chart_dispatch = provide(DispatchChart)
    charts_recover = provide(RecoverCharts)
    publications = provide(PublicationRepository)
    renderer = provide(PostRenderer)
    gateway = provide(TelegramGateway, provides=ITelegramGateway)
    command = provide(PublicationCommands, provides=IPublicationCommands)
    publication_recovery = provide(
        PublicationRecovery, provides=IPublicationRecovery
    )
    dispatch_task = provide(DispatchPublication)
    recover_task = provide(RecoverPublications)
