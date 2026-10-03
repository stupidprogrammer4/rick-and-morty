from pydantic import AwareDatetime, BaseModel, Field

from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode


class SupplierPriceLine(BaseModel):
    symbol: SymbolCode
    buying_rial: int = Field(ge=0)
    selling_rial: int = Field(ge=0)
    quoted_at: AwareDatetime
    is_closed: bool = False


class SupplierPricePush(BaseModel):
    source: SourceCode
    quotes: list[SupplierPriceLine] = Field(min_length=1, max_length=100)
