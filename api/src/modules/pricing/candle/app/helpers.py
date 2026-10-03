from papilio.utils import dates as date_utils

from src.modules.pricing.candle.domain.dtos import ParamDTO
from src.modules.pricing.candle.domain.enums import TimeFrame


class WindowClock:
    timeframe = TimeFrame.FIVE_MINUTE

    def opened_now(self) -> int:
        """
        Desc: Get the epoch second the current window opened at.
        Returns:
            return (int): Opening second of the window now running.
        """
        stamp = int(date_utils.utc_now().timestamp())
        opened = self.timeframe.opened_at(stamp)
        return opened

    def last_closed(self) -> int:
        """
        Desc: Get the epoch second the last closed window opened at.
        Returns:
            return (int): Opening second of the window just closed.
        """
        closed = self.opened_now() - self.timeframe.seconds
        return closed


class ChartWindow:
    max_days = 370

    def days(self, param: ParamDTO) -> float:
        """
        Desc: Measure the asked span in days.
        Args:
            param (ParamDTO): The window the caller asked for.
        Returns:
            return (float): How many days the window covers.
        """
        span = param.to_datetime - param.from_datetime
        return span.total_seconds() / TimeFrame.DAILY.seconds

    def timeframe(self, days: float) -> TimeFrame:
        """
        Desc: Pick the candle width a window of this length is drawn at.
        Args:
            days (float): How many days the window covers.
        Returns:
            return (TimeFrame): Candle width to read the window at.
        """
        picked = TimeFrame.DAILY
        if days <= 1:
            picked = TimeFrame.FIVE_MINUTE
        elif days <= 7:
            picked = TimeFrame.HOURLY
        elif days <= 60:
            picked = TimeFrame.FIVE_HOURLY
        return picked
