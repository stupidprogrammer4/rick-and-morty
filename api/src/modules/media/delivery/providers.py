from dishka import Provider, Scope, provide

from src.modules.media.delivery.app.renderer import MediaCaptionRenderer
from src.modules.media.delivery.infra.gateway import MediaGateway
from src.modules.media.delivery.interfaces import IMediaGateway


class MediaDeliveryProvider(Provider):
    scope = Scope.REQUEST
    gateway = provide(MediaGateway, provides=IMediaGateway)
    captions = provide(MediaCaptionRenderer)
