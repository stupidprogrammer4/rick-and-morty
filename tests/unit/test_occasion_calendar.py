from datetime import date, time

import pytest
from pydantic import ValidationError

from portal_contracts.occasions import (
    CustomOccasion,
    OccasionCalendarName,
    OccasionComment,
    OccasionDraft,
    OccasionPolicy,
)
from src.modules.content.occasions.app.calendar import (
    OccasionCalendar,
    catalogue,
    event_id,
)


def calendar(policy: OccasionPolicy | None = None) -> OccasionCalendar:
    # Date-engine coverage explicitly exercises the complete catalogue.
    return OccasionCalendar(
        policy or OccasionPolicy(selection="all"), "Asia/Tehran"
    )


def titles(day) -> set[str]:
    return {event.title for event in day.events}


def test_new_year_has_all_persian_and_lunar_events():
    day = calendar().day(date(2026, 3, 21))
    assert day.persian == (1405, 1, 1)
    assert day.lunar == (1447, 10, 1)
    assert len(day.events) == 6
    assert any("نوروز" in title for title in titles(day))
    assert any("فطر" in title for title in titles(day))
    assert day.warnings == []


def test_october_fifth_includes_every_selected_category_and_movable_days():
    day = calendar().day(date(2026, 10, 5))
    assert day.persian == (1405, 7, 13)
    assert day.lunar == (1448, 4, 23)
    assert len(day.events) == 6
    assert day.events[0].title == "روز مبارزه با تن‌فروشی"
    assert day.events[0].status == "unofficial"
    assert {
        "روز جهانی معلم",
        "روز جهانی اسکان",
        "روز جهانی معماری",
        "روز نیروی انتظامی",
    } <= titles(day)
    assert len({event.id for event in day.events}) == len(day.events)
    assert all(event.source.startswith("https://") for event in day.events)
    assert day.warnings == []


@pytest.mark.parametrize("year, day", [(2024, 12), (2025, 13)])
def test_programmer_day_counts_leap_day(year, day):
    service = calendar()
    assert any(
        "برنامه" in title for title in titles(service.day(date(year, 9, day)))
    )
    assert not any(
        "برنامه" in title
        for title in titles(service.day(date(year, 9, day - 1)))
    )


@pytest.mark.parametrize(
    "target, lunar, needle",
    [
        (date(2026, 8, 13), (1448, 2, 29), "امام رضا"),
        (date(2026, 5, 17), (1447, 11, 29), "امام محمد تقی"),
    ],
)
def test_lunar_month_end_uses_iranian_month_length(target, lunar, needle):
    service = calendar()
    day = service.day(target)
    assert day.lunar == lunar
    assert any(needle in title for title in titles(day))
    assert not any(
        needle in title
        for title in titles(service.day(target.replace(day=target.day - 1)))
    )


def test_lunar_last_friday_and_last_wednesday_offset():
    service = calendar()
    assert any(
        "قدس" in title for title in titles(service.day(date(2027, 3, 5)))
    )
    day = service.day(date(2027, 3, 16))
    assert any("تکریم همسایگان" in title for title in titles(day))
    assert any("چهارشنبه" in title for title in titles(day))
    assert not any(
        "تکریم همسایگان" in title
        for title in titles(service.day(date(2027, 3, 17)))
    )


def test_single_event_is_not_repeated_annually():
    service = calendar()
    assert any(
        "خورشیدگرفتگی" in title
        for title in titles(service.day(date(2022, 10, 25)))
    )
    assert not any(
        "خورشیدگرفتگی" in title
        for title in titles(service.day(date(2023, 10, 25)))
    )


def test_nth_weekday_and_black_friday_correction():
    service = calendar()
    assert any(
        "فلسفه" in title for title in titles(service.day(date(2026, 11, 19)))
    )
    # November's fourth Thursday is November 28 in 2030.
    assert any(
        "بلک فرایدی" in title
        for title in titles(service.day(date(2030, 11, 29)))
    )
    # 2018 has a fifth Friday (November 30), but Thanksgiving is November 22.
    day = service.day(date(2018, 11, 23))
    assert any("بلک فرایدی" in title for title in titles(day))
    assert not any(
        "بلک فرایدی" in title
        for title in titles(service.day(date(2018, 11, 30)))
    )


