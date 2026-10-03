from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from src.modules.publishing.interfaces import (
    IPrivateReplyService,
    IPublicationCommands,
    IPublicationRecovery,
    IReplyRecovery,
)


class DispatchPublication(RedisScheduler):
    def __init__(self, command: IPublicationCommands):
        self.command = command

    async def run(self, publication_id: int) -> None:
        await self.command.dispatch(publication_id)


class DispatchReply(RedisScheduler):
    def __init__(self, service: IPrivateReplyService):
        self.service = service

    async def run(self, reply_id: int) -> None:
        await self.service.dispatch(reply_id)


class RecoverPublications(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IPublicationRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()


class RecoverReplies(RedisScheduler):
    schedule = [{"interval": 5}]

    def __init__(self, recovery: IReplyRecovery):
        self.recovery = recovery

    async def run(self) -> None:
        await self.recovery.enqueue_pending()
