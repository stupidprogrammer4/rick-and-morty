import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from papilio.utils import currency

from src.modules.pricing.engine.app.crawlers.base import AbstractFetcher
from src.modules.pricing.engine.app.helpers.responses import (
    json_path,
    source_timestamp,
)
from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
    FeeQuote,
    IranSourceQuote,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode


class AbstractIranFetcher(AbstractFetcher[IranSourceQuote]):
    __symbols__: tuple[SymbolCode, ...] = (SymbolCode.GOLD18_GRAM,)
    gold_label: re.Pattern[str]
    price_column: int

    def _failed(self, error: ErrorQuote) -> Sequence[IranSourceQuote]:
        return [
            IranSourceQuote.failed(self.__code__, symbol, error)
            for symbol in self.__symbols__
        ]

    def _price_cell(self, soup: BeautifulSoup) -> str:
        rows = (
            row
            for row in soup.find_all("tr")
            if self.gold_label.search(row.get_text(" ", strip=True))
        )
        found = next(rows, None)
        cells = found.find_all("td") if found is not None else []
        if len(cells) <= self.price_column:
            raise ValueError("GOLD18 price not found")
        return cells[self.price_column].get_text(strip=True)


class TgjuFetcher(AbstractIranFetcher):
    __code__ = SourceCode.TGJU
    __symbols__ = (
        SymbolCode.GOLD18_GRAM,
        SymbolCode.SILVER_GRAM,
        SymbolCode.USD_RIAL,
    )
    gold_sell_key = "tgju_gold_irg18"
    gold_buy_key = "tgju_gold_irg18_buy"
    silver_key = "silver_999"
    dollar_key = "price_dollar_rl"
    source_timezone: str
    parameter_names = {"source_timezone"}

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        board = json_path(resp.json(), "current")
        dollar = json_path(board, self.dollar_key, "p")
        silver = json_path(board, self.silver_key, "p")
        quotes = [
            IranSourceQuote.from_buying_selling(
                self.__code__,
                SymbolCode.GOLD18_GRAM,
                json_path(board, self.gold_sell_key, "p"),
                json_path(board, self.gold_buy_key, "p"),
            ),
            IranSourceQuote.from_buying_selling(
                self.__code__, SymbolCode.SILVER_GRAM, silver, silver
            ),
            IranSourceQuote.from_buying_selling(
                self.__code__, SymbolCode.USD_RIAL, dollar, dollar
            ),
        ]
        keys = [
            (self.gold_sell_key, self.gold_buy_key),
            (self.silver_key,),
            (self.dollar_key,),
        ]
        stamped = []
        for quote, names in zip(quotes, keys):
            times = [
                datetime.fromisoformat(
                    str(json_path(board, name, "ts"))
                ).replace(tzinfo=ZoneInfo(self.source_timezone))
                for name in names
            ]
            stamped.append(replace(quote, quoted_at=min(times)))
        return stamped


class WallexFetcher(AbstractIranFetcher):
    __code__ = SourceCode.WALLEX
    __symbols__ = (SymbolCode.USDT_RIAL,)
    toman_to_rial = 10

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        book = json_path(resp.json(), "result")
        ask = json_path(book, "ask", 0, "price")
        bid = json_path(book, "bid", 0, "price")
        quote = IranSourceQuote.from_buying_selling(
            self.__code__,
            SymbolCode.USDT_RIAL,
            float(ask) * self.toman_to_rial,
            float(bid) * self.toman_to_rial,
        )
        return [quote]


class DigikalaFetcher(AbstractIranFetcher):
    __code__ = SourceCode.DIGIKALA
    __symbols__ = (SymbolCode.GOLD18_GRAM, SymbolCode.SILVER_GRAM)

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        data = resp.json()
        return [
            IranSourceQuote.from_price_and_fee(
                self.__code__,
                symbol,
                int(json_path(data, name, "price")) * 1000,
                FeeQuote(sell_rate=self.fee, buy_rate=self.fee),
            )
            for name, symbol in [
                ("gold18", SymbolCode.GOLD18_GRAM),
                ("silver999", SymbolCode.SILVER_GRAM),
            ]
            if name in data
        ]

    parameter_names = {"fee"}


class TalineFetcher(AbstractIranFetcher):
    __code__ = SourceCode.TALINE

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        quote = None
        for row in json_path(resp.json(), "prices"):
            if row["symbol"] == "GOLD18":
                price = row["price"]
                quote = IranSourceQuote.from_buying_selling(
                    self.__code__,
                    SymbolCode.GOLD18_GRAM,
                    float(price["buy"]) * 10_100,
                    float(price["sell"]) * 10_000,
                )
                stamp = source_timestamp(row["date"]["utc_timestamp"])
                quote = replace(quote, quoted_at=stamp)
                break
        if quote is None:
            raise ValueError("GOLD18 price not found")
        return [quote]


class GoldikaFetcher(AbstractIranFetcher):
    __code__ = SourceCode.GOLDIKA

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        price = json_path(resp.json(), "data", "price")
        quote = IranSourceQuote.from_buying_selling(
            self.__code__, SymbolCode.GOLD18_GRAM, price["sell"], price["buy"]
        )
        stamp = price.get("created_at") or price.get("createdAt")
        if stamp:
            quote = replace(
                quote,
                quoted_at=source_timestamp(stamp),
            )
        return [quote]


