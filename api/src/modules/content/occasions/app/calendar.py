"""Offline, source-backed Iranian and international occasion lookup."""

import calendar
import hashlib
import json
from bisect import bisect_right
from datetime import date, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from typing import Any
from zoneinfo import ZoneInfo

from persiantools.jdatetime import JalaliDate

from portal_contracts.occasions import (
    OccasionDay,
    OccasionEvent,
    OccasionPolicy,
)

EVENTS_SOURCE = (
    "https://github.com/persian-calendar/events/blob/"
    "3bfbcc5b667765691784b55b58d8a385217d96d9/events.json"
)
LUNAR_SOURCE = (
    "https://github.com/roozbehp/qamari/blob/"
    "575d275ef169c0a18012506d473ba1008a1c10d0/consolidated.txt"
)
RULES = {
    "simple",
    "single event",
    "end of month",
    "nth weekday of month",
    "last weekday of month",
    "nth day from",
}


def event_id(event: dict) -> str:
    """Content-based IDs survive source ordering and metadata changes."""
    identity = {
        key: value
        for key, value in event.items()
        if key
        not in {"metadata", "holiday", "source", "status", "note", "region"}
    }
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    return "calendar:" + hashlib.sha256(encoded).hexdigest()[:24]


@lru_cache(maxsize=1)
def catalogue() -> tuple[list[dict], dict, list[tuple[date, int, int]], dict]:
    resource = files("src.modules.content.occasions").joinpath("data")
    document = json.loads(resource.joinpath("events.json").read_text())
    events = document["data"]
    supplement = json.loads(resource.joinpath("supplement.json").read_text())
    events = events + supplement
    for event in events:
        if event["rule"] not in RULES:
            raise ValueError(f"Unknown occasion rule: {event['rule']}")
        if event["calendar"] not in {"Gregorian", "Persian", "Hijri"}:
            raise ValueError(f"Unknown calendar: {event['calendar']}")
    months: dict[tuple[int, int], date] = {}
    for line in (
        resource.joinpath("iran_lunar_months.txt").read_text().splitlines()
    ):
        if not line.strip() or line.startswith("#"):
            continue
        lunar, gregorian, *_ = line.split()
        year, month = map(int, lunar.replace("*", "").split("/"))
        months[year, month] = date.fromisoformat(gregorian.replace("*", ""))
    extension = json.loads(
        resource.joinpath("iran_lunar_1405.json").read_text()
    )
    for year, month, start in extension["months"]:
        months[year, month] = date.fromisoformat(start)
    starts = sorted(
        (start, year, month) for (year, month), start in months.items()
    )
    return events, document["Source"], starts, extension


@lru_cache(maxsize=1)
def youth_selection() -> dict[str, int]:
    """Explicit editorial choices, independent of titles and categories."""
    resource = files("src.modules.content.occasions").joinpath(
        "data", "youth_selection.json"
    )
    entries = json.loads(resource.read_text())["events"]
    priorities = {entry["id"]: entry["priority"] for entry in entries}
    if len(priorities) != len(entries):
        raise ValueError("Duplicate youth occasion selection IDs")
    known = {event_id(event) for event in catalogue()[0]}
    if unknown := priorities.keys() - known:
        raise ValueError(f"Unknown youth occasion selection IDs: {unknown}")
    return priorities


