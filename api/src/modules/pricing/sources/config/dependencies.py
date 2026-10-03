from typing import Annotated

from fastapi import Depends
from papilio.api.dependencies.ids import decode_path_id

from src.modules.pricing.sources.config.constants import SOURCE_ID_ENCRYPTION

SourceID = Annotated[
    int, Depends(decode_path_id(SOURCE_ID_ENCRYPTION, "Source"))
]

SourceIDPath = Annotated[
    int,
    Depends(decode_path_id(SOURCE_ID_ENCRYPTION, "Source", "source_id")),
]
