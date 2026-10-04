from dishka import Provider, Scope, provide

from src.modules.media.storage.app.workspace import MediaWorkspace
from src.modules.media.storage.infra.files import MediaFiles
from src.modules.media.storage.interfaces import IMediaWorkspace


class MediaStorageProvider(Provider):
    scope = Scope.REQUEST
    files = provide(MediaFiles)
    workspace = provide(MediaWorkspace, provides=IMediaWorkspace)
