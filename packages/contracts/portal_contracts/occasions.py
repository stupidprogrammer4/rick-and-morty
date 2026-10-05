from datetime import date
from datetime import time as ClockTime
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

RICK_OCCASION_PROMPT = (
    "تو ریک سانچز هستی. مناسبت‌های امروز را به فارسی محاوره‌ای، با اعتماد "
    "به نفس افراطی، بدبینی علمی، طعنه‌های تند و شوخی‌های پوچ چندجهانی "
    "اعلام کن. گاهی مورتی را مخاطب قرار بده؛ دیالوگ زنده و ریتم بریده "
    "و خودمانی داشته باش، نه لحن مجری، تقویم اداری یا دستیار مؤدب. "
    "عنوان و واقعیت هر مناسبت را عوض نکن و هیچ مناسبت داده‌شده‌ای را "
    "حذف نکن. شوخی را از توضیح واقعی جدا کن. مناسبت‌های سوگ را با "
    "طعنه به مناسک و بوروکراسی توضیح بده، نه تمسخر قربانیان. "
    "فقط بر پایه ابزار تقویم بنویس و برای هر شناسه دقیقاً یک نظر کوتاه بده."
)


class CustomOccasion(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=250)
    calendar: OccasionCalendarName = "Persian"
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    year: int | None = Field(default=None, ge=1, le=9999)
    holiday: bool = False
    source: str = Field(default="custom", min_length=1, max_length=1000)

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


class OccasionPolicy(BaseModel):
    enabled: bool = False
    owner_id: int | None = Field(default=None, gt=0)
    time: ClockTime = ClockTime(10)
    publish_start: ClockTime = ClockTime(15)
    publish_end: ClockTime = ClockTime(18)
    types: list[OccasionType] = Field(
        default_factory=lambda: [
            "Informal",
            "Iran",
            "AncientIran",
            "International",
        ],
        min_length=1,
    )
    custom_events: list[CustomOccasion] = Field(
        default_factory=list, max_length=500
    )
    excluded_ids: list[str] = Field(default_factory=list, max_length=1000)
    prompt: str = Field(
        default=RICK_OCCASION_PROMPT, min_length=1, max_length=4000
    )

    @model_validator(mode="after")
    def valid_policy(self) -> Self:
        if self.enabled and self.owner_id is None:
            raise ValueError("Enabled occasions require an owner")
        if any(
            clock.tzinfo is not None
            for clock in (self.time, self.publish_start, self.publish_end)
        ):
            raise ValueError("Occasion time uses the portal timezone")
        if not self.time <= self.publish_start < self.publish_end:
            raise ValueError(
                "Prepare occasions before the ordered publication window"
            )
        if len(self.types) != len(set(self.types)):
            raise ValueError("Occasion types must be unique")
        identifiers = [event.id for event in self.custom_events]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Custom occasion IDs must be unique")
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


class OccasionDay(BaseModel):
    date: date
    persian: tuple[int, int, int]
    lunar: tuple[int, int, int] | None
    events: list[OccasionEvent]
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class OccasionComment(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=160)


class OccasionDraft(BaseModel):
    date: date
    intro: str = Field(min_length=1, max_length=400)
    comments: list[OccasionComment] = Field(max_length=100)
    outro: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def comments_are_unique(self) -> Self:
        identifiers = [comment.event_id for comment in self.comments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Occasion comments must have unique event IDs")
        if any(not comment.text.strip() for comment in self.comments):
            raise ValueError("Occasion comments cannot be blank")
        return self
