from typing import Sequence

import httpx
from papilio.infra.http.gateway import user_agent

from src.modules.pricing.engine.app.crawlers.base import AbstractFetcher
from src.modules.pricing.engine.app.helpers.responses import json_path
from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
    SupplierSourceQuote,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode


class AbstractSupplierFetcher(AbstractFetcher[SupplierSourceQuote]):
    __symbol__: SymbolCode = SymbolCode.GOLD18_MAZANE

    def _failed(self, error: ErrorQuote) -> Sequence[SupplierSourceQuote]:
        return [
            SupplierSourceQuote.failed(self.__code__, self.__symbol__, error)
        ]


class TalalandFetcher(AbstractSupplierFetcher):
    __code__ = SourceCode.TALALAND

    def headers_of(
        self,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return {"User-Agent": user_agent, **(headers or {})}

    async def _request(self) -> httpx.Response:
        username = self.http.headers.get("username", "")
        token = self.http.headers.get("token", "")
        from urllib.parse import quote

        url = self.__url__.format(
            username=quote(username, safe=""), token=quote(token, safe="")
        )
        resp = await self.http.get(url)
        return resp

    def _parse(self, resp: httpx.Response) -> Sequence[SupplierSourceQuote]:
        data = json_path(resp.json(), "result")
        quote = SupplierSourceQuote.from_pair(
            self.__code__,
            self.__symbol__,
            float(data["bidPrice"]) * 10,
            float(data["askPrice"]) * 10,
            is_closed=not data["marketIsOpen"],
        )
        return [quote]


class MirrokniFetcher(AbstractSupplierFetcher):
    __code__ = SourceCode.MIRROKNI
    group_id = 1
    item_id = 28
    toman_to_rial = 10

    async def _request(self) -> httpx.Response:
        resp = await self.http.post(self.__url__, json={"filter": "all"})
        return resp

    def _parse(self, resp: httpx.Response) -> Sequence[SupplierSourceQuote]:
        items = []
        for group in resp.json().get("Data") or []:
            if group["GroupId"] == self.group_id:
                items = group["Items"]
                break
        info = {}
        for item in items:
            if item["Id"] == self.item_id:
                info = item
                break
        buy, sell = info.get("FeeBuy", 0), info.get("FeeSell", 0)
        quote = SupplierSourceQuote.from_pair(
            self.__code__,
            self.__symbol__,
            float(sell) * self.toman_to_rial,
            float(buy) * self.toman_to_rial,
            is_closed=not (buy and sell),
        )
        return [quote]


SUPPLIER_FETCHERS: dict[
    SourceCode, tuple[type[AbstractSupplierFetcher], ...]
] = {
    SourceCode.MIRROKNI: (MirrokniFetcher,),
    SourceCode.TALALAND: (TalalandFetcher,),
}
