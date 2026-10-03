from dishka import Provider, Scope, provide

from src.modules.publishing.app.commands import PublicationCommands
from src.modules.publishing.app.recovery import (
    PublicationRecovery,
    ReplyRecovery,
)
from src.modules.publishing.app.renderer import PostRenderer
from src.modules.publishing.app.replies import PrivateReplyService
from src.modules.publishing.infra.gateway import TelegramGateway
from src.modules.publishing.infra.mysql import (
    PrivateReplyRepository,
    PublicationRepository,
)
from src.modules.publishing.interfaces import (
    IPrivateReplyService,
    IPublicationCommands,
    IPublicationRecovery,
    IReplyRecovery,
    ITelegramGateway,
)
from src.modules.publishing.tasks.schedulers.dispatch import (
    DispatchPublication,
    DispatchReply,
    RecoverPublications,
    RecoverReplies,
)


class PublishingProvider(Provider):
    scope = Scope.REQUEST
    publications = provide(PublicationRepository)
    renderer = provide(PostRenderer)
    replies = provide(PrivateReplyRepository)
    gateway = provide(TelegramGateway, provides=ITelegramGateway)
    command = provide(PublicationCommands, provides=IPublicationCommands)
    reply_service = provide(PrivateReplyService, provides=IPrivateReplyService)
    publication_recovery = provide(
        PublicationRecovery, provides=IPublicationRecovery
    )
    reply_recovery = provide(ReplyRecovery, provides=IReplyRecovery)
    dispatch_task = provide(DispatchPublication)
    reply_task = provide(DispatchReply)
    recover_task = provide(RecoverPublications)
    recover_reply_task = provide(RecoverReplies)
