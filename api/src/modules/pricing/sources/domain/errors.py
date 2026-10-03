from typing import TypedDict

from src.modules.pricing.sources.domain.enums import ErrorType


class SourceErrorInfo(TypedDict, total=False):
    kind: ErrorType
    message: str
    status_code: int
    raw_content: str
