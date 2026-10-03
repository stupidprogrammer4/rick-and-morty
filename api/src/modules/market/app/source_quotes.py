from decimal import Decimal
from statistics import median

from pydantic import HttpUrl

from portal_contracts.configuration import (
    MarketEnginePolicy,
    PortalConfiguration,
)
from src.modules.market.domain.dtos import MarketSnapshot, Quote
from src.modules.pricing.engine.interfaces import ICacheReaderService
from src.modules.pricing.sources.interfaces import ISourceService
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode
from src.shared.dates import as_utc, utc_now


class SourceMarketPriceProvider:
    def __init__(
        self,
        readings: ICacheReaderService,
        sources: ISourceService,
        settings: PortalConfiguration,
        engine: MarketEnginePolicy,
    ):
        self.readings = readings
        self.sources = sources
        self.policy = settings.market
        self.engine = engine

    async def fetch(self) -> MarketSnapshot:
        instruments = {
            SymbolCode(code): instrument
            for code, instrument in self.policy.instruments.items()
        }
        readings = await self.readings.get_many_by_symbols(list(instruments))
        source_rows = await self.sources.get_all()
        sources = {row.id: row for row in source_rows if row.is_active}
        now = utc_now()
        quotes = []
        for code, instrument in instruments.items():
            eligible = []
            for reading in readings.get(code, ()):
                source = sources.get(reading.source_id)
                age = (now - as_utc(reading.priced_at)).total_seconds()
                if (
                    source is None
                    or reading.is_closed
                    or min(
                        reading.price, reading.buy_price, reading.sell_price
                    )
                    <= 0
                    or reading.buy_price > reading.sell_price
                    or not -self.policy.future_skew_seconds
                    <= age
                    <= self.policy.max_age_seconds
                ):
                    continue
                eligible.append(reading)
            middle = median([row.price for row in eligible]) if eligible else 0
            for reading in eligible:
                if (
                    len(eligible) >= self.engine.min_outlier_sample
                    and abs(reading.price - middle)
                    > middle * self.engine.outlier_rate
                ):
                    continue
                source = sources[reading.source_id]
                dollars = reading.currency == CurrencyType.USD
                divisor = Decimal(100) if dollars else Decimal(1)
                quotes.append(
                    Quote(
                        **instrument.model_dump(),
                        amount=Decimal(reading.price) / divisor,
                        buy_amount=Decimal(reading.buy_price) / divisor,
                        sell_amount=Decimal(reading.sell_price) / divisor,
                        currency="USD" if dollars else "IRR",
                        quoted_at=as_utc(reading.priced_at),
                        timestamp_kind=reading.timestamp_kind,
                        source_code=source.code,
                        source_name=source.title,
                        source_url=HttpUrl(source.website_url),
                    )
                )
        if not quotes:
            raise ValueError("هیچ منبع فعالی قیمت معتبر و تازه ندارد.")
        return MarketSnapshot(mode="sources", quotes=quotes, fetched_at=now)
