from typing import Mapping, Sequence

from papilio.infra.redis.client import RedisClient, resolve
from pydantic import TypeAdapter
from redis.typing import FieldT

from src.config.settings import PortalAppSettings
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.candle.domain.windows import (
    AssetPriceWindow,
    SourcePriceWindow,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode


class AssetWindowCache:
    namespace = "assets:window"
    ttl = 60 * 60

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    def _key(self, st_ts: int) -> str:
        return f"{self.namespace}:{st_ts}"

    async def set(
        self,
        st_ts: int,
        code: AssetCode,
        window: AssetPriceWindow,
    ) -> None:
        key = self._key(st_ts)
        await resolve(
            self.redis.client.hset(key, code, window.model_dump_json())
        )
        await resolve(self.redis.client.expire(key, self.ttl))

    async def set_many(
        self,
        st_ts: int,
        items: Mapping[AssetCode, AssetPriceWindow],
    ) -> None:
        key = self._key(st_ts)
        mapping: dict[FieldT, str] = {
            code: window.model_dump_json() for code, window in items.items()
        }
        await resolve(self.redis.client.hset(key, mapping=mapping))
        await resolve(self.redis.client.expire(key, self.ttl))

    async def get(
        self,
        st_ts: int,
        code: AssetCode,
    ) -> AssetPriceWindow | None:
        raw = await resolve(self.redis.client.hget(self._key(st_ts), code))
        window = None
        if raw is not None:
            window = AssetPriceWindow.model_validate_json(raw)
        return window

    async def get_many(
        self,
        st_ts: int,
        codes: Sequence[AssetCode],
    ) -> dict[AssetCode, AssetPriceWindow]:
        fields = [code for code in codes]
        raws = await resolve(self.redis.client.hmget(self._key(st_ts), fields))
        return {
            code: AssetPriceWindow.model_validate_json(raw)
            for code, raw in zip(codes, raws)
            if raw is not None
        }

    async def get_all(
        self,
        st_ts: int,
    ) -> dict[AssetCode, AssetPriceWindow]:
        stored = await resolve(self.redis.client.hgetall(self._key(st_ts)))
        return {
            AssetCode(field): AssetPriceWindow.model_validate_json(raw)
            for field, raw in stored.items()
            if field in AssetCode.__members__.values()
        }

    async def remove(self, st_ts: int) -> None:
        await resolve(self.redis.client.delete(self._key(st_ts)))


class SourceWindowCache:
    namespace = "sources:window"
    ttl = 60 * 60
    adapter = TypeAdapter(list[SourcePriceWindow])

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    def _key(self, st_ts: int) -> str:
        return f"{self.namespace}:{st_ts}"

    async def set(
        self,
        st_ts: int,
        code: SymbolCode,
        windows: Sequence[SourcePriceWindow],
    ) -> None:
        key = self._key(st_ts)
        payload = self.adapter.dump_json(list(windows)).decode()
        await resolve(self.redis.client.hset(key, code, payload))
        await resolve(self.redis.client.expire(key, self.ttl))

    async def set_many(
        self,
        st_ts: int,
        items: Mapping[SymbolCode, Sequence[SourcePriceWindow]],
    ) -> None:
        key = self._key(st_ts)
        mapping: dict[FieldT, str] = {
            code: self.adapter.dump_json(list(windows)).decode()
            for code, windows in items.items()
        }
        await resolve(self.redis.client.hset(key, mapping=mapping))
        await resolve(self.redis.client.expire(key, self.ttl))

    async def get(
        self,
        st_ts: int,
        code: SymbolCode,
    ) -> list[SourcePriceWindow]:
        raw = await resolve(self.redis.client.hget(self._key(st_ts), code))
        windows = []
        if raw is not None:
            windows = self.adapter.validate_json(raw)
        return windows

    async def get_many(
        self,
        st_ts: int,
        codes: Sequence[SymbolCode],
    ) -> dict[SymbolCode, list[SourcePriceWindow]]:
        fields = [code for code in codes]
        raws = await resolve(self.redis.client.hmget(self._key(st_ts), fields))
        return {
            code: self.adapter.validate_json(raw)
            for code, raw in zip(codes, raws)
            if raw is not None
        }

    async def get_all(
        self,
        st_ts: int,
    ) -> dict[SymbolCode, list[SourcePriceWindow]]:
        stored = await resolve(self.redis.client.hgetall(self._key(st_ts)))
        return {
            SymbolCode(field): self.adapter.validate_json(raw)
            for field, raw in stored.items()
            if field in SymbolCode.__members__.values()
        }

    async def remove(self, st_ts: int) -> None:
        await resolve(self.redis.client.delete(self._key(st_ts)))
