from dishka import Provider, Scope, provide

from src.modules.content.drafts.app.commands import DraftAdmission
from src.modules.content.drafts.app.market import MarketDraftCommands
from src.modules.content.drafts.app.services import DraftService
from src.modules.content.drafts.infra.mysql import (
    DraftEvidenceRepository,
    DraftRepository,
)
from src.modules.content.drafts.interfaces import (
    IDraftAdmission,
    IDraftService,
    IMarketDraftCommands,
)


class ContentProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(DraftRepository)
    evidence_repository = provide(DraftEvidenceRepository)
    service = provide(DraftService, provides=IDraftService)
    admission = provide(DraftAdmission, provides=IDraftAdmission)
    market_drafts = provide(MarketDraftCommands, provides=IMarketDraftCommands)
