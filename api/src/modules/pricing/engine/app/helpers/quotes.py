from typing import Sequence

from papilio.utils import dates as date_utils

from src.modules.pricing.engine.domain.models import (
    FeeModel,
    PricedSourceModel,
)
from src.modules.pricing.engine.domain.quotes import (
    GlobalSourceQuote,
    IranSourceQuote,
    SupplierSourceQuote,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode
from src.tools.currency import round_rial


class IranMarketPriceHelper:
    def build(
        self,
        symbol_ids: dict[SymbolCode, int],
        source_ids: dict[SourceCode, int],
        iran_quotes: Sequence[IranSourceQuote],
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Turn the quotes of the local market into priced readings.
        Args:
            symbol_ids (dict[SymbolCode, int]): ID of each known symbol.
            source_ids (dict[SourceCode, int]): ID of each known source.
            iran_quotes (Sequence[IranSourceQuote]): Quotes as crawled.
        Returns:
            return (Sequence[PricedSourceModel]): Readings to be folded.
        """
        readings = []
        for quote in iran_quotes:
            source_id = source_ids.get(quote.code)
            symbol_id = symbol_ids.get(quote.symbol)
            if source_id is None or symbol_id is None:
                continue
            fee = None
            if quote.fee is not None:
                fee = FeeModel(
                    buy_fee_rate=quote.fee.buy_rate,
                    sell_fee_rate=quote.fee.sell_rate,
                    buy_fee_rial=quote.buy_fee_rial,
                    sell_fee_rial=quote.sell_fee_rial,
                )
            price = quote.price_rial
            divisor = price or 1
            readings.append(
                PricedSourceModel(
                    source_id=source_id,
                    symbol_id=symbol_id,
                    currency=CurrencyType.RIAL,
                    buy_price=quote.buy_price_rial,
                    sell_price=quote.sell_price_rial,
                    price=price,
                    buy_spread=quote.buy_fee_rial,
                    sell_spread=quote.sell_fee_rial,
                    buy_spread_rate=quote.buy_fee_rial / divisor,
                    sell_spread_rate=quote.sell_fee_rial / divisor,
                    priced_at=quote.quoted_at or date_utils.utc_now(),
                    timestamp_kind="source" if quote.quoted_at else "fetched",
                    fee=fee,
                )
            )
        return readings


class GlobalMarketPriceHelper:
    def build(
        self,
        symbol_ids: dict[SymbolCode, int],
        source_ids: dict[SourceCode, int],
        global_quotes: Sequence[GlobalSourceQuote],
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Turn the quotes of the foreign market into priced readings.
        Args:
            symbol_ids (dict[SymbolCode, int]): ID of each known symbol.
            source_ids (dict[SourceCode, int]): ID of each known source.
            global_quotes (Sequence[GlobalSourceQuote]): Quotes as crawled.
        Returns:
            return (Sequence[PricedSourceModel]): Readings to be folded.
        """
        readings = []
        for quote in global_quotes:
            source_id = source_ids.get(quote.code)
            symbol_id = symbol_ids.get(quote.symbol)
            if source_id is None or symbol_id is None:
                continue
            price = round((quote.selling_cent + quote.buying_cent) / 2)
            sell_spread = quote.selling_cent - price
            buy_spread = price - quote.buying_cent
            divisor = price or 1
            readings.append(
                PricedSourceModel(
                    source_id=source_id,
                    symbol_id=symbol_id,
                    currency=CurrencyType.USD,
                    buy_price=quote.buying_cent,
                    sell_price=quote.selling_cent,
                    price=price,
                    buy_spread=buy_spread,
                    sell_spread=sell_spread,
                    buy_spread_rate=buy_spread / divisor,
                    sell_spread_rate=sell_spread / divisor,
                    priced_at=quote.quoted_at or date_utils.utc_now(),
                    timestamp_kind="source" if quote.quoted_at else "fetched",
                )
            )
        return readings


class SupplierMarketPriceHelper:
    def build(
        self,
        symbol_ids: dict[SymbolCode, int],
        source_ids: dict[SourceCode, int],
        supplier_quotes: Sequence[SupplierSourceQuote],
    ) -> Sequence[PricedSourceModel]:
        """
        Desc: Turn the quotes of the suppliers into priced readings.
        Args:
            symbol_ids (dict[SymbolCode, int]): ID of each known symbol.
            source_ids (dict[SourceCode, int]): ID of each known source.
            supplier_quotes (Sequence[SupplierSourceQuote]): Quotes crawled.
        Returns:
            return (Sequence[PricedSourceModel]): Readings to be folded.
        """
        readings = []
        for quote in supplier_quotes:
            source_id = source_ids.get(quote.code)
            symbol_id = symbol_ids.get(quote.symbol)
            if source_id is None or symbol_id is None:
                continue
            price = round_rial(
                (quote.selling_mazane + quote.buying_mazane) / 2
            )
            sell_spread = quote.selling_mazane - price
            buy_spread = price - quote.buying_mazane
            divisor = price or 1
            readings.append(
                PricedSourceModel(
                    source_id=source_id,
                    symbol_id=symbol_id,
                    currency=CurrencyType.RIAL,
                    buy_price=quote.buying_mazane,
                    sell_price=quote.selling_mazane,
                    price=price,
                    buy_spread=buy_spread,
                    sell_spread=sell_spread,
                    buy_spread_rate=buy_spread / divisor,
                    sell_spread_rate=sell_spread / divisor,
                    priced_at=quote.quoted_at or date_utils.utc_now(),
                    timestamp_kind="source" if quote.quoted_at else "fetched",
                    is_closed=quote.is_closed,
                )
            )
        return readings
