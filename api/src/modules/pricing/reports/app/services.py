from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.reports.domain.models import MarketSnapshotModel
from src.modules.pricing.reports.infra.mysql import MarketSnapshotRepository
from src.shared.errors import missing


class MarketSnapshotService:
    def __init__(self, repo: MarketSnapshotRepository):
        self.repo = repo

    @transactional
    async def create(self, data: MarketSnapshotModel) -> MarketSnapshotModel:
        existing = await self.repo.by_mission(data.mission_id)
        if existing is not None:
            return existing
        row = await self.repo.create(data)
        return row

    async def get(self, id: int, owner_id: int) -> MarketSnapshotModel:
        row = await self.repo.get(id)
        if row is None or row.owner_id != owner_id:
            raise missing("market_snapshot", id)
        return row
