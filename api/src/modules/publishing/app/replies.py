from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.enums import BotRole
from portal_contracts.telegram import TelegramDelivery
from src.modules.publishing.domain.models import PrivateReplyModel
from src.modules.publishing.infra.mysql import PrivateReplyRepository
from src.modules.publishing.interfaces import ITelegramGateway
from src.shared.dates import as_utc, utc_now


class PrivateReplyService:
    def __init__(
        self, repo: PrivateReplyRepository, gateway: ITelegramGateway
    ):
        self.repo = repo
        self.gateway = gateway

    async def create(self, data: PrivateReplyModel) -> None:
        await self.repo.create(data)

    async def dispatch(self, id: int) -> None:
        async with transaction():
            row = await self.repo.get(id)
            if (
                row is None
                or row.status != "queued"
                or as_utc(row.scheduled_at) > utc_now()
            ):
                return
            row.status = "sending"
            row.lease_expires_at = utc_now() + timedelta(seconds=60)
            await self.repo.save(row)
            delivery = TelegramDelivery(
                role=BotRole(row.origin_bot),
                chat_id=row.owner_id,
                text=row.text,
                draft_id=row.draft_id,
                revision=row.revision,
            )
        result = await self.gateway.send(delivery)
        async with transaction():
            row = await self.repo.get(id)
            if row is not None and row.status == "sending":
                if result.status == "rate_limited" and result.retry_after:
                    row.status = "queued"
                    row.scheduled_at = utc_now() + timedelta(
                        seconds=result.retry_after
                    )
                else:
                    row.status = result.status
                row.failure_reason = result.reason
                row.message_id = result.message_id
                await self.repo.save(row)
