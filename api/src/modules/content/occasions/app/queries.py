import asyncio
from datetime import date

from amupouya_calendar.engine import OccasionCalendar
from amupouya_calendar.models import CalendarEntry, CalendarPolicy, OccasionDay

from src.modules.content.occasions.infra.mysql import OccasionRepository


class OccasionQueries:
    def __init__(self, repo: OccasionRepository):
        self.repo = repo

    async def day(
        self, target: date, policy: CalendarPolicy, timezone: str
    ) -> OccasionDay:
        rows = await self.repo.active()
        if not rows and not await self.repo.count(""):
            raise ValueError("Occasion catalogue is empty; run bootstrap")
        definitions = [row.definition for row in rows]
        result = await asyncio.to_thread(
            self.calculate, target, policy, timezone, definitions
        )
        return result

    def calculate(
        self,
        target: date,
        policy: CalendarPolicy,
        timezone: str,
        definitions: list[str],
    ) -> OccasionDay:
        entries = [
            CalendarEntry.model_validate_json(value) for value in definitions
        ]
        return OccasionCalendar(policy, timezone, entries).day(target)
