from papilio.schemas.inputs import BaseDTO
from papilio.types.aliases import ColorType, ContentType, StrType

from src.modules.pricing.assets.config.constants import AssetIDInput
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


class SymbolCreate(BaseDTO):
    title: StrType
    code: SymbolCode
    asset_id: AssetIDInput
    currency: CurrencyType
    primary_color: ColorType
    description: ContentType | None = None


class SymbolUpdate(BaseDTO):
    title: StrType | None = None
    currency: CurrencyType | None = None
    primary_color: ColorType | None = None
    description: ContentType | None = None
