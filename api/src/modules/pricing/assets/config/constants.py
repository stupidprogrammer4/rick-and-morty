from typing import Annotated

from papilio.tools.ids import IDEncryption
from pydantic import AfterValidator, PlainSerializer

ASSET_ID_ENCRYPTION = IDEncryption(
    mod=99_999_989,
    coff=31_415_926,
    offset=100_000_000,
)

ASSET_SWITCH_ID_ENCRYPTION = IDEncryption(
    mod=99_999_989,
    coff=16_180_339,
    offset=400_000_000,
)

AssetIDField = Annotated[
    int, PlainSerializer(ASSET_ID_ENCRYPTION.encode, return_type=int)
]

AssetSwitchIDInput = Annotated[
    int, AfterValidator(ASSET_SWITCH_ID_ENCRYPTION.decode)
]

AssetIDInput = Annotated[int, AfterValidator(ASSET_ID_ENCRYPTION.decode)]

AssetSwitchIDField = Annotated[
    int, PlainSerializer(ASSET_SWITCH_ID_ENCRYPTION.encode, return_type=int)
]
