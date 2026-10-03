from typing import Annotated

from fastapi import Depends
from papilio.api.dependencies.ids import decode_path_id

from src.modules.pricing.assets.config.constants import (
    ASSET_ID_ENCRYPTION,
    ASSET_SWITCH_ID_ENCRYPTION,
)

AssetID = Annotated[int, Depends(decode_path_id(ASSET_ID_ENCRYPTION, "Asset"))]

AssetSwitchID = Annotated[
    int,
    Depends(decode_path_id(ASSET_SWITCH_ID_ENCRYPTION, "AssetSwitch")),
]

AssetIDPath = Annotated[
    int,
    Depends(decode_path_id(ASSET_ID_ENCRYPTION, "Asset", "asset_id")),
]

AssetSwitchIDPath = Annotated[
    int,
    Depends(
        decode_path_id(
            ASSET_SWITCH_ID_ENCRYPTION, "AssetSwitch", "asset_switch_id"
        )
    ),
]
