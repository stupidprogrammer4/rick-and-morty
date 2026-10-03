from typing import Sequence

from dishka import AsyncContainer
from papilio.core.logger import logger

from src.modules.pricing.engine.domain.context import SourceContext
from src.modules.pricing.engine.domain.quotes import SupplierSourceQuote
from src.modules.pricing.engine.infra.readers import SourceReader, SymbolReader
from src.modules.pricing.engine.interfaces import (
    ICacheFlusherService,
    ICFGReaderService,
    ICrawlerService,
    IPersistFlusherService,
    IPushedFlusherService,
)
from src.modules.pricing.sources.domain.enums import (
    ErrorType,
    SourceCode,
    SourceSwitch,
)
from src.modules.pricing.sources.domain.errors import SourceErrorInfo
from src.modules.pricing.sources.interfaces import ISourceErrorService


class RunnerService:
    def __init__(self, container: AsyncContainer) -> None:
        self.container = container

    async def run(self) -> bool:
        """
        Desc: Read the config, crawl every source, then write what came
        back, holding a database connection only for the two db phases.
        Returns:
            return (bool): Whether anything was cached.
        """
        async with self.container() as scope:
            reader = await scope.get(ICFGReaderService)
            cfg = await reader.read_context()

        crawler = await self.container.get(ICrawlerService)
        answered, failed = await crawler.crawl(cfg)

        async with self.container() as scope:
            flusher = await scope.get(ICacheFlusherService)
            saved = await flusher.flush_results(cfg, answered)

        async with self.container() as scope:
            persist = await scope.get(IPersistFlusherService)
            await persist.flush_errors(cfg, failed)
        return saved > 0


class PushRunnerService:
    def __init__(self, container: AsyncContainer) -> None:
        self.container = container

    async def _stamp(self, source: SourceContext, exc: Exception) -> None:
        async with self.container() as scope:
            errors = await scope.get(ISourceErrorService)
            await errors.apply_error(
                source.id,
                SourceErrorInfo(
                    kind=ErrorType.LOGICAL_ERROR,
                    message=type(exc).__name__,
                ),
            )

    async def _clear(self, source: SourceContext) -> None:
        async with self.container() as scope:
            errors = await scope.get(ISourceErrorService)
            await errors.apply_error(source.id, None)

    async def run(
        self,
        code: SourceCode,
        quotes: Sequence[SupplierSourceQuote],
    ) -> bool:
        """Persist one pushed-price attempt; the scheduler owns retry."""
        async with self.container() as scope:
            sources = await scope.get(SourceReader)
            symbols = await scope.get(SymbolReader)
            source = await sources.get_by_code_and_active(code, is_active=True)
            lines = await symbols.read_refs()
        if source is None or source.switch != SourceSwitch.SUPPLIER:
            logger.warning(
                "a price arrived for an unavailable supplier %s", code
            )
            return False

        ids = {line.code: line.id for line in lines}
        try:
            async with self.container() as scope:
                flusher = await scope.get(IPushedFlusherService)
                await flusher.flush_supplier(source, ids, quotes)
            if source.has_error:
                await self._clear(source)
        except Exception as exc:
            try:
                await self._stamp(source, exc)
            except Exception:
                logger.error("could not record source %s failure", source.id)
            raise
        return True
