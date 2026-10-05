from datetime import UTC, datetime, timedelta
from math import ceil, floor
from secrets import randbelow
from zoneinfo import ZoneInfo

from portal_contracts.occasions import OccasionPolicy


def occasion_publish_at(
    policy: OccasionPolicy, timezone: str, slot: datetime, now: datetime
) -> datetime | None:
    """Choose a remaining second in this slot's afternoon window.

    The publication workflow stores the chosen instant with its unique draft
    revision key, so restarts and repeated scheduling retain that choice.
    """
    zone = ZoneInfo(timezone)
    day = slot.astimezone(zone).date()
    start = datetime.combine(day, policy.publish_start, zone)
    end = datetime.combine(day, policy.publish_end, zone)
    first = max(0, ceil((now.astimezone(zone) - start).total_seconds()))
    last = floor((end - start).total_seconds())
    if first > last:
        return None
    chosen = start + timedelta(seconds=first + randbelow(last - first + 1))
    return chosen.astimezone(UTC)
