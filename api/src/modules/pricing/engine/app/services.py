import asyncio
from typing import Awaitable, Sequence

from src.modules.pricing.engine.app.crawlers.bubble import BUBBLE_FETCHERS
from src.modules.pricing.engine.app.crawlers.global_market import (
    GLOBAL_FETCHERS,
)
from src.modules.pricing.engine.app.crawlers.iran_market import IRAN_FETCHERS
from src.modules.pricing.engine.app.crawlers.supplier import (
    SUPPLIER_FETCHERS,
)
from src.modules.pricing.engine.domain.context import CFGContext
from src.modules.pricing.engine.domain.quotes import (
    BubbleQuote,
    GlobalSourceQuote,
    IranSourceQuote,
    SourceQuote,
    SupplierSourceQuote,
)
from src.shared.http import SourceHTTPClient


class CrawlerService:
    def __init__(self, connection: SourceHTTPClient) -> None:
        self.connection = connection

    async def crawl(
        self,
        cfg: CFGContext,
    ) -> tuple[SourceQuote, SourceQuote]:
        """
        Desc: Call every source that has a fetcher, all at once, and split
        what answered from what failed.
        Args:
            cfg (CFGContext): The sources to call, with their configs.
        Returns:
            return (tuple[SourceQuote, SourceQuote]): The answered quotes,
                then the failed ones.
        """
        suppliers: list[Awaitable[Sequence[SupplierSourceQuote]]] = []
        irans: list[Awaitable[Sequence[IranSourceQuote]]] = []
        globals_: list[Awaitable[Sequence[GlobalSourceQuote]]] = []
        bubbles: list[Awaitable[Sequence[BubbleQuote]]] = []
        for source in cfg.sources:
            headers = source.headers_credentials
            timeout = source.timeout
            for supplier_cls in SUPPLIER_FETCHERS.get(source.code, ()):
                suppliers.append(
                    supplier_cls(
                        self.connection,
                        headers,
                        timeout,
                        source.fetchers.get(supplier_cls.__name__),
                    ).fetch()
                )
            for iran_cls in IRAN_FETCHERS.get(source.code, ()):
                irans.append(
                    iran_cls(
                        self.connection,
                        headers,
                        timeout,
                        source.fetchers.get(iran_cls.__name__),
                    ).fetch()
                )
            for global_cls in GLOBAL_FETCHERS.get(source.code, ()):
                globals_.append(
                    global_cls(
                        self.connection,
                        headers,
                        timeout,
                        source.fetchers.get(global_cls.__name__),
                    ).fetch()
                )
            for bubble_cls in BUBBLE_FETCHERS.get(source.code, ()):
                bubbles.append(
                    bubble_cls(
                        self.connection,
                        headers,
                        timeout,
                        source.fetchers.get(bubble_cls.__name__),
                    ).fetch()
                )

        (
            supplier_rows,
            iran_rows,
            global_rows,
            bubble_rows,
        ) = await asyncio.gather(
            asyncio.gather(*suppliers),
            asyncio.gather(*irans),
            asyncio.gather(*globals_),
            asyncio.gather(*bubbles),
        )
        supplied = [q for rows in supplier_rows for q in rows]
        iraned = [q for rows in iran_rows for q in rows]
        worlded = [q for rows in global_rows for q in rows]
        bubbled = [q for rows in bubble_rows for q in rows]
        answered = SourceQuote(
            suppliers=[q for q in supplied if q.error is None],
            irans=[q for q in iraned if q.error is None],
            globals=[q for q in worlded if q.error is None],
            bubbles=[q for q in bubbled if q.error is None],
        )
        failed = SourceQuote(
            suppliers=[q for q in supplied if q.error is not None],
            irans=[q for q in iraned if q.error is not None],
            globals=[q for q in worlded if q.error is not None],
            bubbles=[q for q in bubbled if q.error is not None],
        )
        return answered, failed
