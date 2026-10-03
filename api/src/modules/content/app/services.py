from papilio.infra.db.tools.decorators import transactional

from portal_contracts.content import (
    DraftCreate,
    DraftDecision,
    DraftEdit,
    DraftOut,
    DraftPage,
)
from portal_contracts.enums import BotRole
from portal_contracts.missions import PageRequest
from src.modules.content.domain.models import DraftModel
from src.modules.content.infra.mysql import DraftRepository
from src.shared.errors import conflict, missing


class DraftService:
    def __init__(self, repo: DraftRepository):
        self.repo = repo

    @transactional
    async def create(
        self,
        owner_id: int,
        origin_bot: BotRole,
        data: DraftCreate,
        *,
        key: str,
        mission_id: int | None = None,
        synthetic: bool = False,
        market_snapshot_id: int | None = None,
    ) -> DraftOut:
        if data.category == "market" and market_snapshot_id is None:
            raise conflict("قیمت‌ها باید از مأموریت /prices دریافت شوند.")
        existing = await self.repo.by_key(key)
        if existing is not None:
            if existing.owner_id != owner_id:
                raise missing("draft", existing.id)
            return DraftOut.model_validate(existing, from_attributes=True)
        model = await self.repo.create(
            DraftModel(
                **data.model_dump(mode="json"),
                owner_id=owner_id,
                origin_bot=origin_bot,
                idempotency_key=key,
                mission_id=mission_id,
                synthetic=synthetic,
                market_snapshot_id=market_snapshot_id,
            )
        )
        return DraftOut.model_validate(model, from_attributes=True)

    async def get(self, id: int, owner_id: int) -> DraftOut:
        model = await self.repo.get(id)
        if model is None or model.owner_id != owner_id:
            raise missing("draft", id)
        return DraftOut.model_validate(model, from_attributes=True)

    async def locked(self, id: int, owner_id: int) -> DraftModel:
        model = await self.repo.get(id, lock=True)
        if model is None or model.owner_id != owner_id:
            raise missing("draft", id)
        return model

    async def page(self, owner_id: int, data: PageRequest) -> DraftPage:
        rows, total = await self.repo.page(
            owner_id, (data.page - 1) * data.per_page, data.per_page
        )
        return DraftPage(
            items=[
                DraftOut.model_validate(row, from_attributes=True)
                for row in rows
            ],
            total=total,
            **data.model_dump(),
        )

    @transactional
    async def edit(self, id: int, owner_id: int, data: DraftEdit) -> DraftOut:
        model = await self.locked(id, owner_id)
        if model.revision != data.revision:
            raise conflict("نسخه پیش‌نویس تغییر کرده.")
        model.title = data.title
        model.text = data.text
        model.revision += 1
        model.approved_revision = None
        model.status = "draft"
        await self.repo.save(model)
        return DraftOut.model_validate(model, from_attributes=True)

    @transactional
    async def decide(
        self, id: int, owner_id: int, data: DraftDecision, *, approve: bool
    ) -> DraftOut:
        model = await self.locked(id, owner_id)
        if (
            model.revision != data.revision
            or model.origin_bot != data.origin_bot
        ):
            raise conflict("این تأیید متعلق به نسخه یا بات فعلی نیست.")
        model.status = "approved" if approve else "rejected"
        model.approved_revision = data.revision if approve else None
        await self.repo.save(model)
        return DraftOut.model_validate(model, from_attributes=True)
