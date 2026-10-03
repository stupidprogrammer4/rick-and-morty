from typing import Annotated

from fastapi import Depends
from papilio.api.dependencies.ids import decode_path_id

from src.modules.pricing.bubbles.config.constants import BUBBLE_ID_ENCRYPTION

BubbleID = Annotated[
    int, Depends(decode_path_id(BUBBLE_ID_ENCRYPTION, "Bubble"))
]
