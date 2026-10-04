import asyncio
from datetime import datetime

from papilio.infra.redis.client import RedisClient, resolve

from src.modules.ops.queues.domain.dtos import TaskStreams


class TaskHistoryStore:
    def __init__(self, redis: RedisClient, streams: TaskStreams):
        self.redis = redis
        self.streams = streams

    async def prune(self, before: datetime) -> int:
        threshold = f"{int(before.timestamp() * 1000)}-0"
        main, media = await asyncio.gather(
            resolve(
                self.redis.client.execute_command(
                    "XTRIM",
                    self.streams.main,
                    "MINID",
                    "=",
                    threshold,
                    "ACKED",
                )
            ),
            resolve(
                self.redis.client.execute_command(
                    "XTRIM",
                    self.streams.media,
                    "MINID",
                    "=",
                    threshold,
                    "ACKED",
                )
            ),
        )
        if not isinstance(main, int) or not isinstance(media, int):
            raise RuntimeError("Redis did not return a stream trim count")
        return main + media
