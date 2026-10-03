from dataclasses import dataclass

from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.domain.models import AdminSourcePriceModel
from src.modules.pricing.symbols.domain.models import SymbolsMetaModel


@dataclass
class SourcePricesResult:
    data: list[AdminSourcePriceModel]
    meta: SymbolsMetaModel


@dataclass
class MultiSourcePricesResult:
    data: list[AdminSourcePriceModel]
    meta: SymbolsMetaModel


@dataclass
class SourceErrorRemoval:
    source_id: int
    error: SourceErrorInfo
