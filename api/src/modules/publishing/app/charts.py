import asyncio
import base64
from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import PublicationChartOut, PublicationResolution
from portal_contracts.enums import BotRole
from portal_contracts.telegram import TelegramPhotoDelivery
from src.modules.ops.interfaces import IPortalGuard
from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.domain.models import AssetChartCard
from src.modules.pricing.charts.interfaces import IAssetChartQuery
from src.modules.publishing.app.policy import PublicationPolicy
from src.modules.publishing.domain.models import (
    PublicationChartModel,
    PublicationModel,
)
from src.modules.publishing.infra.charts import (
    PublicationChartReader,
    PublicationChartRepository,
)
from src.modules.publishing.interfaces import ITelegramGateway
from src.shared.dates import as_utc, utc_now
from src.shared.errors import conflict, missing


class PublicationChartCommands:
    def __init__(
        self,
        repo: PublicationChartRepository,
        reader: PublicationChartReader,
        query: IAssetChartQuery,
        renderer: AssetChartRenderer,
        settings: PortalConfiguration,
        guard: IPortalGuard,
        gateway: ITelegramGateway,
    ):
        self.repo = repo
        self.reader = reader
        self.query = query
        self.renderer = renderer
        self.settings = settings
        self.guard = guard
        self.gateway = gateway
        self.policy = PublicationPolicy(settings.portal)

    async def schedule(self, publication: PublicationModel) -> None:
        if not self.settings.market.charts.enabled:
            return
        cards = await self.query.get_all()
        rows = []
        for card in cards:
            payload = card.model_dump_json()
            if len(payload.encode()) > 60000:
                raise ValueError("Frozen chart exceeds the storage limit")
            rows.append(
                PublicationChartModel(
                    publication_id=publication.id,
                    owner_id=publication.owner_id,
                    asset_id=card.asset.id,
                    payload=payload,
                    scheduled_at=publication.scheduled_at,
                    deadline=publication.deadline
                    + timedelta(
                        seconds=self.settings.portal.publication_timeout
                    ),
                )
            )
        await self.repo.create_all(rows)

    async def dispatch(self, chart_id: int) -> None:
        async with transaction():
            gate = await self.guard.lock("publishing")
            row = await self.repo.locked(chart_id)
            now = utc_now()
            if (
                row is None
                or row.status != "queued"
                or as_utc(row.scheduled_at) > now
            ):
                return
            if as_utc(row.deadline) <= now:
                row.status = "expired"
                await self.repo.save(row)
                return
            parent = await self.reader.parent(row.publication_id)
            if (
                parent is None
                or parent.status != "sent"
                or parent.message_id is None
            ):
                return
            if gate.paused or self.policy.quiet(now):
                return
            if parent.channel_id != self.settings.portal.channel_id:
                row.status = "failed"
                row.failure_reason = "publishing_channel_changed"
                await self.repo.save(row)
                return
            card = AssetChartCard.model_validate_json(row.payload)
            row.status = "rendering"
            row.lease_expires_at = now + timedelta(seconds=60)
            await self.repo.save(row)
        try:
            image = await asyncio.to_thread(self.renderer.render, card)
        except Exception:
            async with transaction():
                row = await self.repo.locked(chart_id)
                if row is not None and row.status == "rendering":
                    row.status = "failed"
                    row.failure_reason = "chart_render_failed"
                    await self.repo.save(row)
            return
        async with transaction():
            gate = await self.guard.lock("publishing")
            row = await self.repo.locked(chart_id)
            if row is None or row.status != "rendering":
                return
            if as_utc(row.deadline) <= utc_now():
                row.status = "expired"
                await self.repo.save(row)
                return
            if gate.paused or self.policy.quiet(utc_now()):
                row.status = "queued"
                await self.repo.save(row)
                return
            row.status = "sending"
            row.lease_expires_at = utc_now() + timedelta(seconds=60)
            await self.repo.save(row)
            delivery = TelegramPhotoDelivery(
                role=BotRole(parent.bot_role),
                chat_id=parent.channel_id,
                publication_id=parent.id,
                chart_id=chart_id,
                reply_to_message_id=parent.message_id,
                caption=card.caption,
                png_base64=base64.b64encode(image).decode("ascii"),
            )
        if self.settings.portal.dry_run:
            async with transaction():
                row = await self.repo.locked(chart_id)
                if row is not None:
                    row.status = "dry_run"
                    await self.repo.save(row)
            return
        result = await self.gateway.send_photo(delivery)
        async with transaction():
            row = await self.repo.locked(chart_id)
            if row is None or row.status != "sending":
                return
            row.message_id = result.message_id
            row.failure_reason = result.reason
            if result.status == "sent" and result.message_id is not None:
                row.status = "sent"
            elif result.status == "rate_limited" and result.retry_after:
                row.status = "queued"
                row.scheduled_at = utc_now() + timedelta(
                    seconds=result.retry_after
                )
            elif result.status == "failed":
                row.status = "failed"
            else:
                row.status = "unknown"
            await self.repo.save(row)

    async def resolve(
        self, id: int, owner_id: int, data: PublicationResolution
    ) -> PublicationChartOut:
        if (data.message_id is None) == (not data.resend):
            raise conflict("یا شناسهٔ پیام را بده یا ارسال دوباره را تأیید کن.")
        async with transaction():
            await self.guard.lock("publishing")
            row = await self.repo.locked(id)
            if row is None or row.owner_id != owner_id:
                raise missing("publication chart", id)
            if row.status != "unknown":
                raise conflict("فقط ارسال نامشخص قابل تعیین تکلیف است.")
            row.message_id = data.message_id
            row.status = "queued" if data.resend else "sent"
            if data.resend:
                row.scheduled_at = utc_now()
                row.deadline = utc_now() + timedelta(
                    seconds=self.settings.portal.publication_timeout
                )
            await self.repo.save(row)
            result = PublicationChartOut.model_validate(
                row, from_attributes=True
            )
        return result


class PublicationChartRecovery:
    def __init__(
        self, repo: PublicationChartRepository, reader: PublicationChartReader
    ):
        self.repo = repo
        self.reader = reader

    async def enqueue_pending(self) -> None:
        from src.modules.publishing.tasks.schedulers.dispatch import (
            DispatchChart,
        )

        async with transaction():
            now = utc_now()
            await self.repo.recover(now)
            ids = await self.reader.due(now, 100)
        await asyncio.gather(
            *(DispatchChart.enqueue(chart_id=id) for id in ids)
        )


class PublicationChartQuery:
    def __init__(self, reader: PublicationChartReader):
        self.reader = reader

    async def get_for_publication(
        self, publication_id: int, owner_id: int
    ) -> list[PublicationChartOut]:
        parent = await self.reader.parent(publication_id)
        if parent is None or parent.owner_id != owner_id:
            raise missing("publication", publication_id)
        rows = await self.reader.for_publication(publication_id, owner_id)
        return [
            PublicationChartOut.model_validate(row, from_attributes=True)
            for row in rows
        ]
