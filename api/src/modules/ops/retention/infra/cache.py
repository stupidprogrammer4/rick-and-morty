import json
from datetime import datetime

from papilio.infra.redis.client import RedisClient, resolve

from src.config.settings import PortalAppSettings
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.shared.dates import as_utc, utc_now


class VariableCacheStore:
    _prune_fields = """
local removed = 0
local now = tonumber(ARGV[1])
for offset = 2, #ARGV, 3 do
    local field = ARGV[offset]
    if redis.call('HGET', KEYS[1], field) == ARGV[offset + 1] then
        local deadline = tonumber(ARGV[offset + 2])
        if deadline <= now then
            removed = removed + redis.call('HDEL', KEYS[1], field)
        else
            redis.call('HEXPIREAT', KEYS[1], deadline,
                       'LT', 'FIELDS', 1, field)
        end
    end
end
return removed
"""

    def __init__(self, redis: RedisClient, settings: PortalAppSettings):
        self.redis = redis
        prefix = settings.tasks.queue_name
        suffixes = ["assets:price", "bubble:price", "sources:bubble"]
        for symbol in SymbolCode:
            suffixes.extend(
                (f"sources:price:{symbol}", f"sources:selection:{symbol}")
            )
        self.keys = [f"{prefix}:{suffix}" for suffix in suffixes]

    async def prune(self) -> int:
        removed = 0
        now = int(utc_now().timestamp())
        for key in self.keys:
            fields = await resolve(self.redis.client.hgetall(key))
            arguments: list = [now]
            for field, raw in fields.items():
                try:
                    payload = json.loads(raw)
                    rows = payload if isinstance(payload, list) else [payload]
                    stamps = [
                        int(
                            as_utc(
                                datetime.fromisoformat(row["priced_at"])
                            ).timestamp()
                        )
                        for row in rows
                    ]
                    deadline = min(stamps) + 86400
                except (ValueError, TypeError, KeyError):
                    deadline = now
                arguments.extend((field, raw, min(deadline, now + 86400)))
            if fields:
                removed += await resolve(
                    self.redis.client.eval(
                        self._prune_fields, 1, key, *arguments
                    )
                )
        return removed
