from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.content.replies.interfaces import (
    IPrivateReplyService,
    IReplyRecovery,
)


class DispatchReply(RedisScheduler):
    def __init__(self, service: IPrivateReplyService):
        self.service = service

    async def run(self, reply_id: int) -> None:
        await self.service.dispatch(reply_id)


class RecoverReplies(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IReplyRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()
