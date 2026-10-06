"""Keep at most one day's historical prices using short cleanup batches."""

from math import ceil

from src.modules.pricing.retention.infra.history import (
    HISTORY_TARGETS,
    PricingHistoryStore,
)
from src.shared.dates import utc_now

HISTORY_RETENTION_SECONDS = 24 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 60


def history_cutoff() -> int:
    # Stored timestamps are whole seconds; ceil also removes a row already
    # expired by a fraction of a second, preserving an exact boundary row.
    return ceil(utc_now().timestamp() - HISTORY_RETENTION_SECONDS)


class PricingHistoryMaintenance:
    def __init__(self, history: PricingHistoryStore):
        self.history = history

    async def stats(self) -> dict:
        cutoff = history_cutoff()
        return {
            "retention_seconds": HISTORY_RETENTION_SECONDS,
            "cutoff_timestamp": cutoff,
            "expired_rows": await self.history.expired_counts(cutoff),
        }

    async def clean(
        self, *, batch_size: int = 1000, max_batches_per_table: int = 20
    ) -> dict:
        if not 1 <= batch_size <= 10000:
            raise ValueError("Pricing cleanup batches must be 1..10000 rows")
        if not 1 <= max_batches_per_table <= 10000:
            raise ValueError(
                "Pricing cleanup needs 1..10000 batches per table"
            )
        cutoff = history_cutoff()
        removed = {}
        for target in HISTORY_TARGETS:
            total = 0
            for _ in range(max_batches_per_table):
                count = await self.history.prune_batch(
                    target, cutoff, batch_size
                )
                total += count
                if count < batch_size:
                    break
            removed[target.name] = total
        return {
            "retention_seconds": HISTORY_RETENTION_SECONDS,
            "cutoff_timestamp": cutoff,
            "removed_rows": removed,
        }