def test_offset_can_cross_year_boundary():
    service = calendar()
    rule = {
        "calendar": "Gregorian",
        "rule": "last weekday of month",
        "month": 12,
        "weekday": 5,
        "offset": 4,
        "title": "cross-year",
        "type": "International",
    }
    service._events = [rule]
    assert titles(service.day(date(2027, 1, 4))) == {"cross-year"}
    assert titles(service.day(date(2026, 12, 31))) == set()


def test_custom_recurrence_leap_days_one_off_and_exclusions():
    policy = OccasionPolicy(
        selection="all",
        custom_events=[
            CustomOccasion(
                id="leap", title="Leap", calendar="Gregorian", month=2, day=29
            ),
            CustomOccasion(
                id="year",
                title="Only 2026",
                calendar="Gregorian",
                month=10,
                day=5,
                year=2026,
            ),
            CustomOccasion(id="persian", title="Persian", month=7, day=13),
            CustomOccasion(
                id="hijri", title="Hijri", calendar="Hijri", month=4, day=23
            ),
        ],
    )
    service = calendar(policy)
    assert "Leap" in titles(service.day(date(2024, 2, 29)))
    assert "Leap" not in titles(service.day(date(2025, 3, 1)))
    assert {"Only 2026", "Persian", "Hijri"} <= titles(
        service.day(date(2026, 10, 5))
    )
    assert "Only 2026" not in titles(service.day(date(2027, 10, 5)))
    policy.excluded_ids = ["custom:year"]
    assert "Only 2026" not in titles(service.day(date(2026, 10, 5)))
    built_in = service.day(date(2026, 10, 5)).events[0]
    policy.excluded_ids.append(built_in.id)
    assert built_in.id not in {
        event.id for event in service.day(date(2026, 10, 5)).events
    }


def test_policy_categories_and_stable_ids():
    day = calendar(
        OccasionPolicy(selection="all", types=["International"])
    ).day(date(2026, 10, 5))
    assert len(day.events) == 3
    assert all(event.type == "International" for event in day.events)
    event = catalogue()[0][0]
    assert event_id(event) == event_id(dict(event, holiday=False, metadata={}))
    assert len({event_id(item) for item in catalogue()[0]}) == 689


def test_informal_catalogue_is_broad_and_girlfriend_note_is_explicit():
    service = calendar()
    entries = [
        event for event in catalogue()[0] if event["type"] == "Informal"
    ]
    assert len(entries) >= 40
    assert {event["month"] for event in entries} == set(range(1, 13))
    assert all(
        event["status"] == "unofficial" and event["source"]
        for event in entries
    )
    girlfriend = service.day(date(2026, 8, 1)).events[0]
    assert girlfriend.title == "روز دوست‌دختر و دوستان دختر"
    assert girlfriend.type == "Informal"
    assert girlfriend.status == "unofficial"
    assert girlfriend.note is not None and "دوست زن" in girlfriend.note
    assert any(
        "دوست‌پسر" in title for title in titles(service.day(date(2026, 10, 3)))
    )
    without = calendar(OccasionPolicy(types=["Iran", "International"]))
    assert not any(
        event.type == "Informal"
        for event in without.day(date(2026, 10, 5)).events
    )


def test_unknown_lunar_dates_have_visible_warning_and_no_guess():
    service = calendar()
    day = service.day(date(2027, 10, 5))
    assert day.lunar is None
    assert day.warnings
    assert "روز جهانی معلم" in titles(day)
    assert all(event.calendar != "Hijri" for event in day.events)
    partial = service.day(date(2027, 3, 20))
    assert partial.lunar == (1448, 10, 11)
    assert partial.warnings
    assert service.day(date(2027, 3, 21)).lunar is None


def test_policy_and_draft_validation():
    assert OccasionPolicy().enabled is False
    assert OccasionPolicy().time == time(10)
    assert OccasionPolicy().publish_start == time(15)
    assert OccasionPolicy().publish_end == time(18)
    assert OccasionPolicy().selection == "youth"
    assert OccasionPolicy().max_events == 3
    for cap in (0, 6):
        with pytest.raises(ValidationError):
            OccasionPolicy(max_events=cap)
    with pytest.raises(ValidationError):
        OccasionPolicy(enabled=True)
    invalid_dates: list[tuple[OccasionCalendarName, int, int]] = [
        ("Gregorian", 2, 30),
        ("Persian", 7, 31),
        ("Hijri", 1, 31),
    ]
    for calendar_name, month, day in invalid_dates:
        with pytest.raises(ValidationError):
            CustomOccasion(
                id="bad",
                title="Bad",
                calendar=calendar_name,
                month=month,
                day=day,
            )
    with pytest.raises(ValidationError):
        OccasionPolicy(
            custom_events=[
                CustomOccasion(id="same", title="A", month=1, day=1),
                CustomOccasion(id="same", title="B", month=1, day=1),
            ]
        )
    with pytest.raises(ValidationError):
        OccasionDraft(
            date=date(2026, 10, 5),
            intro="Rick",
            outro="Bye",
            comments=[
                OccasionComment(event_id="same", text="A"),
                OccasionComment(event_id="same", text="B"),
            ],
        )


