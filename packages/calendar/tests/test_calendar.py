import json
from datetime import date
from importlib.resources import files

import pytest
from amupouya_calendar.engine import OccasionCalendar, catalogue, event_id
from amupouya_calendar.models import CalendarEntry, CalendarPolicy
from pydantic import ValidationError


def test_all_source_days_are_represented_and_legacy_ids_survive():
    resource = files("amupouya_calendar").joinpath("data")
    original = json.loads(resource.joinpath("events.json").read_text())["data"]
    original += json.loads(resource.joinpath("supplement.json").read_text())
    current = {event_id(e) for e in catalogue()[0]}
    assert len(current) == 894
    assert {event_id(e) for e in original} <= current
    coverage = json.loads(
        resource.joinpath("coverage_20261011.json").read_text()
    )
    assert len(coverage["items"]) == 353
    for item in coverage["items"]:
        if item["scope"] == "day":
            assert item["entry_ids"]
            assert set(item["entry_ids"]) <= current
    assert (
        len([CalendarEntry.model_validate(e) for e in catalogue()[0]]) == 894
    )


@pytest.mark.parametrize(
    "day,term",
    [
        (date(2026, 4, 23), "فناوری اطلاعات"),
        (date(2026, 5, 9), "پرندگان مهاجر"),
        (date(2026, 10, 10), "پرندگان مهاجر"),
        (date(2026, 7, 4), "تعاونی"),
        (date(2026, 9, 24), "دریانوردی"),
        (date(2026, 11, 5), "قلدری"),
        (date(2026, 11, 15), "تصادفات"),
        (date(2026, 11, 19), "فلسفه"),
    ],
)
def test_moving_dates(day, term):
    calendar = OccasionCalendar(CalendarPolicy(), "Asia/Tehran")
    assert any(term in e.title for e in calendar.day(day).events)


def test_explicit_tags_do_not_match_unrelated_words():
    calendar = OccasionCalendar(
        CalendarPolicy(tags=["girls", "women"]), "Asia/Tehran"
    )
    assert any(
        "دختر" in e.title for e in calendar.day(date(2026, 10, 11)).events
    )
    assert not calendar.day(
        date(2026, 2, 21)
    ).events  # Mother language is not motherhood.
    assert any(
        "دوست‌دختر" in e.title and e.status == "unofficial"
        for e in calendar.day(date(2026, 8, 1)).events
    )


def test_single_year_observance_is_not_fabricated_next_year():
    calendar = OccasionCalendar(CalendarPolicy(), "Asia/Tehran")
    assert any(
        "وساک" in e.title for e in calendar.day(date(2026, 5, 1)).events
    )
    assert not any(
        "وساک" in e.title for e in calendar.day(date(2027, 5, 1)).events
    )


def test_invalid_date_or_rule_is_rejected():
    entry = CalendarEntry.model_validate(catalogue()[0][0])
    with pytest.raises(ValidationError):
        CalendarEntry.model_validate(
            dict(
                entry.model_dump(),
                calendar="Gregorian",
                month=2,
                day=30,
                rule="simple",
            )
        )
