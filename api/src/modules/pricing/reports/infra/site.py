import asyncio
import json
from decimal import Decimal
from functools import reduce

from src.config.settings import PortalAppSettings
from src.modules.pricing.reports.domain.dtos import (
    MarketSnapshot,
    PriceMapping,
    Quote,
    QuoteMapping,
)
from src.shared.dates import utc_now
from src.shared.http import SourceHTTPClient


class OwnerSitePriceProvider:
    def __init__(
        self,
        client: SourceHTTPClient,
        settings: PortalAppSettings,
        mapping: PriceMapping,
    ):
        self.client = client
        self.token = settings.market.token
        self.mapping = mapping

    async def quote(self, item: QuoteMapping, hosts: set[str]) -> Quote:
        raw = await self.client.get(
            str(item.endpoint),
            hosts,
            token=self.token.get_secret_value(),
            maximum_bytes=100000,
        )
        payload = json.loads(raw, parse_float=Decimal)
        if payload.get("success") is False:
            raise ValueError("Price API returned an unsuccessful result")
        return Quote(
            symbol=item.symbol,
            label=item.label,
            amount=reduce(
                lambda obj, key: obj[key], item.amount_path, payload
            ),
            currency=item.currency,
            basis=item.basis,
            purity=item.purity,
            market=item.market,
            quoted_at=reduce(
                lambda obj, key: obj[key], item.timestamp_path, payload
            ),
            source_url=item.source_url,
        )

    async def fetch(self) -> MarketSnapshot:
        mapping = self.mapping
        quotes = await asyncio.gather(
            *(
                self.quote(item, mapping.allowed_hosts)
                for item in mapping.quotes
            )
        )
        return MarketSnapshot(quotes=list(quotes), fetched_at=utc_now())
