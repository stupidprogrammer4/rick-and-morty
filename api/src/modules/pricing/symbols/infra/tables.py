from papilio.infra.db.table import BaseTable

from src.modules.pricing.symbols.domain.models import (
    SymbolModel,
)


class SymbolTable(SymbolModel, BaseTable, table=True):
    pass
