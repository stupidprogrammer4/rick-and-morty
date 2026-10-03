from collections.abc import Awaitable
from typing import Protocol, Sequence

from src.modules.pricing.logins.domain.events import SourceUnauthorizedInput
from src.modules.pricing.logins.domain.quotes import LoginQuote
from src.modules.pricing.sources.domain.enums import SourceCode


class ISourceLoginService(Protocol):
    def login(self, code: SourceCode) -> Awaitable[bool]: ...

    def login_by_id(self, source_id: int) -> Awaitable[bool]: ...

    def login_codes(self, codes: Sequence[SourceCode]) -> Awaitable[int]: ...

    def login_all(self) -> Awaitable[int]: ...

    def _try_to_login_all(
        self,
        codes: Sequence[SourceCode],
    ) -> Awaitable[Sequence[LoginQuote]]: ...

    def _save_all_credentials(
        self,
        quotes: Sequence[LoginQuote],
    ) -> Awaitable[int]: ...


class ISourceUnauthorizedHandler(Protocol):
    def handle(self, data: SourceUnauthorizedInput) -> Awaitable[int]: ...
