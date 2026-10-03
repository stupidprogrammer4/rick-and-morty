from dishka import Provider, Scope, alias, provide

from src.modules.pricing.logins.app.handlers import (
    SourceUnauthorizedHandler,
)
from src.modules.pricing.logins.app.services import SourceLoginService
from src.modules.pricing.logins.infra.readers import LoginReader
from src.modules.pricing.logins.interfaces import (
    ISourceLoginService,
    ISourceUnauthorizedHandler,
)
from src.modules.pricing.logins.tasks.schedulers.login import (
    RefreshAllLoginsTask,
    RefreshLoginsTask,
)


class LoginProvider(Provider):
    scope = Scope.REQUEST

    login_reader = provide(LoginReader)
    source_login_service = provide(
        SourceLoginService, provides=ISourceLoginService
    )
    source_unauthorized_handler = provide(SourceUnauthorizedHandler)
    refreshallloginstask = provide(RefreshAllLoginsTask, scope=Scope.REQUEST)
    refreshloginstask = provide(RefreshLoginsTask, scope=Scope.REQUEST)

    source_unauthorized_handler_contract = alias(
        SourceUnauthorizedHandler, provides=ISourceUnauthorizedHandler
    )
