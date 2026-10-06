from datetime import datetime
from typing import Mapping

from papilio.infra.redis.client import RedisClient, resolve
from redis.typing import FieldT

from src.shared.dates import as_utc, utc_now


async def set_price_fields(
    redis: RedisClient,
    key: str,
    mapping: Mapping[FieldT, str],
    clocks: Mapping[FieldT, datetime],
) -> None:
    if not mapping:
        return
    pipe = redis.client.pipeline()
    pipe.hset(key, mapping=dict(mapping))
    now = int(utc_now().timestamp())
    for field, clock in clocks.items():
        deadline = min(int(as_utc(clock).timestamp()), now) + 86400
        pipe.hexpireat(key, deadline, field)
    await resolve(pipe.execute())