class MeligoldFetcher(AbstractIranFetcher):
    __code__ = SourceCode.MELIGOLD

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        data = json_path(resp.json(), "data")
        quote = IranSourceQuote.from_buying_selling(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            int(data["price_buy"]) * 10,
            int(data["price_sell"]) * 10,
        )
        return [quote]


class MiligoldFetcher(AbstractIranFetcher):
    __code__ = SourceCode.MILIGOLD

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        price = int(json_path(resp.json(), "data", "price18")) * 1000
        quote = IranSourceQuote.from_price_and_fee(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            price,
            FeeQuote(sell_rate=self.fee, buy_rate=self.fee),
        )
        stamp = json_path(resp.json(), "data", "date")
        quote = replace(
            quote,
            quoted_at=source_timestamp(stamp, self.source_timezone),
        )
        return [quote]

    source_timezone: str
    parameter_names = {"fee", "source_timezone"}


class TechnogoldFetcher(AbstractIranFetcher):
    __code__ = SourceCode.TECHNOGOLD

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        results = json_path(resp.json(), "results")
        quote = IranSourceQuote.from_buying_selling(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            int(results["sell_price"]) * 10,
            int(results["buy_price"]) * 10,
        )
        return [quote]


class WallgoldFetcher(AbstractIranFetcher):
    __code__ = SourceCode.WALLGOLD

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        price = int(json_path(resp.json(), "result", "price")) * 10
        quote = IranSourceQuote.from_price_and_fee(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            price,
            FeeQuote(sell_rate=self.fee, buy_rate=self.fee),
        )
        return [quote]

    parameter_names = {"fee"}


class TalaseaFetcher(AbstractIranFetcher):
    __code__ = SourceCode.TALASEA

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        data = resp.json()
        price = int(json_path(data, "price")) * 10_000
        fee = float(json_path(data, "feeTable", 0, "fee"))
        quote = IranSourceQuote.from_price_and_fee(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            price,
            FeeQuote(sell_rate=fee, buy_rate=fee),
        )
        return [quote]


class EstjtFetcher(AbstractIranFetcher):
    __code__ = SourceCode.ESTJT
    gold_label = re.compile("۱۸ عیار")
    thousands_sep = "٫"
    price_column = 1
    rial_scale = "0"

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        soup = BeautifulSoup(resp.text, "html.parser")
        price = self._price_cell(soup)
        price = price.replace(self.thousands_sep, "")
        quote = IranSourceQuote.from_buying_selling(
            self.__code__,
            SymbolCode.GOLD18_GRAM,
            price + self.rial_scale,
            price + self.rial_scale,
        )
        return [quote]


class AlanchandFetcher(AbstractIranFetcher):
    __code__ = SourceCode.ALANCHAND
    gold_label = re.compile("گرم طلای 18 عیار")
    toman_unit = "تومان"
    price_column = 1
    toman_to_rial = 10

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        soup = BeautifulSoup(resp.text, "html.parser")
        text = self._price_cell(soup)
        toman = currency.to_rial(text.split(self.toman_unit)[0])
        price = toman * self.toman_to_rial
        quote = IranSourceQuote.from_buying_selling(
            self.__code__, SymbolCode.GOLD18_GRAM, price, price
        )
        return [quote]


class NoghreseaFetcher(AbstractIranFetcher):
    __code__ = SourceCode.NOGHRESEA
    __symbols__ = (SymbolCode.SILVER_GRAM,)
    thousand_toman_to_rial = 10_000

    def _parse(self, resp: httpx.Response) -> Sequence[IranSourceQuote]:
        data = resp.json()
        price = int(float(json_path(data, "price")))
        fee = json_path(data, "fee")
        quote = IranSourceQuote.from_price_and_fee(
            self.__code__,
            SymbolCode.SILVER_GRAM,
            price * self.thousand_toman_to_rial,
            FeeQuote(
                sell_rate=float(fee["sell"]),
                buy_rate=float(fee["buy"]),
            ),
        )
        return [quote]


IRAN_FETCHERS: dict[SourceCode, tuple[type[AbstractIranFetcher], ...]] = {
    SourceCode.ALANCHAND: (AlanchandFetcher,),
    SourceCode.DIGIKALA: (DigikalaFetcher,),
    SourceCode.ESTJT: (EstjtFetcher,),
    SourceCode.GOLDIKA: (GoldikaFetcher,),
    SourceCode.MELIGOLD: (MeligoldFetcher,),
    SourceCode.NOGHRESEA: (NoghreseaFetcher,),
    SourceCode.MILIGOLD: (MiligoldFetcher,),
    SourceCode.TALASEA: (TalaseaFetcher,),
    SourceCode.TALINE: (TalineFetcher,),
    SourceCode.TECHNOGOLD: (TechnogoldFetcher,),
    SourceCode.TGJU: (TgjuFetcher,),
    SourceCode.WALLEX: (WallexFetcher,),
    SourceCode.WALLGOLD: (WallgoldFetcher,),
}
