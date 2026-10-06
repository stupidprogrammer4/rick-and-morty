from typing import Mapping, Sequence

from papilio.infra.redis.client import RedisClient, resolve
from redis.typing import FieldT

from src.config.settings import PortalAppSettings
from src.modules.pricing.assets.domain.enums import AssetCode
from src.modules.pricing.calculator.domain.models import (
    AssetBubbleModel,
    AssetPriceModel,
)
from src.shared.cache_retention import set_price_fields


class AssetPriceCache:
    namespace = "assets:price"

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    async def set(
        self,
        code: AssetCode,
        result: AssetPriceModel,
    ) -> None:
        await set_price_fields(
            self.redis,
            self.namespace,
            {code: result.model_dump_json()},
            {code: result.priced_at},
        )

    async def set_many(
        self,
        results: Mapping[AssetCode, AssetPriceModel],
    ) -> None:
        mapping: dict[FieldT, str] = {
            code: result.model_dump_json() for code, result in results.items()
        }
        await set_price_fields(
            self.redis,
            self.namespace,
            mapping,
            {code: row.priced_at for code, row in results.items()},
        )

    async def get(self, code: AssetCode) -> AssetPriceModel | None:
        raw = await resolve(self.redis.client.hget(self.namespace, code))
        result = None
        if raw is not None:
            result = AssetPriceModel.model_validate_json(raw)
        return result

    async def get_many(
        self,
        codes: Sequence[AssetCode],
    ) -> dict[AssetCode, AssetPriceModel]:
        fields = [code for code in codes]
        raws = await resolve(self.redis.client.hmget(self.namespace, fields))
        found = {
            code: AssetPriceModel.model_validate_json(raw)
            for code, raw in zip(codes, raws)
            if raw is not None
        }
        return found

    async def get_all(self) -> dict[AssetCode, AssetPriceModel]:
        stored = await resolve(self.redis.client.hgetall(self.namespace))
        found = {
            AssetCode(field): AssetPriceModel.model_validate_json(raw)
            for field, raw in stored.items()
            if field in AssetCode.__members__.values()
        }
        return found

    async def remove(self, code: AssetCode) -> None:
        await resolve(self.redis.client.hdel(self.namespace, code))

    async def clear(self) -> None:
        await resolve(self.redis.client.delete(self.namespace))


class BubbleCache:
    namespace = "bubble:price"

    def __init__(
        self, redis: RedisClient, settings: PortalAppSettings
    ) -> None:
        self.redis = redis
        self.namespace = f"{settings.tasks.queue_name}:{self.namespace}"

    async def set(self, code: AssetCode, result: AssetBubbleModel) -> None:
        await set_price_fields(
            self.redis,
            self.namespace,
            {code: result.model_dump_json()},
            {code: result.priced_at},
        )

    async def set_many(
        self,
        results: Mapping[AssetCode, AssetBubbleModel],
    ) -> None:
        mapping: dict[FieldT, str] = {
            code: result.model_dump_json() for code, result in results.items()
        }
        await set_price_fields(
            self.redis,
            self.namespace,
            mapping,
            {code: row.priced_at for code, row in results.items()},
        )

    async def get(self, code: AssetCode) -> AssetBubbleModel | None:
        raw = await resolve(self.redis.client.hget(self.namespace, code))
        result = None
        if raw is not None:
            result = AssetBubbleModel.model_validate_json(raw)
        return result

    async def get_many(
        self,
        codes: Sequence[AssetCode],
    ) -> dict[AssetCode, AssetBubbleModel]:
        fields = [code for code in codes]
        raws = await resolve(self.redis.client.hmget(self.namespace, fields))
        found = {
            code: AssetBubbleModel.model_validate_json(raw)
            for code, raw in zip(codes, raws)
            if raw is not None
        }
        return found

    async def get_all(self) -> dict[AssetCode, AssetBubbleModel]:
        stored = await resolve(self.redis.client.hgetall(self.namespace))
        found = {
            AssetCode(field): AssetBubbleModel.model_validate_json(raw)
            for field, raw in stored.items()
            if field in AssetCode.__members__.values()
        }
        return found

    async def remove(self, code: AssetCode) -> None:
        await resolve(self.redis.client.hdel(self.namespace, code))

    async def clear(self) -> None:
        await resolve(self.redis.client.delete(self.namespace))