class OccasionCalendar:
    def __init__(self, policy: OccasionPolicy, timezone: str):
        self.policy = policy
        self.timezone = ZoneInfo(timezone)
        self._events, self._sources, self._starts, self._extension = (
            catalogue()
        )
        self._dates = [start for start, _, _ in self._starts]
        self._months = {
            (year, month): start for start, year, month in self._starts
        }
        self._last_known = date.fromisoformat(self._extension["valid_through"])
        self._youth = youth_selection()

    def _lunar(self, target: date) -> tuple[int, int, int] | None:
        index = bisect_right(self._dates, target) - 1
        if index < 0 or target > self._last_known:
            return None
        start, year, month = self._starts[index]
        elapsed = (target - start).days
        if elapsed >= 30:
            return None
        return year, month, elapsed + 1

    def _start(self, system: str, year: int, month: int) -> date | None:
        try:
            if system == "Gregorian":
                return date(year, month, 1)
            if system == "Persian":
                return JalaliDate(year, month, 1).to_gregorian()
            return self._months.get((year, month))
        except (ValueError, OverflowError):
            return None

    def _bounds(
        self, system: str, year: int, month: int
    ) -> tuple[date, date] | None:
        start = self._start(system, year, month)
        following = self._start(system, year + (month == 12), month % 12 + 1)
        if start is None or following is None:
            return None
        if system == "Hijri" and (following - start).days not in {29, 30}:
            return None
        return start, following

    def _matches(self, event: dict, target: date, year: int) -> bool:
        system, month, rule = (
            event["calendar"],
            event["month"],
            event["rule"],
        )
        if rule == "single event" and year != event["year"]:
            return False
        start = self._start(system, year, month)
        if start is None:
            return False
        if rule in {"simple", "single event", "nth day from"}:
            offset = event["day"] - 1
            if rule == "nth day from":
                offset += event["nth"] - 1
            candidate = start + timedelta(days=offset)
            if rule != "nth day from":
                # Reject nonexistent recurring dates such as February 29.
                if system == "Gregorian":
                    if event["day"] > calendar.monthrange(year, month)[1]:
                        return False
                elif system == "Persian":
                    if event["day"] > JalaliDate.days_in_month(month, year):
                        return False
                else:
                    bounds = self._bounds(system, year, month)
                    if bounds and candidate >= bounds[1]:
                        return False
                    if self._lunar(candidate) != (year, month, event["day"]):
                        return False
            return target == candidate
        bounds = self._bounds(system, year, month)
        if bounds is None:
            return False
        start, following = bounds
        if rule == "end of month":
            candidate = following - timedelta(days=1)
        else:
            # Upstream uses Sunday=1, ..., Friday=6, Saturday=7.
            weekday = (event["weekday"] + 5) % 7
            if rule == "last weekday of month":
                last = following - timedelta(days=1)
                candidate = last - timedelta(
                    days=(last.weekday() - weekday) % 7
                )
            else:
                candidate = start + timedelta(
                    days=(weekday - start.weekday()) % 7
                    + 7 * (event["nth"] - 1)
                )
                if candidate >= following:
                    return False
            candidate += timedelta(days=event.get("offset", 0))
        return target == candidate

    def day(self, target: date | None = None) -> OccasionDay:
        target = target or datetime.now(self.timezone).date()
        persian = JalaliDate.to_jalali(target)
        lunar = self._lunar(target)
        years = {
            "Gregorian": target.year,
            "Persian": persian.year,
            "Hijri": lunar[0] if lunar else None,
        }
        events = []
        excluded = set(self.policy.excluded_ids)
        for original in self._events:
            identifier = event_id(original)
            if (
                original["type"] not in self.policy.types
                or identifier in excluded
                or (
                    self.policy.selection == "youth"
                    and identifier not in self._youth
                )
            ):
                continue
            event: dict[str, Any] = original
            if original["title"].startswith("جمعهٔ سیاه"):
                # Thanksgiving's following Friday need not be the last one.
                event = dict(
                    original,
                    rule="nth weekday of month",
                    nth=4,
                    weekday=5,
                    offset=1,
                    title="جمعهٔ سیاه یا بلک فرایدی (پس از شکرگزاری)",
                )
            year = years[event["calendar"]]
            if year is None:
                continue
            # Offsets and nth-day rules may cross month/year boundaries.
            if not any(
                self._matches(event, target, candidate_year)
                for candidate_year in (year - 1, year, year + 1)
            ):
                continue
            source = original.get("source") or EVENTS_SOURCE
            status: Any = original.get("status") or {
                "Iran": "official",
                "AncientIran": "traditional",
                "Informal": "unofficial",
            }.get(original["type"], "recorded")
            events.append(
                OccasionEvent(
                    id=identifier,
                    title=event["title"],
                    type=event["type"],
                    calendar=event["calendar"],
                    holiday=event.get("holiday", False),
                    source=source,
                    status=status,
                    note=original.get("note"),
                    region=original.get("region"),
                )
            )
        for custom in self.policy.custom_events:
            identifier = "custom:" + custom.id
            if identifier in excluded:
                continue
            year = years[custom.calendar]
            if year is None or (
                custom.year is not None and custom.year != year
            ):
                continue
            rule = dict(custom.model_dump(), rule="simple")
            if self._matches(rule, target, year):
                events.append(
                    OccasionEvent(
                        id=identifier,
                        title=custom.title,
                        type="Custom",
                        calendar=custom.calendar,
                        holiday=custom.holiday,
                        source=custom.source,
                        status="custom",
                    )
                )
        warnings = []
        if lunar is None:
            warnings.append(
                "تاریخ قمری ایران برای این روز در دادهٔ معتبر موجود نیست؛ "
                "مناسبت‌های قمری قابل تأیید نیستند."
            )
        elif self._bounds("Hijri", lunar[0], lunar[1]) is None:
            warnings.append(
                "پایان این ماه قمری هنوز در دادهٔ معتبر موجود نیست؛ "
                "مناسبت‌های وابسته به پایان ماه قابل تأیید نیستند."
            )
        if self.policy.selection == "youth":
            # Explicit custom entries have priority over catalogue choices.
            events = sorted(
                events,
                key=lambda event: (
                    0 if event.type == "Custom" else self._youth[event.id],
                    event.id,
                ),
            )[: self.policy.max_events]
        else:
            events = sorted(events, key=lambda event: event.type != "Informal")
        sources = sorted({event.source for event in events})
        if lunar is not None:
            sources.append(
                self._extension["source"]
                if target >= date(2026, 3, 21)
                else LUNAR_SOURCE
            )
        return OccasionDay(
            date=target,
            persian=(persian.year, persian.month, persian.day),
            lunar=lunar,
            events=events,
            warnings=warnings,
            sources=sorted(set(sources)),
        )
