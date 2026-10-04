import hashlib
from datetime import datetime

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import PublicationPages
from portal_contracts.presentation import PortalPresentation
from src.modules.content.drafts.domain.models import DraftModel
from src.modules.pricing.reports.app.pages import MarketPageRenderer
from src.modules.pricing.reports.domain.dtos import (
    MarketSnapshot,
    validate_freshness,
)
from src.modules.pricing.reports.interfaces import IMarketSnapshotService
from src.shared.errors import conflict


class MarketPublicationQuery:
    def __init__(
        self,
        snapshots: IMarketSnapshotService,
        settings: PortalConfiguration,
        pages: MarketPageRenderer,
        presentation: PortalPresentation,
    ):
        self.snapshots = snapshots
        self.settings = settings
        self.pages = pages
        self.presentation = presentation

    async def render_pages(self, draft: DraftModel) -> PublicationPages | None:
        if not self.presentation.market_pagination_enabled:
            return None
        if draft.market_snapshot_id is None:
            raise conflict("قیمت ثبت‌شده برای صفحه‌بندی موجود نیست.")
        record = await self.snapshots.get(
            draft.market_snapshot_id, draft.owner_id
        )
        snapshot = MarketSnapshot.model_validate_json(record.payload)
        return self.pages.render(snapshot)

    async def validate(self, draft: DraftModel, now: datetime) -> None:
        if draft.market_snapshot_id is None:
            raise conflict("پیش‌نویس بازار به قیمت ثبت‌شده متصل نیست.")
        record = await self.snapshots.get(
            draft.market_snapshot_id, draft.owner_id
        )
        if record.body_hash != hashlib.sha256(draft.text.encode()).hexdigest():
            raise conflict("متن قیمت تغییر کرده؛ قیمت تازه دریافت کن.")
        snapshot = MarketSnapshot.model_validate_json(record.payload)
        policy = self.settings.market
        if not policy.enabled:
            raise conflict("منبع بازار غیرفعال است.")
        try:
            validate_freshness(
                snapshot,
                now,
                policy.max_age_seconds,
                policy.future_skew_seconds,
            )
        except ValueError as exc:
            raise conflict(str(exc)) from exc
