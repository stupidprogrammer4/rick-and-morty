from typing import Annotated

from fastapi import Depends
from papilio.api.dependencies.ids import decode_path_id

from src.modules.pricing.symbols.config.constants import SYMBOL_ID_ENCRYPTION

SymbolID = Annotated[
    int, Depends(decode_path_id(SYMBOL_ID_ENCRYPTION, "Symbol"))
]

SymbolIDPath = Annotated[
    int,
    Depends(decode_path_id(SYMBOL_ID_ENCRYPTION, "Symbol", "symbol_id")),
]
