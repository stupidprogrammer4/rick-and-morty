import asyncio

from papilio.infra.db.transaction import transaction

from src.modules.content.replies.infra.mysql import PrivateReplyRepository
from src.shared.dates import utc_now


class ReplyRecovery:
    def __init__(self, repo: PrivateReplyRepository):
        self.repo = repo

    async def enqueue_pending(self) -> None:
        from src.modules.content.replies.tasks.schedulers.dispatch import (
            DispatchReply,
        )

        async with transaction():
            await self.repo.recover_sending(utc_now())
            rows = await self.repo.due(100)
            ids = [row.id for row in rows]
        await asyncio.gather(
            *(DispatchReply.enqueue(reply_id=id) for id in ids)
        )
