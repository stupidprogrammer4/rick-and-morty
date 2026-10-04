from dishka import Provider, Scope, provide

from src.media_tasks.schedulers import CleanMedia, ExecuteMedia, RecoverMedia


class MediaTaskProvider(Provider):
    scope = Scope.REQUEST
    execute = provide(ExecuteMedia)
    recover = provide(RecoverMedia)
    clean = provide(CleanMedia)
