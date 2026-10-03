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
