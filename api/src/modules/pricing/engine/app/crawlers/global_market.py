from typing import Sequence

import httpx

from src.modules.pricing.engine.app.crawlers.base import AbstractFetcher
from src.modules.pricing.engine.app.helpers.responses import json_path
from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
    GlobalSourceQuote,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode


class AbstractGlobalFetcher(AbstractFetcher[GlobalSourceQuote]):
    __symbol__: SymbolCode = SymbolCode.XAU_OUNCE

    def _failed(self, error: ErrorQuote) -> Sequence[GlobalSourceQuote]:
        return [
            GlobalSourceQuote.failed(self.__code__, self.__symbol__, error)
        ]


class GoldApiXauFetcher(AbstractGlobalFetcher):
    __code__ = SourceCode.GOLD_API

    def _parse(self, resp: httpx.Response) -> Sequence[GlobalSourceQuote]:
        price = json_path(resp.json(), "price")
        quote = GlobalSourceQuote.from_mid(
            self.__code__, self.__symbol__, price
        )
        return [quote]


class GoldPriceDevFetcher(AbstractGlobalFetcher):
    __code__ = SourceCode.GOLDPRICE_DEV

    def _parse(self, resp: httpx.Response) -> Sequence[GlobalSourceQuote]:
        data = resp.json()
        quote = GlobalSourceQuote.from_pair(
            self.__code__,
            self.__symbol__,
            json_path(data, "ask"),
            json_path(data, "bid"),
        )
        return [quote]


class GoldApiXagFetcher(AbstractGlobalFetcher):
    __code__ = SourceCode.GOLD_API
    __symbol__ = SymbolCode.XAG_OUNCE

    def _parse(self, resp: httpx.Response) -> Sequence[GlobalSourceQuote]:
        price = json_path(resp.json(), "price")
        quote = GlobalSourceQuote.from_mid(
            self.__code__, self.__symbol__, price
        )
        return [quote]


GLOBAL_FETCHERS: dict[SourceCode, tuple[type[AbstractGlobalFetcher], ...]] = {
    SourceCode.GOLD_API: (GoldApiXauFetcher, GoldApiXagFetcher),
    SourceCode.GOLDPRICE_DEV: (GoldPriceDevFetcher,),
}
