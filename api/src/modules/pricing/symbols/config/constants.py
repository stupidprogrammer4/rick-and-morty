from typing import Annotated

from papilio.tools.ids import IDEncryption
from pydantic import AfterValidator, PlainSerializer

SYMBOL_ID_ENCRYPTION = IDEncryption(
    mod=99_999_989,
    coff=14_142_135,
    offset=500_000_000,
)

SymbolIDField = Annotated[
    int, PlainSerializer(SYMBOL_ID_ENCRYPTION.encode, return_type=int)
]

SymbolIDInput = Annotated[int, AfterValidator(SYMBOL_ID_ENCRYPTION.decode)]
