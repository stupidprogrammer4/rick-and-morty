from dishka import Provider, Scope, provide

from src.modules.pricing.charts.app.global_gold import GlobalGoldChartQuery
from src.modules.pricing.charts.app.queries import AssetChartQuery
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.infra.browser import (
    BrowserImageRenderer,
    ChartAssets,
)
from src.modules.pricing.charts.infra.global_gold import GlobalGoldSeries
from src.modules.pricing.charts.infra.images import ChartImageCache
from src.modules.pricing.charts.interfaces import (
    IAssetChartQuery,
    IAssetChartRenderer,
    IChartImageCache,
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
    images = provide(
        ChartImageCache, provides=IChartImageCache, scope=Scope.APP
    )

    @provide(scope=Scope.APP)
    def renderer(
        self,
        browser: BrowserImageRenderer,
        assets: ChartAssets,
        cache: IChartImageCache,
    ) -> IAssetChartRenderer:
        return AssetChartRenderer(browser, assets, cache)
