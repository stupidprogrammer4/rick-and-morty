import asyncio

from papilio.infra.db.transaction import transaction

from src.modules.automation.missions.infra.mysql import MissionRepository
from src.shared.dates import utc_now


class MissionRecovery:
    def __init__(self, repo: MissionRepository):
        self.repo = repo

    async def enqueue_pending(self) -> None:
        from src.modules.automation.missions.tasks.schedulers.execute import (
            ExecuteMission,
        )

        async with transaction():
            await self.repo.expire_running(utc_now())
            rows = await self.repo.due(100)
            ids = [row.id for row in rows]
        await asyncio.gather(
            *(ExecuteMission.enqueue(mission_id=id) for id in ids)
        )
