from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    HttpUrl,
    model_validator,
)

from portal_contracts.configuration import MarketInstrument


class Quote(MarketInstrument):
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: Literal["IRR", "IRT", "USD"]
    buy_amount: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    sell_amount: Decimal | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )
    source_code: str | None = None
    source_name: str | None = None
    timestamp_kind: Literal["source", "fetched"] = "source"
    quoted_at: AwareDatetime
    source_url: HttpUrl
    sources: list[HttpUrl] = Field(default_factory=list)

    @model_validator(mode="after")
    def amounts_are_paired(self):
        if (self.buy_amount is None) != (self.sell_amount is None):
            raise ValueError("Buy and sell amounts must be supplied together")
        if self.buy_amount is not None and self.sell_amount is not None:
            if self.buy_amount > self.sell_amount:
                raise ValueError("Buy amount cannot exceed sell amount")
        return self

    def toman(self) -> Decimal:
        if self.currency == "USD":
            raise ValueError("A USD quote requires an exchange rate for toman")
        amount = self.amount / 10 if self.currency == "IRR" else self.amount
        return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class MarketSnapshot(BaseModel):
    mode: Literal["aggregate", "sources"] = "aggregate"
    quotes: list[Quote] = Field(min_length=1, max_length=100)
    fetched_at: AwareDatetime

    @model_validator(mode="after")
    def symbols_are_complete(self):
        if self.mode == "sources":
            keys = [(q.symbol, q.basis, q.source_code) for q in self.quotes]
            if any(
                not q.source_code or not q.source_name for q in self.quotes
            ):
                raise ValueError("Source reports require source identity")
            if len(set(keys)) != len(keys):
                raise ValueError("Source quotes must have distinct identities")
        elif len(self.quotes) != 3 or {
            quote.symbol for quote in self.quotes
        } != {
            "gold",
            "usd",
            "silver",
        }:
            raise ValueError("All three distinct symbols are required")
        return self


class QuoteMapping(BaseModel):
    symbol: Literal["gold", "usd", "silver"]
    label: str
    amount_path: list[str] = Field(min_length=1)
    timestamp_path: list[str] = Field(min_length=1)
    currency: Literal["IRR", "IRT"]
    basis: str
    purity: str | None = None
    market: str | None = None
    endpoint: HttpUrl
    source_url: HttpUrl


class PriceMapping(BaseModel):
    allowed_hosts: set[str] = Field(min_length=1)
    quotes: list[QuoteMapping] = Field(min_length=3, max_length=3)


def validate_freshness(
    snapshot: MarketSnapshot, now: datetime, max_age: int, future_skew: int
) -> None:
    for quote in snapshot.quotes:
        age = (now - quote.quoted_at).total_seconds()
        if age > max_age or age < -future_skew:
            raise ValueError(
                f"قیمت {quote.label} قدیمی یا زمان آن نامعتبر است."
            )
