from typing import Sequence

from papilio.infra.db.schema.entity import BaseEntity

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.sources.domain.enums import SourceCode, SourceSwitch
from src.modules.pricing.symbols.domain.enums import SymbolCode


class SourceContext(BaseEntity):
    code: SourceCode
    id: int
    switch: SourceSwitch
    timeout: int
    headers_credentials: dict[str, str] | None
    has_error: bool = False
    fetchers: dict = {}


class AssetRefContext(BaseEntity):
    code: AssetCode
    id: int


class SymbolRefContext(BaseEntity):
    code: SymbolCode
    id: int


class CFGContext(BaseEntity):
    sources: Sequence[SourceContext]
    symbols: Sequence[SymbolRefContext]
    assets: Sequence[AssetRefContext]
