import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.modules.pricing.engine.app.crawlers.iran_market import TgjuFetcher
from src.modules.pricing.engine.app.helpers.responses import http_error
from src.modules.pricing.symbols.domain.enums import SymbolCode


def test_copied_tgju_parser_keeps_source_times_and_database_endpoint():
    source = next(
        row
        for row in json.loads(Path("api/seeds/pricing.json").read_text())[
            "sources"
        ]
        if row["code"] == "tgju"
    )
    configuration = source["fetchers"]["TgjuFetcher"]
    fetcher = TgjuFetcher(None, configuration=configuration)
    board = {
        "tgju_gold_irg18": {"p": "100,000,000", "ts": "2026-10-03 15:04:00"},
        "tgju_gold_irg18_buy": {
            "p": "98,000,000",
            "ts": "2026-10-03 15:03:00",
        },
        "silver_999": {"p": "5,284,000", "ts": "2026-10-03 11:11:30"},
        "price_dollar_rl": {"p": "2,673,000", "ts": "2026-10-03 15:04:00"},
    }
    quotes = fetcher._parse(httpx.Response(200, json={"current": board}))
    silver = next(
        row for row in quotes if row.symbol == SymbolCode.SILVER_GRAM
    )
    assert silver.price_rial == 5_284_000
    assert silver.quoted_at == datetime(
        2026, 10, 3, 11, 11, 30, tzinfo=ZoneInfo("Asia/Tehran")
    )
    assert fetcher.__url__ == configuration["endpoint"]
    assert (
        next(
            row for row in quotes if row.symbol == SymbolCode.GOLD18_GRAM
        ).quoted_at.hour
        == 15
    )


def test_price_errors_never_keep_credentials_or_provider_body():
    request = httpx.Request("GET", "https://example.com/private-path-secret")
    response = httpx.Response(
        403, text="token=private-body-secret", request=request
    )
    error = http_error(
        httpx.HTTPStatusError(
            "private-path-secret", request=request, response=response
        )
    )
    assert error.message == "HTTPStatusError"
    assert error.http_error.status_code == "403"
    assert error.http_error.raw_content == ""
    assert error.http_error.json is None


def test_database_price_parameters_cannot_override_methods():
    with pytest.raises(ValueError, match="Unsupported price source parameter"):
        TgjuFetcher(
            None,
            configuration={
                "endpoint": "https://example.com",
                "allowed_hosts": ["example.com"],
                "parameters": {"fetch": "changed"},
            },
        )


def test_wallex_order_book_quotes_usdt_independently_of_usd():
    from src.modules.pricing.engine.app.crawlers.iran_market import (
        WallexFetcher,
    )

    fetcher = WallexFetcher(None)
    quotes = fetcher._parse(
        httpx.Response(
            200,
            json={
                "result": {
                    "ask": [{"price": "268300"}],
                    "bid": [{"price": "267900"}],
                }
            },
        )
    )
    usdt = next(iter(quotes))
    assert usdt.symbol == SymbolCode.USDT_RIAL
    assert usdt.buy_price_rial == 2_679_000
    assert usdt.sell_price_rial == 2_683_000
    assert usdt.quoted_at is None


def test_digikala_keeps_gold_and_silver_units_and_fees_separate():
    from src.modules.pricing.engine.app.crawlers.iran_market import (
        DigikalaFetcher,
    )

    fetcher = DigikalaFetcher(
        None, configuration={"parameters": {"fee": 0.005}}
    )
    quotes = fetcher._parse(
        httpx.Response(
            200,
            json={
                "gold18": {"price": 265614, "ttl": 60},
                "silver999": {"price": 5313, "ttl": 60},
            },
        )
    )
    amounts = {q.symbol: q for q in quotes}
    assert amounts[SymbolCode.GOLD18_GRAM].price_rial == 265_614_000
    assert amounts[SymbolCode.SILVER_GRAM].price_rial == 5_313_000
    assert amounts[SymbolCode.SILVER_GRAM].buy_price_rial == 5_286_400
    assert amounts[SymbolCode.SILVER_GRAM].sell_price_rial == 5_339_600


def test_global_source_keeps_decimal_units_and_original_time():
    from src.modules.pricing.engine.app.crawlers.global_market import (
        GoldApiXagFetcher,
        GoldPriceDevFetcher,
    )

    silver = GoldApiXagFetcher(None)._parse(
        httpx.Response(
            200,
            json={
                "price": "60.529",
                "updatedAt": "2026-10-03T14:27:01Z",
            },
        )
    )
    assert next(iter(silver)).selling_cent == 6053
    assert (
        next(iter(silver)).quoted_at.isoformat() == "2026-10-03T14:27:01+00:00"
    )
    gold = GoldPriceDevFetcher(None)._parse(
        httpx.Response(
            200,
            json={
                "price": "4141.52",
                "is_stale": False,
                "computed_at": "2026-10-02T21:08:02+00:00",
            },
        )
    )
    assert next(iter(gold)).selling_cent == 414152
    assert next(iter(gold)).quoted_at.day == 2
    with pytest.raises(ValueError):
        GoldPriceDevFetcher(None)._parse(
            httpx.Response(
                200,
                json={
                    "price": "4141.52",
                    "is_stale": True,
                    "computed_at": "2026-10-02T21:08:02+00:00",
                },
            )
        )


def test_naive_source_time_needs_configured_timezone():
    from src.modules.pricing.engine.app.helpers.responses import (
        source_timestamp,
    )

    with pytest.raises(ValueError):
        source_timestamp("2026-10-03T14:00:00")
    assert (
        source_timestamp("2026-10-03T14:00:00", "Asia/Tehran")
        .utcoffset()
        .total_seconds()
        == 12600
    )
    assert (
        source_timestamp("2026-10-03T14:00:00+00:00", "Asia/Tehran")
        .utcoffset()
        .total_seconds()
        == 0
    )
