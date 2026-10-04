from decimal import Decimal

from pydantic import HttpUrl

from src.modules.ops.settings.domain.dtos import PriceMapping
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.interfaces import (
    ICacheReaderService,
    ICalculatorService,
)
from src.modules.pricing.engine.interfaces import (
    ICacheReaderService as ISourceReadings,
)
from src.modules.pricing.reports.domain.dtos import MarketSnapshot, Quote
from src.modules.pricing.sources.interfaces import ISourceService
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.shared.dates import as_utc, utc_now


class AuryxPriceProvider:
    def __init__(
        self,
        prices: ICacheReaderService,
        readings: ISourceReadings,
        sources: ISourceService,
        mapping: PriceMapping,
        calculator: ICalculatorService,
    ):
        self.prices = prices
        self.readings = readings
        self.sources = sources
        self.mapping = mapping
        self.calculator = calculator

    async def fetch(self) -> MarketSnapshot:
        codes = {
            "gold": AssetCode.GOLD18,
            "silver": AssetCode.SILVER999,
            "usd": AssetCode.USD,
        }
        symbols = {
            "gold": [
                SymbolCode.GOLD18_GRAM,
                SymbolCode.GOLD18_MAZANE,
                SymbolCode.XAU_OUNCE,
            ],
            "silver": [SymbolCode.SILVER_GRAM, SymbolCode.XAG_OUNCE],
            "usd": [SymbolCode.USD_RIAL],
        }
        await self.calculator.calculate_usd()
        await self.calculator.calculate_all()
        prices = await self.prices.get_prices(list(codes.values()))
        readings = await self.readings.get_many_by_symbols(
            [symbol for values in symbols.values() for symbol in values]
        )
        source_rows = await self.sources.get_all()
        sources = {row.id: row for row in source_rows if row.is_active}
        quotes = []
        for mapping in self.mapping.quotes:
            price = prices.get(codes[mapping.symbol])
            selected = [
                row
                for symbol in symbols[mapping.symbol]
                for row in readings.get(symbol, ())
                if row.is_selected
                and row.source_id in sources
                and as_utc(row.priced_at) <= utc_now()
            ]
            if price is None or price.price <= 0 or not selected:
                raise ValueError(
                    "موتور قیمت برای همه دارایی‌ها داده معتبر ندارد."
                )
            urls = sorted(
                {sources[row.source_id].website_url for row in selected}
            )
            quotes.append(
                Quote(
                    symbol=mapping.symbol,
                    label=mapping.label,
                    timestamp_kind=price.timestamp_kind,
                    amount=Decimal(price.price),
                    currency="IRR",
                    basis=mapping.basis,
                    purity=mapping.purity,
                    market=mapping.market,
                    quoted_at=min(
                        as_utc(price.priced_at),
                        *(as_utc(row.priced_at) for row in selected),
                    ),
                    source_url=HttpUrl(urls[0]),
                    sources=[HttpUrl(url) for url in urls],
                )
            )
        return MarketSnapshot(quotes=quotes, fetched_at=utc_now())
