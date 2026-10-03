from pydantic import BaseModel

from src.modules.pricing.sources.domain.enums import SourceCode


class SourceUnauthorizedInput(BaseModel):
    codes: list[SourceCode]
