from datetime import timedelta

from src.modules.ops.retention.infra.cache import VariableCacheStore
from src.modules.ops.retention.infra.history import (
    HISTORY_TABLES,
    BotHistoryStore,
)
from src.shared.dates import utc_now

RETENTION_SECONDS = 86400


class BotHistoryMaintenance:
    def __init__(self, history: BotHistoryStore, cache: VariableCacheStore):
        self.history = history
        self.cache = cache

    async def stats(self) -> dict:
        cutoff = utc_now() - timedelta(seconds=RETENTION_SECONDS)
        return {
            "retention_seconds": RETENTION_SECONDS,
            "expired_rows": await self.history.expired_counts(cutoff),
        }

    async def clean(
        self, *, batch_size: int = 100, max_batches_per_table: int = 20
    ) -> dict:
        if (
            not 1 <= batch_size <= 1000
            or not 1 <= max_batches_per_table <= 1000
        ):
            raise ValueError("Cleanup limits must be 1..1000")
        now = utc_now()
        cutoff = now - timedelta(seconds=RETENTION_SECONDS)
        removed = {}
        for table in HISTORY_TABLES:
            for _ in range(max_batches_per_table):
                count, deleted = await self.history.prune_batch(
                    table, cutoff, batch_size
                )
                for name, total in deleted.items():
                    removed[name] = removed.get(name, 0) + total
                if count < batch_size:
                    break
        removed["tbl_ai_budgets"] = await self.history.prune_budgets(now)
        return {
            "retention_seconds": RETENTION_SECONDS,
            "removed_rows": removed,
            "removed_cache_fields": await self.cache.prune(),
        }
