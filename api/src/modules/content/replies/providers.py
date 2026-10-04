from dishka import Provider, Scope, provide

from src.modules.content.replies.app.recovery import ReplyRecovery
from src.modules.content.replies.app.services import PrivateReplyService
from src.modules.content.replies.infra.mysql import PrivateReplyRepository
from src.modules.content.replies.interfaces import (
    IPrivateReplyService,
    IReplyRecovery,
)
from src.modules.content.replies.tasks.schedulers.dispatch import (
    DispatchReply,
    RecoverReplies,
)


class ReplyProvider(Provider):
    scope = Scope.REQUEST
    replies = provide(PrivateReplyRepository)
    reply_service = provide(PrivateReplyService, provides=IPrivateReplyService)
    reply_recovery = provide(ReplyRecovery, provides=IReplyRecovery)
    reply_task = provide(DispatchReply)
    recover_reply_task = provide(RecoverReplies)
