from typing import Annotated

from papilio.tools.ids import IDEncryption
from pydantic import AfterValidator, PlainSerializer

BUBBLE_ID_ENCRYPTION = IDEncryption(
    mod=99_999_989,
    coff=27_182_818,
    offset=300_000_000,
)

BubbleIDField = Annotated[
    int, PlainSerializer(BUBBLE_ID_ENCRYPTION.encode, return_type=int)
]

BubbleIDInput = Annotated[int, AfterValidator(BUBBLE_ID_ENCRYPTION.decode)]
