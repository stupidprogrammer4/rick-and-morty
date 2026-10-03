from papilio.core.logger import logger
from papilio_tasks.apps.schedulers.backends.redis import (
    RedisScheduler,
)

from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.candle.interfaces import (
    ICandleService,
    ISourceCandleService,
)


class BuildFromCacheTask(RedisScheduler):
    schedule = [{"cron": "*/5 * * * *"}]

    def __init__(
        self, candles: ICandleService, sources: ISourceCandleService
    ) -> None:
        self.candles = candles
        self.sources = sources

    async def run(self) -> int:
        priced = await self.candles.build_from_cache()
        quoted = await self.sources.build_from_cache()
        logger.info("closed window written down: %s + %s", priced, quoted)
        return priced + quoted


class RollTimeframeTask(RedisScheduler):
    schedule = [
        {
            "cron": "1 * * * *",
            "cron_offset": "Asia/Tehran",
            "kwargs": {"tf": TimeFrame.HOURLY.value},
        },
        {
            "cron": "2 */5 * * *",
            "cron_offset": "Asia/Tehran",
            "kwargs": {"tf": TimeFrame.FIVE_HOURLY.value},
        },
        {
            "cron": "3 0 * * *",
            "cron_offset": "Asia/Tehran",
            "kwargs": {"tf": TimeFrame.DAILY.value},
        },
    ]

    def __init__(
        self, candles: ICandleService, sources: ISourceCandleService
    ) -> None:
        self.candles = candles
        self.sources = sources

    async def run(self, tf: TimeFrame) -> int:
        frame = TimeFrame(tf)
        priced = await self.candles.build_timeframe_from_rolled(frame)
        quoted = await self.sources.build_timeframe_from_rolled(frame)
        logger.info("%s rolled up: %s + %s", frame.value, priced, quoted)
        return priced + quoted
