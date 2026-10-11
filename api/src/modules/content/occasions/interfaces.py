from collections.abc import Awaitable
from datetime import date
from typing import Protocol

from amupouya_calendar.models import CalendarPolicy, OccasionDay

from src.modules.content.occasions.domain.dtos import (
    OccasionOut,
    OccasionPage,
    OccasionUpdate,
    OccasionWrite,
)


class IOccasionService(Protocol):
    def get(self, key: str) -> Awaitable[OccasionOut]: ...
    def search(
        self, query: str, page: int, per_page: int
    ) -> Awaitable[OccasionPage]: ...
    def create(self, data: OccasionWrite) -> Awaitable[OccasionOut]: ...
    def update(
        self, key: str, data: OccasionUpdate
    ) -> Awaitable[OccasionOut]: ...
    def seed(self) -> Awaitable[None]: ...


class IOccasionQueries(Protocol):
    def day(
        self, target: date, policy: CalendarPolicy, timezone: str
    ) -> Awaitable[OccasionDay]: ...
