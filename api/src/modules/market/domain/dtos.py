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


class Quote(BaseModel):
    symbol: Literal["gold", "usd", "silver"]
    label: str = Field(min_length=1)
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: Literal["IRR", "IRT"]
    basis: str = Field(min_length=1)
    purity: str | None = None
    market: str | None = None
    timestamp_kind: Literal["source", "fetched"] = "source"
    quoted_at: AwareDatetime
    source_url: HttpUrl
    sources: list[HttpUrl] = Field(default_factory=list)

    @model_validator(mode="after")
    def basis_is_explicit(self):
        if self.symbol in {"gold", "silver"} and not self.purity:
            raise ValueError("Metal purity must be explicit")
        if self.symbol == "usd" and not self.market:
            raise ValueError("USD market must be explicit")
        return self

    def toman(self) -> Decimal:
        amount = self.amount / 10 if self.currency == "IRR" else self.amount
        return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class MarketSnapshot(BaseModel):
    quotes: list[Quote] = Field(min_length=3, max_length=3)
    fetched_at: AwareDatetime

    @model_validator(mode="after")
    def symbols_are_complete(self):
        if {quote.symbol for quote in self.quotes} != {
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
