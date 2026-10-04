from datetime import timedelta
from html import escape

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.presentation import PortalPresentation
from src.modules.pricing.assets.domain.models import AssetModel
from src.modules.pricing.assets.interfaces import IAssetService
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.calculator.interfaces import ICacheReaderService
from src.modules.pricing.candle.app.helpers import ChartWindow
from src.modules.pricing.candle.domain.dtos import ParamDTO
from src.modules.pricing.candle.domain.models import CandleChartModel
from src.modules.pricing.candle.interfaces import ICandleService
from src.modules.pricing.charts.domain.models import (
    AssetChartCard,
    ChartAsset,
    ChartQuote,
)
from src.modules.pricing.ticker.domain.enums import ChartType
from src.shared.dates import utc_now


class AssetChartQuery:
    def __init__(
        self,
        assets: IAssetService,
        candles: ICandleService,
        prices: ICacheReaderService,
        settings: PortalConfiguration,
        presentation: PortalPresentation,
    ):
        self.assets = assets
        self.candles = candles
        self.prices = prices
        self.settings = settings
        self.presentation = presentation

    def window(self) -> ParamDTO:
        now = utc_now()
        span = ChartType(self.settings.market.charts.window).span
        return ParamDTO(
            from_datetime=now - timedelta(seconds=span), to_datetime=now
        )

    def card(
        self,
        asset: AssetModel,
        chart: CandleChartModel,
        price: AssetPriceModel | None,
    ) -> AssetChartCard:
        style = self.settings.market.charts
        symbol = style.asset_symbols.get(asset.code.value)
        decoration = self.presentation.asset_styles.get(symbol or "")
        title = (
            f"{decoration.emoji} {asset.title}" if decoration else asset.title
        )
        candle_data = chart.model_copy(
            update={
                "candles": [
                    row
                    for row in chart.candles
                    if row.en_ts <= chart.to_timestamp
                    and 0 < row.low <= min(row.open, row.close)
                    and max(row.open, row.close) <= row.high
                ],
            }
        )
        caption = f"<b>{escape(title)}</b>\n\n{escape(style.caption)}"
        if decoration:
            caption += "\n\n" + escape(decoration.hashtag)
        caption += (
            '\n\n📊 <a href="https://www.tradingview.com/">'
            "TradingView Lightweight Charts™</a>"
            " · © 2025 TradingView, Inc."
        )
        return AssetChartCard(
            asset=ChartAsset.from_obj(asset),
            chart=candle_data,
            style=style,
            timezone=self.settings.portal.timezone,
            caption=caption,
            quote=ChartQuote.model_validate(price, from_attributes=True)
            if price is not None
            else None,
        )

    async def get(self, asset_id: int) -> AssetChartCard:
        asset = await self.assets.get_by_id(asset_id)
        result = await self.candles.get_candle(asset_id, self.window())
        price = await self.prices.get_price(asset.code)
        return self.card(asset, result.data, price)

    async def get_all(self) -> list[AssetChartCard]:
        assets = await self.assets.get_all()
        param = self.window()
        result = await self.candles.get_all_candles(param)
        prices = await self.prices.get_prices([asset.code for asset in assets])
        window = ChartWindow()
        empty = CandleChartModel(
            timeframe=window.timeframe(window.days(param)),
            candles=[],
            from_timestamp=int(param.from_datetime.timestamp()),
            to_timestamp=int(param.to_datetime.timestamp()),
        )
        return [
            self.card(
                asset, result.data.get(asset.id, empty), prices.get(asset.code)
            )
            for asset in assets
        ]
