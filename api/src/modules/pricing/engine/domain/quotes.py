from dataclasses import dataclass
from datetime import datetime
from typing import Self, Sequence

from papilio.utils import currency
from papilio.utils.currency import QuotedAmount

from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.sources.domain.enums import ErrorType, SourceCode
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.tools.currency import round_rial


@dataclass(frozen=True, slots=True)
class HTTPErrorQuote:
    raw_content: str
    status_code: str
    json: dict[str, str] | None


@dataclass(frozen=True, slots=True)
class ErrorQuote:
    error_type: ErrorType
    message: str
    http_error: HTTPErrorQuote | None = None


@dataclass(frozen=True, slots=True)
class SupplierSourceQuote:
    code: SourceCode
    symbol: SymbolCode
    selling_mazane: int
    buying_mazane: int
    is_closed: bool = False
    error: ErrorQuote | None = None
    quoted_at: datetime | None = None

    @classmethod
    def from_pair(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        first: QuotedAmount,
        second: QuotedAmount,
        is_closed: bool = False,
        quoted_at: datetime | None = None,
    ) -> Self:
        first_rial = currency.to_decimal(first)
        second_rial = currency.to_decimal(second)
        quote = cls(
            code=code,
            symbol=symbol,
            selling_mazane=round_rial(max(first_rial, second_rial)),
            buying_mazane=round_rial(min(first_rial, second_rial)),
            is_closed=is_closed,
            quoted_at=quoted_at,
        )
        return quote

    @classmethod
    def failed(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        error: ErrorQuote,
    ) -> Self:
        quote = cls(
            code=code,
            symbol=symbol,
            selling_mazane=0,
            buying_mazane=0,
            error=error,
        )
        return quote


@dataclass(frozen=True, slots=True)
class FeeQuote:
    sell_rate: float
    buy_rate: float


@dataclass(frozen=True, slots=True)
class IranSourceQuote:
    code: SourceCode
    symbol: SymbolCode
    price_rial: int
    buy_fee_rial: int
    sell_fee_rial: int
    buy_price_rial: int
    sell_price_rial: int
    fee: FeeQuote | None = None

    quoted_at: datetime | None = None
    error: ErrorQuote | None = None

    @classmethod
    def from_price_and_fee(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        price_rial: QuotedAmount,
        fee: FeeQuote,
    ) -> Self:
        price = round_rial(currency.to_decimal(price_rial))
        buy_fee = round_rial(price * currency.to_decimal(fee.buy_rate))
        sell_fee = round_rial(price * currency.to_decimal(fee.sell_rate))
        quote = cls(
            code=code,
            symbol=symbol,
            price_rial=price,
            buy_fee_rial=buy_fee,
            sell_fee_rial=sell_fee,
            buy_price_rial=round_rial(price - buy_fee),
            sell_price_rial=round_rial(price + sell_fee),
            fee=fee,
        )
        return quote

    @classmethod
    def from_buying_selling(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        first: QuotedAmount,
        second: QuotedAmount,
        fee: FeeQuote | None = None,
    ) -> Self:
        first_rial = currency.to_decimal(first)
        second_rial = currency.to_decimal(second)
        buying = min(first_rial, second_rial)
        selling = max(first_rial, second_rial)
        buy_fee = 0
        sell_fee = 0
        if fee is not None:
            buy_fee = round_rial(buying * currency.to_decimal(fee.buy_rate))
            sell_fee = round_rial(selling * currency.to_decimal(fee.sell_rate))
        quote = cls(
            code=code,
            symbol=symbol,
            price_rial=round_rial((buying + selling) / 2),
            buy_fee_rial=buy_fee,
            sell_fee_rial=sell_fee,
            buy_price_rial=round_rial(buying - buy_fee),
            sell_price_rial=round_rial(selling + sell_fee),
            fee=fee,
        )
        return quote

    @classmethod
    def failed(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        error: ErrorQuote,
    ) -> Self:
        quote = cls(
            code=code,
            symbol=symbol,
            price_rial=0,
            buy_fee_rial=0,
            sell_fee_rial=0,
            buy_price_rial=0,
            sell_price_rial=0,
            error=error,
        )
        return quote


@dataclass(frozen=True, slots=True)
class GlobalSourceQuote:
    code: SourceCode
    symbol: SymbolCode
    selling_cent: int
    buying_cent: int
    error: ErrorQuote | None = None
    quoted_at: datetime | None = None

    @classmethod
    def from_pair(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        first: QuotedAmount,
        second: QuotedAmount,
    ) -> Self:
        first_cent = currency.to_cent(first)
        second_cent = currency.to_cent(second)
        quote = cls(
            code=code,
            symbol=symbol,
            selling_cent=max(first_cent, second_cent),
            buying_cent=min(first_cent, second_cent),
        )
        return quote

    @classmethod
    def from_mid(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        price: QuotedAmount,
    ) -> Self:
        mid = currency.to_cent(price)
        quote = cls(
            code=code, symbol=symbol, selling_cent=mid, buying_cent=mid
        )
        return quote

    @classmethod
    def failed(
        cls,
        code: SourceCode,
        symbol: SymbolCode,
        error: ErrorQuote,
    ) -> Self:
        quote = cls(
            code=code,
            symbol=symbol,
            selling_cent=0,
            buying_cent=0,
            error=error,
        )
        return quote


@dataclass(frozen=True, slots=True)
class BubbleQuote:
    code: SourceCode
    asset: AssetCode
    amount: int
    error: ErrorQuote | None = None

    @classmethod
    def from_amount(
        cls,
        code: SourceCode,
        asset: AssetCode,
        amount: QuotedAmount,
    ) -> Self:
        quote = cls(
            code=code,
            asset=asset,
            amount=round_rial(currency.to_decimal(amount)),
        )
        return quote

    @classmethod
    def failed(
        cls,
        code: SourceCode,
        asset: AssetCode,
        error: ErrorQuote,
    ) -> Self:
        quote = cls(code=code, asset=asset, amount=0, error=error)
        return quote


@dataclass(frozen=True, slots=True)
class SourceQuote:
    irans: Sequence[IranSourceQuote]
    globals: Sequence[GlobalSourceQuote]
    suppliers: Sequence[SupplierSourceQuote]
    bubbles: Sequence[BubbleQuote]
