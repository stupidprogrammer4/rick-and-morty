from papilio.infra.db.transaction import transaction

from portal_contracts.content import DraftCreate, DraftOut
from portal_contracts.enums import BotRole
from src.modules.content.interfaces import IDraftService
from src.modules.ops.interfaces import IPortalGuard


class DraftAdmission:
    def __init__(self, drafts: IDraftService, guard: IPortalGuard):
        self.drafts = drafts
        self.guard = guard

    async def create_manual(
        self, owner_id: int, origin_bot: BotRole, data: DraftCreate, key: str
    ) -> DraftOut:
        async with transaction():
            await self.guard.lock(f"drafts:{owner_id}")
            result = await self.drafts.create(
                owner_id, origin_bot, data, key=key
            )
        return result
