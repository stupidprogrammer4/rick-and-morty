from dishka import Provider, Scope, provide

from src.modules.content.app.commands import DraftAdmission
from src.modules.content.app.services import DraftService
from src.modules.content.infra.mysql import (
    DraftEvidenceRepository,
    DraftRepository,
)
from src.modules.content.interfaces import IDraftAdmission, IDraftService


class ContentProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(DraftRepository)
    evidence_repository = provide(DraftEvidenceRepository)
    service = provide(DraftService, provides=IDraftService)
    admission = provide(DraftAdmission, provides=IDraftAdmission)
