import json
from typing import Mapping, Sequence

from papilio.infra.redis.client import RedisClient, resolve
from pydantic import TypeAdapter
from redis.typing import FieldT

from src.config.settings import PortalAppSettings
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.engine.domain.models import (
    PricedSourceModel,
    SourceKeyedModel,
    SourceSelectionModel,
)
from src.modules.pricing.sources.domain.models import (
    SourceBubbleModel,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.shared.cache_retention import set_price_fields
from src.shared.dates import as_utc, utc_now


class SourceKeyedCache[T: SourceKeyedModel]:
    namespace: str
    model: type[T]
    field_ttl = 300

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    def _fields(self, rows: Sequence[T]) -> dict[FieldT, str]:
        return {str(row.source_id): row.model_dump_json() for row in rows}

    async def set(self, code: SymbolCode, rows: Sequence[T]) -> None:
        if not rows:
            return
        key = self.namespace.format(symbol=code)
        fields = self._fields(rows)
        pipe = self.redis.client.pipeline()
        pipe.hset(key, mapping=fields)
        pipe.hexpire(key, self.field_ttl, *fields)
        await resolve(pipe.execute())

    async def set_many(
        self,
        results: Mapping[SymbolCode, Sequence[T]],
    ) -> None:
        pipe = self.redis.client.pipeline()
        for code, rows in results.items():
            if not rows:
                continue
            key = self.namespace.format(symbol=code)
            fields = self._fields(rows)
            pipe.hset(key, mapping=fields)
            pipe.hexpire(key, self.field_ttl, *fields)
        await resolve(pipe.execute())

    def _rows(self, stored: Mapping[bytes | str, bytes | str]) -> list[T]:
        rows = [self.model.model_validate_json(raw) for raw in stored.values()]
        rows.sort(key=lambda row: row.source_id)
        return rows

    async def get(self, code: SymbolCode) -> list[T]:
        key = self.namespace.format(symbol=code)
        stored = await resolve(self.redis.client.hgetall(key))
        return self._rows(stored)

    async def get_many(
        self,
        codes: Sequence[SymbolCode],
    ) -> dict[SymbolCode, list[T]]:
        pipe = self.redis.client.pipeline()
        for code in codes:
            pipe.hgetall(self.namespace.format(symbol=code))
        stored = await resolve(pipe.execute())
        return {
            code: self._rows(rows) for code, rows in zip(codes, stored) if rows
        }

    async def get_all(self) -> dict[SymbolCode, list[T]]:
        codes = list(SymbolCode)
        pipe = self.redis.client.pipeline()
        for code in codes:
            pipe.hgetall(self.namespace.format(symbol=code))
        stored = await resolve(pipe.execute())
        return {
            code: self._rows(rows) for code, rows in zip(codes, stored) if rows
        }

    async def remove(self, code: SymbolCode) -> None:
        await resolve(
            self.redis.client.delete(self.namespace.format(symbol=code))
        )

    async def clear(self) -> None:
        pipe = self.redis.client.pipeline()
        for code in SymbolCode:
            pipe.delete(self.namespace.format(symbol=code))
        await resolve(pipe.execute())

    async def get_by_id(self, source_id: int) -> list[T]:
        field = str(source_id)
        pipe = self.redis.client.pipeline()
        for code in SymbolCode:
            pipe.hget(self.namespace.format(symbol=code), field)
        stored = await resolve(pipe.execute())
        return [
            self.model.model_validate_json(raw)
            for raw in stored
            if raw is not None
        ]

    async def get_by_ids(self, source_ids: Sequence[int]) -> list[T]:
        if not source_ids:
            return []
        fields = [str(id) for id in source_ids]
        pipe = self.redis.client.pipeline()
        for code in SymbolCode:
            pipe.hmget(self.namespace.format(symbol=code), fields)
        stored = await resolve(pipe.execute())
        return [
            self.model.model_validate_json(raw)
            for raws in stored
            for raw in raws
            if raw is not None
        ]


class SourcePriceCache(SourceKeyedCache[PricedSourceModel]):
    namespace = "sources:price:{symbol}"
    model = PricedSourceModel
    _upsert_by_version = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local matched = {}
for offset = 1, #ARGV, 4 do
    local field = ARGV[offset]
    local version = tonumber(ARGV[offset + 1])
    local deadline = tonumber(ARGV[offset + 2])
    local payload = ARGV[offset + 3]
    local stored = redis.call('HGET', KEYS[1], field)
    local previous = stored and cjson.decode(stored)['_priced_at_us'] or 0
    if deadline > now then
        if version > previous then
            redis.call('HSET', KEYS[1], field, payload)
            redis.call('HPEXPIREAT', KEYS[1], deadline, 'FIELDS', 1, field)
            table.insert(matched, (offset - 1) / 4 + 1)
        elseif version == previous and stored == payload then
            table.insert(matched, (offset - 1) / 4 + 1)
        end
    end
end
return matched
"""

    def _versioned_field(
        self, row: PricedSourceModel, max_age_seconds: int
    ) -> list[str | int]:
        if row.priced_at.utcoffset() is None:
            raise ValueError("Price timestamp must include a timezone")
        version = int(row.priced_at.timestamp() * 1_000_000)
        deadline = version // 1000 + min(max_age_seconds, 86400) * 1000
        payload = row.model_dump(mode="json")
        payload["_priced_at_us"] = version
        return [str(row.source_id), version, deadline, json.dumps(payload)]

    async def set_if_priced_at_newer(
        self, code: SymbolCode, row: PricedSourceModel, *, max_age_seconds: int
    ) -> bool:
        """
        Desc: Upsert a newer field or match an identical unexpired field.
        Args:
            code (SymbolCode): Hash symbol.
            row (PricedSourceModel): Source field and timestamp to compare.
            max_age_seconds (int): Expiry offset from the supplied timestamp.
        Returns:
            return (bool): Whether the field was written or already identical.
        """
        matched = await resolve(
            self.redis.client.eval(
                self._upsert_by_version,
                1,
                self.namespace.format(symbol=code),
                *self._versioned_field(row, max_age_seconds),
            )
        )
        return bool(matched)

    async def set_many_if_priced_at_newer(
        self,
        results: Mapping[SymbolCode, Sequence[PricedSourceModel]],
        *,
        max_age_seconds: int,
    ) -> dict[SymbolCode, list[PricedSourceModel]]:
        """
        Desc: Upsert newer source fields atomically within each symbol hash.
        Args:
            results (Mapping[SymbolCode, Sequence[PricedSourceModel]]):
                Fields grouped by symbol.
            max_age_seconds (int): Expiry offset from each supplied timestamp.
        Returns:
            return (dict[SymbolCode, list[PricedSourceModel]]):
                Written or identical unexpired rows by symbol.
        """
        pending = {code: rows for code, rows in results.items() if rows}
        if not pending:
            return {}
        pipe = self.redis.client.pipeline(transaction=False)
        for code, rows in pending.items():
            fields = [
                value
                for row in rows
                for value in self._versioned_field(row, max_age_seconds)
            ]
            pipe.eval(
                self._upsert_by_version,
                1,
                self.namespace.format(symbol=code),
                *fields,
            )
        matched = await resolve(pipe.execute())
        return {
            code: [rows[index - 1] for index in indices]
            for (code, rows), indices in zip(pending.items(), matched)
            if indices
        }


class SourceSelectionCache(SourceKeyedCache[SourceSelectionModel]):
    namespace = "sources:selection:{symbol}"
    model = SourceSelectionModel


class BubbleSourceCache:
    namespace = "sources:bubble"
    adapter = TypeAdapter(list[SourceBubbleModel])

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    async def set(
        self,
        code: AssetCode,
        results: Sequence[SourceBubbleModel],
    ) -> None:
        payload = self.adapter.dump_json(list(results)).decode()
        await set_price_fields(
            self.redis,
            self.namespace,
            {code: payload},
            {
                code: min(
                    (as_utc(row.priced_at) for row in results),
                    default=utc_now(),
                )
            },
        )

    async def set_many(
        self,
        results: Mapping[AssetCode, Sequence[SourceBubbleModel]],
    ) -> None:
        mapping: dict[FieldT, str] = {
            code: self.adapter.dump_json(list(rows)).decode()
            for code, rows in results.items()
        }
        await set_price_fields(
            self.redis,
            self.namespace,
            mapping,
            {
                code: min(
                    (as_utc(row.priced_at) for row in rows), default=utc_now()
                )
                for code, rows in results.items()
            },
        )

    async def get(self, code: AssetCode) -> list[SourceBubbleModel] | None:
        raw = await resolve(self.redis.client.hget(self.namespace, code))
        results = None
        if raw is not None:
            results = self.adapter.validate_json(raw)
        return results

    async def get_many(
        self,
        codes: Sequence[AssetCode],
    ) -> dict[AssetCode, list[SourceBubbleModel]]:
        fields = [code for code in codes]
        raws = await resolve(self.redis.client.hmget(self.namespace, fields))
        found = {
            code: self.adapter.validate_json(raw)
            for code, raw in zip(codes, raws)
            if raw is not None
        }
        return found

    async def get_all(self) -> dict[AssetCode, list[SourceBubbleModel]]:
        stored = await resolve(self.redis.client.hgetall(self.namespace))
        found = {
            AssetCode(field): self.adapter.validate_json(raw)
            for field, raw in stored.items()
            if field in AssetCode.__members__.values()
        }
        return found

    async def remove(self, code: AssetCode) -> None:
        await resolve(self.redis.client.hdel(self.namespace, code))

    async def clear(self) -> None:
        await resolve(self.redis.client.delete(self.namespace))
