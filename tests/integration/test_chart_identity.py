import pytest

from portal_contracts.configuration import SettingScope
from src.modules.pricing.calculator.interfaces import ICacheReaderService
from src.modules.pricing.charts.interfaces import IAssetChartQuery
from tests.integration.test_publication_charts import prepare_charts

pytestmark = pytest.mark.integration


def test_chart_card_freezes_validated_price_and_asset_identity(portal):
    async def workflow():
        await prepare_charts(portal)
        snapshot = await portal.snapshot()
        market = snapshot.configuration.market.model_dump(mode="json")
        market["charts"].update(
            asset_display_symbols={"usd": "USD"},
            asset_logos={"usd": "usd.svg"},
        )
        await portal.change("market.policy", SettingScope.GLOBAL, market)
        async with portal.request() as scope:
            cards = await (await scope.get(IAssetChartQuery)).get_all()
            prices = await (
                await scope.get(ICacheReaderService)
            ).get_all_prices()
            expected = {row.asset_id: row for row in prices}
            assert len(cards) == 4
            for card in cards:
                price = expected[card.asset.id]
                assert card.quote.price == price.price
                assert card.quote.priced_at == price.priced_at
            usd = next(
                card for card in cards if card.asset.code.value == "usd"
            )
            assert usd.style.asset_display_symbols["usd"] == "USD"
            assert usd.style.asset_logos["usd"] == "usd.svg"
        async with portal.request() as scope:
            card = await (await scope.get(IAssetChartQuery)).get(usd.asset.id)
            assert card.quote.price == expected[usd.asset.id].price

    portal.run(workflow())
