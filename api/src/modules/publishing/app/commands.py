from datetime import timedelta
from zoneinfo import ZoneInfo

from papilio.errors.exceptions import ConflictException
from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import (
    PublicationOut,
    PublicationPages,
    PublicationResolution,
    PublishRequest,
)
from portal_contracts.enums import BotRole
from portal_contracts.telegram import TelegramDelivery
from src.modules.content.interfaces import IDraftService
from src.modules.market.interfaces import IMarketPublicationQuery
from src.modules.ops.interfaces import IPortalGuard
from src.modules.publishing.app.policy import PublicationPolicy
from src.modules.publishing.app.renderer import PostRenderer
from src.modules.publishing.domain.models import PublicationModel
from src.modules.publishing.infra.mysql import PublicationRepository
from src.modules.publishing.interfaces import (
    IPublicationChartCommands,
    ITelegramGateway,
)
from src.shared.dates import as_utc, utc_now
from src.shared.errors import conflict, missing


class PublicationCommands:
    def __init__(
        self,
        repo: PublicationRepository,
        drafts: IDraftService,
        guard: IPortalGuard,
        gateway: ITelegramGateway,
        settings: PortalConfiguration,
        renderer: PostRenderer,
        market: IMarketPublicationQuery,
        charts: IPublicationChartCommands,
    ):
        self.repo = repo
        self.drafts = drafts
        self.guard = guard
        self.gateway = gateway
        self.settings = settings
        self.renderer = renderer
        self.market = market
        self.charts = charts
        self.policy = PublicationPolicy(settings.portal)

    async def schedule(
        self, draft_id: int, owner_id: int, data: PublishRequest
    ) -> PublicationOut:
        now = utc_now()
        scheduled = data.scheduled_at or now
        if scheduled < now - timedelta(seconds=5):
            raise conflict("زمان انتشار گذشته است.")
        async with transaction():
            await self.guard.lock("publishing")
            draft = await self.drafts.locked(draft_id, owner_id)
            if (
                draft.status != "approved"
                or draft.revision != data.revision
                or draft.approved_revision != data.revision
                or draft.origin_bot != data.origin_bot
            ):
                raise conflict("نسخه فعلی پیش‌نویس را تأیید کن.")
            if draft.synthetic and not self.settings.portal.dry_run:
                raise conflict("محتوای آزمایشی قابل نشر زنده نیست.")
            if draft.category == "market":
                await self.market.validate(draft, now)
            key = f"draft:{draft_id}:revision:{data.revision}"
            existing = await self.repo.by_key(key)
            if existing is not None:
                return PublicationOut.model_validate(
                    existing, from_attributes=True
                )
            pages = (
                await self.market.render_pages(draft)
                if draft.category == "market"
                else None
            )
            frozen_pages = pages.model_dump_json() if pages else None
            if frozen_pages is not None and len(frozen_pages.encode()) > 60000:
                raise ValueError("Publication pages exceed the storage limit")
            row = await self.repo.create(
                PublicationModel(
                    pages=frozen_pages,
                    owner_id=owner_id,
                    draft_id=draft_id,
                    revision=data.revision,
                    key=key,
                    bot_role=draft.publisher_bot,
                    channel_id=self.settings.portal.channel_id or 0,
                    scheduled_at=scheduled,
                    deadline=scheduled
                    + timedelta(
                        seconds=self.settings.portal.publication_timeout
                    ),
                )
            )
            if draft.category == "market":
                await self.charts.schedule(row)
            result = PublicationOut.model_validate(row, from_attributes=True)
        return result

    async def dispatch(self, publication_id: int) -> None:
        now = utc_now()
        async with transaction():
            guard = await self.guard.lock("publishing")
            row = await self.repo.get(publication_id, lock=True)
            if row is None or row.status != "queued":
                return
            if as_utc(row.scheduled_at) > now:
                return
            if as_utc(row.deadline) <= now:
                row.status = "expired"
                await self.repo.save(row)
                return
            if guard.paused or self.policy.quiet(now):
                return
            draft = await self.drafts.locked(row.draft_id, row.owner_id)
            if (
                draft.status != "approved"
                or draft.revision != row.revision
                or draft.approved_revision != row.revision
            ):
                row.status = "cancelled"
                await self.repo.save(row)
                return
            if draft.category == "market":
                try:
                    await self.market.validate(draft, now)
                except ConflictException:
                    row.status = "failed"
                    row.failure_reason = "market_quote_invalid_or_expired"
                    await self.repo.save(row)
                    return
            if not self.settings.portal.dry_run and (
                self.settings.portal.channel_id is None
                or row.channel_id != self.settings.portal.channel_id
            ):
                row.status = "failed"
                row.failure_reason = "publishing_channel_not_configured"
                await self.repo.save(row)
                return
            day = now.astimezone(
                ZoneInfo(self.settings.portal.timezone)
            ).date()
            count = await self.repo.day_count(day)
            if count >= self.settings.portal.daily_post_cap:
                return
            row.budget_day = day
            pages = (
                PublicationPages.model_validate_json(row.pages)
                if row.pages
                else None
            )
            try:
                row.payload = (
                    pages.items[0].text
                    if pages
                    else self.renderer.render(
                        draft.title, draft.text, draft.category
                    )
                )
            except ValueError:
                row.status = "failed"
                row.budget_day = None
                row.failure_reason = "post_exceeds_message_limit"
                await self.repo.save(row)
                return
            row.status = "sending"
            row.lease_expires_at = now + timedelta(seconds=60)
            await self.repo.save(row)
            delivery = TelegramDelivery(
                role=BotRole(row.bot_role),
                chat_id=row.channel_id,
                text=row.payload,
                publication_id=row.id,
                navigation=pages.navigation(row.id, 0) if pages else None,
            )
        if self.settings.portal.dry_run:
            async with transaction():
                row = await self.repo.get(publication_id, lock=True)
                if row is not None:
                    row.status = "dry_run"
                    row.budget_day = None
                    await self.repo.save(row)
            return
        result = await self.gateway.send(delivery)
        async with transaction():
            row = await self.repo.get(publication_id, lock=True)
            if row is None or row.status != "sending":
                return
            row.message_id = result.message_id
            row.failure_reason = result.reason
            if result.status == "sent" and result.message_id is not None:
                row.status = "sent"
            elif result.status == "rate_limited" and result.retry_after:
                row.status = "queued"
                row.budget_day = None
                row.scheduled_at = utc_now() + timedelta(
                    seconds=result.retry_after
                )
            elif result.status == "failed":
                row.status = "failed"
                row.budget_day = None
            else:
                row.status = "unknown"
            await self.repo.save(row)

    async def resolve(
        self, id: int, owner_id: int, data: PublicationResolution
    ) -> PublicationOut:
        if (data.message_id is None) == (not data.resend):
            raise conflict("یا شناسه پیام را بده یا ارسال دوباره را تأیید کن.")
        async with transaction():
            await self.guard.lock("publishing")
            row = await self.repo.get(id, lock=True)
            if row is None or row.owner_id != owner_id:
                raise missing("publication", id)
            if row.status != "unknown":
                raise conflict("فقط ارسال نامشخص قابل تعیین تکلیف است.")
            row.message_id = data.message_id
            row.status = "queued" if data.resend else "sent"
            if data.resend:
                row.budget_day = None
                row.scheduled_at = utc_now()
                row.deadline = utc_now() + timedelta(
                    seconds=self.settings.portal.publication_timeout
                )
            await self.repo.save(row)
            result = PublicationOut.model_validate(row, from_attributes=True)
        return result
