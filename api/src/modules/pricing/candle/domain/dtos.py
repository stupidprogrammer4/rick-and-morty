from datetime import datetime

from papilio.schemas.inputs import BaseDTO

from src.modules.pricing.symbols.config.constants import SymbolIDInput


class ParamDTO(BaseDTO):
    from_datetime: datetime
    to_datetime: datetime


class SourceParamDTO(ParamDTO):
    symbol_id: SymbolIDInput
