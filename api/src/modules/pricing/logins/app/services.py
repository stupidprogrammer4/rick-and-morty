import asyncio
from typing import Sequence

from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.logins.app.logins import LOGINS
from src.modules.pricing.logins.domain.context import LoginContext
from src.modules.pricing.logins.domain.quotes import LoginQuote
from src.modules.pricing.logins.infra.readers import LoginReader
from src.modules.pricing.sources.domain.dtos import SourceConfigUpdate
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.interfaces import ISourceConfigService
from src.shared.http import SourceHTTPClient


class SourceLoginService:
    def __init__(
        self,
        reader: LoginReader,
        configs: ISourceConfigService,
        client: SourceHTTPClient,
    ) -> None:
        self.reader = reader
        self.configs = configs
        self.client = client

    async def _try_to_login(self, source: LoginContext) -> LoginQuote:
        """
        Desc: Log into one source through its gateway.
        Args:
            source (LoginContext): The source to log into and its secret.
        Returns:
            return (LoginQuote): What it handed back, or why it refused.
        """
        login = LOGINS[source.code](source, self.client)
        quote = await login.login()
        return quote

    async def _try_to_login_all(
        self,
        codes: Sequence[SourceCode],
    ) -> Sequence[LoginQuote]:
        """
        Desc: Log into every named source that has a login, all at once.
        Args:
            codes (Sequence[SourceCode]): Codes to attempt; ones with no
                login gateway are skipped.
        Returns:
            return (Sequence[LoginQuote]): One quote per attempt made.
        """
        wanted = [code for code in codes if code in LOGINS]
        quotes: Sequence[LoginQuote] = []
        if wanted:
            sources = await self.reader.read_by_codes(wanted)
            quotes = await asyncio.gather(
                *(self._try_to_login(source) for source in sources)
            )
        return quotes

    async def _save_credential(self, quote: LoginQuote) -> bool:
        """
        Desc: Store one granted login on the source's config.
        Args:
            quote (LoginQuote): The attempt to store.
        Returns:
            return (bool): True when credentials were written.
        """
        saved = False
        if quote.issued:
            await self.configs.update(
                quote.source_id,
                SourceConfigUpdate(headers_credentials=quote.credentials),
            )
            saved = True
        return saved

    async def _save_all_credentials(
        self,
        quotes: Sequence[LoginQuote],
    ) -> int:
        """
        Desc: Store every granted login of a sweep.
        Args:
            quotes (Sequence[LoginQuote]): The attempts to store.
        Returns:
            return (int): How many sources were given fresh credentials.
        """
        credentials = {
            quote.source_id: quote.credentials
            for quote in quotes
            if quote.issued
        }
        configs = await self.configs.update_headers_credentials(credentials)
        return len(configs)

    @handle_conflicts
    @transactional
    async def login(self, code: SourceCode) -> bool:
        """
        Desc: Log one source in and store what it issued.
        Args:
            code (SourceCode): Code of the source to log into.
        Returns:
            return (bool): True when it issued credentials.
        """
        saved = False
        if code in LOGINS:
            source = await self.reader.read_by_code(code)
            if source is not None:
                quote = await self._try_to_login(source)
                saved = await self._save_credential(quote)
        return saved

    @handle_conflicts
    @transactional
    async def login_by_id(self, source_id: int) -> bool:
        """
        Desc: Log a source in when only its id is known, as an event gives it.
        Args:
            source_id (int): ID of the source to log into.
        Returns:
            return (bool): True when it issued credentials.
        """
        source = await self.reader.read(source_id)
        saved = False
        if source is not None and source.code in LOGINS:
            quote = await self._try_to_login(source)
            saved = await self._save_credential(quote)
        return saved

    @handle_conflicts
    @transactional
    async def login_codes(self, codes: Sequence[SourceCode]) -> int:
        """
        Desc: Log the named sources in and store what they issued.
        Args:
            codes (Sequence[SourceCode]): Codes of the sources to log into.
        Returns:
            return (int): How many issued credentials.
        """
        quotes = await self._try_to_login_all(codes)
        saved = await self._save_all_credentials(quotes)
        return saved

    @handle_conflicts
    @transactional
    async def login_all(self) -> int:
        """
        Desc: Log in every source that has a login gateway at all.
        Returns:
            return (int): How many issued credentials.
        """
        saved = await self.login_codes(list(LOGINS))
        return saved
