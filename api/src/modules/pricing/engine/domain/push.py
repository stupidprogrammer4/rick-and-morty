from pydantic import AwareDatetime, BaseModel, Field

from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode


class SupplierPricePush(BaseModel):
    source: SourceCode
    symbol: SymbolCode
    buying_rial: int = Field(ge=0)
    selling_rial: int = Field(ge=0)
    quoted_at: AwareDatetime
    is_closed: bool = False
