from dishka import Provider, Scope, provide

from src.modules.pricing.charts.app.global_gold import GlobalGoldChartQuery
from src.modules.pricing.charts.app.queries import AssetChartQuery
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.infra.browser import (
    BrowserImageRenderer,
    ChartAssets,
)
from src.modules.pricing.charts.infra.global_gold import GlobalGoldSeries
from src.modules.pricing.charts.interfaces import (
    IAssetChartQuery,
    IAssetChartRenderer,
    IGlobalGoldChartQuery,
    IGlobalGoldSeries,
)


class ChartProvider(Provider):
    scope = Scope.REQUEST
    global_series = provide(GlobalGoldSeries, provides=IGlobalGoldSeries)
    global_gold = provide(GlobalGoldChartQuery, provides=IGlobalGoldChartQuery)
    queries = provide(AssetChartQuery, provides=IAssetChartQuery)
    assets = provide(ChartAssets, scope=Scope.APP)
    browser = provide(BrowserImageRenderer, scope=Scope.APP)
    renderer = provide(AssetChartRenderer, provides=IAssetChartRenderer)
