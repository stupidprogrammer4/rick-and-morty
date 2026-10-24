import base64
import time

from papilio.infra.redis.client import RedisClient, resolve

from src.config.settings import PortalAppSettings


class ChartImageCache:
    """Disposable images; durable gallery snapshots remain in MySQL."""

    store = """
    redis.call('SET', KEYS[1], ARGV[1], 'EX', 43200)
    redis.call('ZADD', KEYS[2], ARGV[2], KEYS[1])
    while redis.call('ZCARD', KEYS[2]) > 64 do
        local oldest = redis.call('ZPOPMIN', KEYS[2], 1)
        redis.call('DEL', oldest[1])
    end
    redis.call('EXPIRE', KEYS[2], 43200)
    return 1
    """

    def __init__(self, redis: RedisClient, settings: PortalAppSettings):
        self.redis = redis
        self.prefix = f"{settings.tasks.queue_name}:charts:png:v1:"

    async def get(self, key: str) -> bytes | None:
        raw = await resolve(self.redis.client.get(self.prefix + key))
        return (
            base64.b64decode(raw, validate=True) if raw is not None else None
        )

    async def put(self, key: str, image: bytes) -> None:
        if (
            not image.startswith(b"\x89PNG\r\n\x1a\n")
            or len(image) > 256 * 1024
        ):
            raise ValueError("Invalid rendered chart image")
        await resolve(
            self.redis.client.eval(
                self.store,
                2,
                self.prefix + key,
                self.prefix + "index",
                base64.b64encode(image).decode("ascii"),
                time.time(),
            )
        )
