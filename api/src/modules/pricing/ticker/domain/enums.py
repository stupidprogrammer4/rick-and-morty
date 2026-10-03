from papilio.types.enums import FaStrEnum


class ChartType(FaStrEnum):
    DAILY = ("daily", "روزانه")
    WEEKLY = ("weekly", "هفتگی")
    MONTHLY = ("monthly", "ماهانه")
    SIX_MONTHLY = ("six_monthly", "شش‌ماهه")
    YEARLY = ("yearly", "سالانه")

    @property
    def step(self) -> int:
        return {
            ChartType.DAILY: 5 * 60,
            ChartType.WEEKLY: 30 * 60,
            ChartType.MONTHLY: 2 * 60 * 60,
            ChartType.SIX_MONTHLY: 12 * 60 * 60,
            ChartType.YEARLY: 24 * 60 * 60,
        }[self]

    @property
    def span(self) -> int:
        day = 24 * 60 * 60
        return {
            ChartType.DAILY: day,
            ChartType.WEEKLY: 7 * day,
            ChartType.MONTHLY: 30 * day,
            ChartType.SIX_MONTHLY: 180 * day,
            ChartType.YEARLY: 365 * day,
        }[self]
