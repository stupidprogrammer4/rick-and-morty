from dishka import Provider, Scope, provide

from src.modules.pricing.charts.app.queries import AssetChartQuery
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.interfaces import IAssetChartQuery


class ChartProvider(Provider):
    scope = Scope.REQUEST
    queries = provide(AssetChartQuery, provides=IAssetChartQuery)
    renderer = provide(AssetChartRenderer)
