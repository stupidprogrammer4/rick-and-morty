from papilio.infra.db.tools.decorators import transactional

from src.modules.ops.domain.models import PortalGuardModel
from src.modules.ops.infra.mysql import PortalGuardRepository


class PortalGuardService:
    def __init__(self, repo: PortalGuardRepository):
        self.repo = repo

    async def lock(self, key: str) -> PortalGuardModel:
        result = await self.repo.lock(key)
        return result

    async def is_paused(self) -> bool:
        row = await self.repo.get("publishing")
        return row.paused if row is not None else False

    @transactional
    async def pause(self, paused: bool) -> None:
        await self.repo.lock("publishing")
        await self.repo.set_paused("publishing", paused)
