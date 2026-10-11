from amupouya_calendar.models import CalendarEntry
from pydantic import BaseModel, Field


class OccasionWrite(BaseModel):
    entry: CalendarEntry
    enabled: bool = True


class OccasionUpdate(OccasionWrite):
    revision: int = Field(ge=1)


class OccasionOut(OccasionUpdate):
    pass


class OccasionPage(BaseModel):
    items: list[OccasionOut]
    page: int
    per_page: int
    total: int


class OccasionChange(BaseModel):
    definition: str
    enabled: bool
    revision: int
