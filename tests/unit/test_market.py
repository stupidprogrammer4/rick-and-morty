import json
from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.modules.pricing.reports.domain.dtos import (
    MarketSnapshot,
    Quote,
    validate_freshness,
)
from src.modules.pricing.reports.infra.site import OwnerSitePriceProvider
from src.shared.dates import utc_now


def quote(symbol="gold", amount="1000001", currency="IRR", **changes):
    fields = dict(
        symbol=symbol,
        label=symbol,
        amount=amount,
        currency=currency,
        basis="per_gram",
        purity="750",
        market="aggregate",
        quoted_at=utc_now(),
        source_url="https://api.talamala.ir/api/assets/gold18/price",
    )
    fields.update(changes)
    return Quote.model_validate(fields)


@pytest.mark.parametrize(
    "currency,amount,expected",
    [
        ("IRR", "1000005", "100001"),
        ("IRT", "1000005", "1000005"),
        ("IRR", "1000001", "100000"),
    ],
)
def test_currency_is_converted_exactly_once(currency, amount, expected):
    assert quote(amount=amount, currency=currency).toman() == Decimal(expected)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"amount": "-1"},
        {"amount": "0"},
        {"purity": None},
        {"quoted_at": "2026-10-03T12:00:00"},
        {"symbol": "usd", "market": None},
    ],
)
def test_incomplete_or_invalid_quote_is_rejected(changes):
    with pytest.raises(ValidationError):
        quote(**changes)


def test_one_stale_quote_rejects_the_whole_snapshot():
    now = utc_now()
    data = MarketSnapshot(
        quotes=[
            quote("gold"),
            quote("usd"),
            quote("silver", quoted_at=now - timedelta(seconds=901)),
        ],
        fetched_at=now,
    )
    with pytest.raises(ValueError):
        validate_freshness(data, now, 900, 120)


def test_duplicate_symbols_do_not_form_a_complete_snapshot():
    with pytest.raises(ValidationError):
        MarketSnapshot(
            quotes=[quote(), quote(), quote("usd")], fetched_at=utc_now()
        )


@pytest.mark.asyncio
async def test_talamala_native_envelope_and_units(snapshot):
    from pydantic import SecretStr

    from src.config.settings import MarketCredentials

    class ExternalSource:
        async def get(self, url, hosts, **kwargs):
            assert hosts == {"api.talamala.ir"}
            assert url.endswith("/price")
            return json.dumps(
                {
                    "success": True,
                    "data": {
                        "price": "1000005",
                        "priced_at": utc_now().isoformat(),
                    },
                }
            ).encode()

    class Credentials:
        market = MarketCredentials(token=SecretStr(""))

    provider = OwnerSitePriceProvider(
        ExternalSource(), Credentials(), snapshot[2]
    )
    result = await provider.fetch()
    assert {item.symbol for item in result.quotes} == {"gold", "usd", "silver"}
    assert all(item.currency == "IRR" for item in result.quotes)
    assert all(item.toman() == Decimal("100001") for item in result.quotes)
    assert result.quotes[0].purity == "750"
    assert result.quotes[2].purity == "999"
