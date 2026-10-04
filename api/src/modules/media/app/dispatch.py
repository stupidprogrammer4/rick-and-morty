import asyncio
from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import (
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.ops.interfaces import IPortalGuard
from src.shared.dates import utc_now


class MediaDispatch:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        reader: MediaReader,
        queue: IMediaQueue,
        guard: IPortalGuard,
        policy: MediaPolicy,
    ):
        self.jobs = jobs
        self.items = items
        self.reader = reader
        self.queue = queue
        self.guard = guard
        self.policy = policy

    async def dispatch(self) -> None:
        if not self.policy.enabled:
            return
        async with transaction():
            # Serialize reservations for the global concurrency limit.
            await self.guard.lock("media-dispatch")
            now = utc_now()
            occupied = await self.reader.occupied(now)
            free = max(0, self.policy.concurrent_downloads - occupied)
            transfers = await self.reader.ready_items(now, free)
            transfer_ids = [ticket.item_id for ticket in transfers]
            lease = now + timedelta(
                seconds=self.policy.item_timeout_seconds + 420
            )
            await self.items.reserve_many(transfer_ids, lease)
            pending = await self.jobs.due(self.policy.active_global)
            plan_ids = [job.id for job in pending if job.total == 0][
                : max(0, free - len(transfers))
            ]
            await self.jobs.dispatch_many(plan_ids, lease)
            completed = await self.reader.finished_jobs()
            ready = await self.reader.ready_deliveries(now)
        await asyncio.gather(
            self.queue.transfer_many(transfer_ids),
            self.queue.plan_many(plan_ids),
            self.queue.complete_many(completed),
            self.queue.deliver_many(ready),
        )
