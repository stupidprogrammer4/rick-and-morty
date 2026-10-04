from dishka import Provider, Scope, provide

from src.modules.pricing.charts.app.queries import AssetChartQuery
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.infra.browser import (
    BrowserImageRenderer,
    ChartAssets,
)
from src.modules.pricing.charts.interfaces import (
    IAssetChartQuery,
    IAssetChartRenderer,
)


class ChartProvider(Provider):
    scope = Scope.REQUEST
    queries = provide(AssetChartQuery, provides=IAssetChartQuery)
    assets = provide(ChartAssets, scope=Scope.APP)
    browser = provide(BrowserImageRenderer, scope=Scope.APP)
    renderer = provide(AssetChartRenderer, provides=IAssetChartRenderer)
