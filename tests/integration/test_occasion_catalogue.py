from datetime import date

import pytest
from amupouya_calendar.models import CalendarPolicy

from src.modules.content.occasions.domain.dtos import OccasionUpdate
from src.modules.content.occasions.interfaces import (
    IOccasionQueries,
    IOccasionService,
)

pytestmark = pytest.mark.integration


def test_database_controls_calendar_and_seed_preserves_edits(portal):
    async def run():
        async with portal.request() as scope:
            queries = await scope.get(IOccasionQueries)
            day = await queries.day(
                date(2026, 10, 11),
                CalendarPolicy(tags=["girls"]),
                "Asia/Tehran",
            )
            girl = next(e for e in day.events if e.title == "روز جهانی دختران")
            service = await scope.get(IOccasionService)
            row = await service.get(girl.id)
            await service.update(
                girl.id,
                OccasionUpdate(
                    entry=row.entry, enabled=False, revision=row.revision
                ),
            )
            await service.seed()
        async with portal.request() as scope:
            queries = await scope.get(IOccasionQueries)
            after = await queries.day(
                date(2026, 10, 11),
                CalendarPolicy(tags=["girls"]),
                "Asia/Tehran",
            )
            assert girl.id not in {e.id for e in after.events}
            service = await scope.get(IOccasionService)
            preserved = await service.get(girl.id)
            assert preserved.revision == 2 and not preserved.enabled
            maritime = await queries.day(
                date(2026, 9, 24), CalendarPolicy(), "Asia/Tehran"
            )
            assert any("دریانوردی" in e.title for e in maritime.events)

    portal.run(run())
