from dishka import Provider, Scope, provide

from src.modules.content.news.app.services import ArticleService
from src.modules.content.news.infra.mysql import ArticleRepository
from src.modules.content.news.infra.sources import NewsCollector
from src.modules.content.news.interfaces import IArticleService, INewsCollector


class NewsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(ArticleRepository)
    collector = provide(NewsCollector, provides=INewsCollector)
    articles = provide(ArticleService, provides=IArticleService)
