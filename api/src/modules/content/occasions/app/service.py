import asyncio

from amupouya_calendar.engine import catalogue
from amupouya_calendar.models import CalendarEntry
from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.tools.decorators import transactional

from src.modules.content.occasions.domain.dtos import (
    OccasionChange,
    OccasionOut,
    OccasionPage,
    OccasionUpdate,
    OccasionWrite,
)
from src.modules.content.occasions.domain.models import OccasionModel
from src.modules.content.occasions.infra.mysql import OccasionRepository


class OccasionService:
    def __init__(self, repo: OccasionRepository):
        self.repo = repo

    def output(self, row: OccasionModel) -> OccasionOut:
        return OccasionOut(
            entry=CalendarEntry.model_validate_json(row.definition),
            enabled=row.enabled,
            revision=row.revision,
        )

    async def get(self, key: str) -> OccasionOut:
        row = await self.repo.by_key(key)
        if row is None:
            raise NotFoundException(
                "Occasion not found",
                "record_not_found",
                "occasion",
                "key",
                key,
            )
        return self.output(row)

    async def search(
        self, query: str, page: int, per_page: int
    ) -> OccasionPage:
        rows = await self.repo.page(query, page, per_page)
        total = await self.repo.count(query)
        return OccasionPage(
            items=[self.output(row) for row in rows],
            page=page,
            per_page=per_page,
            total=total,
        )

    @transactional
    async def create(self, data: OccasionWrite) -> OccasionOut:
        if await self.repo.by_key(data.entry.id) is not None:
            raise ValueError("Occasion ID already exists")
        row = await self.repo.create(
            OccasionModel(
                key=data.entry.id,
                definition=data.entry.model_dump_json(),
                enabled=data.enabled,
            )
        )
        return self.output(row)

    @transactional
    async def update(self, key: str, data: OccasionUpdate) -> OccasionOut:
        if key != data.entry.id:
            raise ValueError("Occasion identity cannot change")
        row = await self.repo.by_key(key)
        if row is None:
            raise NotFoundException(
                "Occasion not found",
                "record_not_found",
                "occasion",
                "key",
                key,
            )
        changed = await self.repo.change(
            row.id,
            OccasionChange(
                definition=data.entry.model_dump_json(),
                enabled=data.enabled,
                revision=data.revision + 1,
            ),
            data.revision,
        )
        if not changed:
            raise ValueError("Occasion changed; reload its revision")
        return OccasionOut(
            entry=data.entry, enabled=data.enabled, revision=data.revision + 1
        )

    @transactional
    async def seed(self) -> None:
        rows = await asyncio.to_thread(self.seed_rows)
        await self.repo.seed_many(rows)

    def seed_rows(self) -> list[OccasionModel]:
        return [
            OccasionModel(
                key=e["id"],
                definition=CalendarEntry.model_validate(e).model_dump_json(),
            )
            for e in catalogue()[0]
        ]
