from papilio.types.enums import FaStrEnum


class TimeFrame(FaStrEnum):
    FIVE_MINUTE = ("5m", "۵ دقیقه")
    HOURLY = ("1h", "یک ساعت")
    FIVE_HOURLY = ("5h", "۵ ساعت")
    DAILY = ("1d", "روزانه")

    @property
    def seconds(self) -> int:
        return {
            TimeFrame.FIVE_MINUTE: 5 * 60,
            TimeFrame.HOURLY: 60 * 60,
            TimeFrame.FIVE_HOURLY: 5 * 60 * 60,
            TimeFrame.DAILY: 24 * 60 * 60,
        }[self]

    @property
    def rolled_from(self) -> "TimeFrame | None":
        return {
            TimeFrame.FIVE_MINUTE: None,
            TimeFrame.HOURLY: TimeFrame.FIVE_MINUTE,
            TimeFrame.FIVE_HOURLY: TimeFrame.HOURLY,
            TimeFrame.DAILY: TimeFrame.HOURLY,
        }[self]

    def opened_at(self, timestamp: int) -> int:
        offset = 3 * 60 * 60 + 30 * 60
        opened = (timestamp + offset) // self.seconds
        return opened * self.seconds - offset
