from dataclasses import dataclass, field
from typing import Self

from src.modules.pricing.sources.domain.enums import ErrorType, SourceCode


@dataclass(frozen=True, slots=True)
class LoginError:
    error_type: ErrorType
    message: str


@dataclass(frozen=True, slots=True)
class LoginQuote:
    code: SourceCode
    source_id: int
    credentials: dict[str, str] = field(default_factory=dict)
    error: LoginError | None = None

    @property
    def issued(self) -> bool:
        return self.error is None and bool(self.credentials)

    @classmethod
    def granted(
        cls,
        code: SourceCode,
        source_id: int,
        credentials: dict[str, str],
    ) -> Self:
        quote = cls(code=code, source_id=source_id, credentials=credentials)
        return quote

    @classmethod
    def refused(
        cls,
        code: SourceCode,
        source_id: int,
        error: LoginError,
    ) -> Self:
        quote = cls(code=code, source_id=source_id, error=error)
        return quote
