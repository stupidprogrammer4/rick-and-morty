from datetime import datetime

from src.modules.pricing.assets.config.constants import AssetIDField
from src.modules.pricing.symbols.config.constants import (
    SymbolIDField,
)
from src.modules.pricing.symbols.domain.models import (
    SymbolBase,
    SymbolMetaModel,
)


class SymbolOut(SymbolBase):
    id: SymbolIDField
    asset_id: AssetIDField
    created_at: datetime
    updated_at: datetime


class SymbolMetaOut(SymbolMetaModel):
    pass
