import hashlib

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import DraftCreate, DraftOut
from portal_contracts.enums import BotRole, Category
from portal_contracts.presentation import PortalPresentation
from src.modules.content.drafts.domain.dtos import MarketDraftContext
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.pricing.reports.app.pages import MarketPageRenderer
from src.modules.pricing.reports.app.renderer import MarketReportRenderer
from src.modules.pricing.reports.domain.dtos import (
    MarketSnapshot,
    validate_freshness,
)
from src.modules.pricing.reports.domain.models import MarketSnapshotModel
from src.modules.pricing.reports.interfaces import IMarketSnapshotService
from src.shared.dates import utc_now


class MarketDraftCommands:
    def __init__(
        self,
        snapshots: IMarketSnapshotService,
        drafts: IDraftService,
        renderer: MarketReportRenderer,
        settings: PortalConfiguration,
        presentation: PortalPresentation,
        pages: MarketPageRenderer,
    ):
        self.snapshots = snapshots
        self.drafts = drafts
        self.renderer = renderer
        self.settings = settings
        self.presentation = presentation
        self.pages = pages

    async def from_snapshot(
        self, mission: MarketDraftContext, snapshot: MarketSnapshot
    ) -> DraftOut:
        policy = self.settings.market
        validate_freshness(
            snapshot,
            utc_now(),
            policy.max_age_seconds,
            policy.future_skew_seconds,
        )
        text = (
            self.pages.preview(self.pages.render(snapshot))
            if self.presentation.market_pagination_enabled
            else self.renderer.render(snapshot)
        )
        async with transaction():
            record = await self.snapshots.create(
                MarketSnapshotModel(
                    mission_id=mission.id,
                    owner_id=mission.owner_id,
                    payload=snapshot.model_dump_json(),
                    body_hash=hashlib.sha256(text.encode()).hexdigest(),
                )
            )
            draft = await self.drafts.create(
                mission.owner_id,
                BotRole(mission.origin_bot),
                DraftCreate(
                    category=Category.MARKET,
                    title=self.presentation.market_heading,
                    text=text,
                    publisher_bot=self.presentation.posts[
                        Category.MARKET
                    ].publisher_bot,
                ),
                key=f"mission:{mission.id}:market",
                mission_id=mission.id,
                market_snapshot_id=record.id,
            )
        return draft
