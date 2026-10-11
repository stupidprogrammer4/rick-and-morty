from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

OccasionType = Literal[
    "Informal",
    "Iran",
    "AncientIran",
    "International",
    "Afghanistan",
    "IranFormer",
]
OccasionCalendarName = Literal["Persian", "Gregorian", "Hijri"]


class CustomOccasion(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=250)
    calendar: OccasionCalendarName = "Persian"
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    year: int | None = Field(default=None, ge=1, le=9999)
    holiday: bool = False
    source: str = Field(default="custom", min_length=1, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid_calendar_date(self) -> Self:
        if self.calendar == "Gregorian":
            date(self.year or 2000, self.month, self.day)
        elif self.calendar == "Persian":
            maximum = 31 if self.month <= 6 else 30
            if self.day > maximum:
                raise ValueError("Invalid Persian day")
        elif self.day > 30:
            raise ValueError("Lunar months have at most 30 days")
        if not self.title.strip():
            raise ValueError("Occasion title cannot be blank")
        return self


class CalendarPolicy(BaseModel):
    selection: Literal["youth", "all"] = "all"
    max_events: int = Field(default=3, ge=1, le=5)
    types: list[OccasionType] = Field(
        min_length=1,
        default_factory=lambda: [
            "Informal",
            "Iran",
            "AncientIran",
            "International",
            "Afghanistan",
            "IranFormer",
        ],
    )
    custom_events: list[CustomOccasion] = Field(
        default_factory=list, max_length=500
    )
    excluded_ids: list[str] = Field(default_factory=list, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_selection(self) -> Self:
        ids = [event.id for event in self.custom_events]
        if len(ids) != len(set(ids)) or len(self.types) != len(
            set(self.types)
        ):
            raise ValueError("Selection types and custom IDs must be unique")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("Selection tags must be unique")
        return self


class OccasionEvent(BaseModel):
    id: str
    title: str
    type: OccasionType | Literal["Custom"]
    calendar: OccasionCalendarName
    holiday: bool = False
    source: str
    status: Literal[
        "official", "unofficial", "traditional", "custom", "recorded"
    ] = "recorded"
    note: str | None = None
    region: str | None = None
    tags: list[str] = Field(default_factory=list)


class OccasionDay(BaseModel):
    date: date
    persian: tuple[int, int, int]
    lunar: tuple[int, int, int] | None
    events: list[OccasionEvent]
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class CalendarEntry(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    calendar: OccasionCalendarName
    type: OccasionType
    rule: Literal[
        "simple",
        "single event",
        "end of month",
        "nth weekday of month",
        "last weekday of month",
        "nth day from",
    ]
    month: int = Field(ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=366)
    year: int | None = Field(default=None, ge=1, le=9999)
    nth: int | None = Field(default=None, ge=1, le=366)
    weekday: int | None = Field(default=None, ge=1, le=7)
    offset: int = Field(default=0, ge=-31, le=31)
    holiday: bool = False
    source: str = Field(min_length=1, max_length=1000)
    status: Literal[
        "official", "unofficial", "traditional", "custom", "recorded"
    ] = "recorded"
    note: str | None = Field(default=None, max_length=1500)
    region: str | None = Field(default=None, max_length=150)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid_rule(self) -> Self:
        if (
            self.rule in {"simple", "single event", "nth day from"}
            and self.day is None
        ):
            raise ValueError("This rule requires a day")
        if self.rule == "single event" and self.year is None:
            raise ValueError("Single events require a year")
        if (
            self.rule in {"nth weekday of month", "last weekday of month"}
            and self.weekday is None
        ):
            raise ValueError("Weekday rules require a weekday")
        if (
            self.rule in {"nth weekday of month", "nth day from"}
            and self.nth is None
        ):
            raise ValueError("This rule requires an ordinal")
        if (
            self.rule == "nth weekday of month"
            and self.nth is not None
            and self.nth > 5
        ):
            raise ValueError(
                "A month has at most five occurrences of a weekday"
            )
        if self.rule in {"simple", "single event"} and self.day is not None:
            CustomOccasion(
                id="validation",
                title=self.title,
                calendar=self.calendar,
                month=self.month,
                day=self.day,
                year=self.year,
            )
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("Tags must be unique")
        return self
