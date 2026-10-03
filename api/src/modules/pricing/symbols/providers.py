from dishka import Provider, Scope, provide

from src.modules.pricing.symbols.app.services import (
    SymbolMetaService,
    SymbolService,
)
from src.modules.pricing.symbols.infra.mysql import SymbolRepository
from src.modules.pricing.symbols.interfaces import (
    ISymbolMetaService,
    ISymbolService,
)


class SymbolProvider(Provider):
    scope = Scope.REQUEST

    symbol_repo = provide(SymbolRepository)
    symbol_service = provide(SymbolService, provides=ISymbolService)
    symbol_meta_service = provide(
        SymbolMetaService, provides=ISymbolMetaService
    )
