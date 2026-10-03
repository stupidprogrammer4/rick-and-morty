import hashlib
from datetime import datetime

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.content import DraftCreate, DraftOut
from portal_contracts.enums import BotRole, Category
from portal_contracts.presentation import PortalPresentation
from src.modules.content.domain.models import DraftModel
from src.modules.content.interfaces import IDraftService
from src.modules.market.app.renderer import MarketReportRenderer
from src.modules.market.domain.dtos import MarketSnapshot, validate_freshness
from src.modules.market.domain.models import MarketSnapshotModel
from src.modules.market.interfaces import IMarketSnapshotService
from src.modules.missions.domain.models import MissionModel
from src.shared.dates import utc_now
from src.shared.errors import conflict


class MarketDraftCommands:
    def __init__(
        self,
        snapshots: IMarketSnapshotService,
        drafts: IDraftService,
        renderer: MarketReportRenderer,
        settings: PortalConfiguration,
        presentation: PortalPresentation,
    ):
        self.snapshots = snapshots
        self.drafts = drafts
        self.renderer = renderer
        self.settings = settings
        self.presentation = presentation

    async def from_snapshot(
        self, mission: MissionModel, snapshot: MarketSnapshot
    ) -> DraftOut:
        policy = self.settings.market
        validate_freshness(
            snapshot,
            utc_now(),
            policy.max_age_seconds,
            policy.future_skew_seconds,
        )
        text = self.renderer.render(snapshot)
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


class MarketPublicationQuery:
    def __init__(
        self, snapshots: IMarketSnapshotService, settings: PortalConfiguration
    ):
        self.snapshots = snapshots
        self.settings = settings

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