def test_default_october_fifth_keeps_only_selected_social_campaign():
    day = calendar(OccasionPolicy()).day(date(2026, 10, 5))
    assert [event.title for event in day.events] == ["روز مبارزه با تن‌فروشی"]
    assert day.events[0].status == "unofficial"
    assert day.events[0].source.endswith("/V16n4/IDNP.htm")
    assert not any(
        "معلم" in title or "انتظامی" in title for title in titles(day)
    )


def test_default_keeps_girlfriend_and_science_days():
    service = calendar(OccasionPolicy())
    assert "روز دوست‌دختر و دوستان دختر" in titles(
        service.day(date(2026, 8, 1))
    )
    assert "روز جهانی زن و دختر در علم" in titles(
        service.day(date(2026, 2, 11))
    )
    assert any(
        "برنامه‌نویس" in title
        for title in titles(service.day(date(2026, 9, 13)))
    )
    assert "روز جهانی موسیقی" in titles(service.day(date(2026, 6, 21)))


def test_default_does_not_fill_empty_day_with_government_events():
    target = date(2026, 10, 7)
    assert calendar().day(target).events
    assert calendar(OccasionPolicy()).day(target).events == []


def test_new_titles_and_informal_category_do_not_imply_curator_selection():
    service = calendar(OccasionPolicy())
    service._events = [
        {
            "title": "روز جدید اینترنت، بازی و علم",
            "type": "Informal",
            "calendar": "Gregorian",
            "month": 10,
            "day": 5,
            "rule": "simple",
            "source": "https://example.org/new-campaign",
        }
    ]
    assert service.day(date(2026, 10, 5)).events == []
    service.policy.selection = "all"
    assert len(service.day(date(2026, 10, 5)).events) == 1


def test_default_keeps_single_nowruz_and_yalda_titles():
    service = calendar(OccasionPolicy())
    nowruz = service.day(date(2026, 3, 21))
    assert sum("نوروز" in event.title for event in nowruz.events) == 1
    assert all("فطر" not in event.title for event in nowruz.events)
    yalda = service.day(date(2026, 12, 21))
    assert sum("یلدا" in event.title for event in yalda.events) == 1


def test_youth_cap_is_prioritized_stable_and_respects_exclusions():
    policy = OccasionPolicy(max_events=3)
    service = calendar(policy)
    # Inject a same-day collision using real, explicitly curated catalogue IDs.
    curated = [
        event for event in service._events if event_id(event) in service._youth
    ]
    ranked = sorted(
        curated,
        key=lambda event: (service._youth[event_id(event)], event_id(event)),
    )
    chosen = ranked[:2] + ranked[-3:]
    service._events = list(chosen)
    service._matches = lambda event, target, year: True
    target = date(2026, 10, 5)
    expected = [event_id(event) for event in chosen[:3]]
    assert [event.id for event in service.day(target).events] == expected
    service._events.reverse()
    assert [event.id for event in service.day(target).events] == expected
    policy.excluded_ids = [expected[0]]
    assert [event.id for event in service.day(target).events] == [
        event_id(event) for event in chosen[1:4]
    ]
    policy.max_events = 1
    assert [event.id for event in service.day(target).events] == [expected[1]]


def test_youth_custom_entry_is_explicit_and_has_priority():
    service = calendar(
        OccasionPolicy(
            max_events=1,
            custom_events=[
                CustomOccasion(
                    id="community",
                    title="Community meetup",
                    calendar="Gregorian",
                    month=10,
                    day=5,
                )
            ],
        )
    )
    assert [event.id for event in service.day(date(2026, 10, 5)).events] == [
        "custom:community"
    ]
