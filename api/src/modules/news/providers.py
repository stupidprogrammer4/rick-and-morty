from dishka import Provider, Scope, provide

from src.modules.news.app.services import ArticleService
from src.modules.news.infra.mysql import ArticleRepository
from src.modules.news.infra.sources import NewsCollector
from src.modules.news.interfaces import IArticleService, INewsCollector


class NewsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(ArticleRepository)
    collector = provide(NewsCollector, provides=INewsCollector)
    articles = provide(ArticleService, provides=IArticleService)
