from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.pricing.retention.app import maintenance
from src.modules.pricing.retention.app.maintenance import (
    PricingHistoryMaintenance,
    history_cutoff,
)
from src.modules.pricing.retention.infra.history import HISTORY_TARGETS
from src.modules.pricing.retention.tasks.schedulers.prune import (
    PrunePricingHistory,
)


@pytest.mark.parametrize("microsecond, expected_offset", [(0, 0), (1, 1)])
def test_cutoff_is_exactly_one_day_with_fractional_expiry(
    monkeypatch, microsecond, expected_offset
):
    now = datetime(2026, 10, 6, 12, microsecond=microsecond, tzinfo=UTC)
    monkeypatch.setattr(maintenance, "utc_now", lambda: now)
    assert history_cutoff() == (int(now.timestamp()) - 86400 + expected_offset)


def test_cleanup_targets_only_the_six_pricing_time_series():
    assert {
        target.name: target.clock_column for target in HISTORY_TARGETS
    } == {
        "tbl_price_tickers": "timestamp",
        "tbl_source_price_tickers": "timestamp",
        "tbl_bubble_tickers": "timestamp",
        "tbl_source_bubble_tickers": "timestamp",
        "tbl_candles": "st_ts",
        "tbl_source_candles": "st_ts",
    }
    assert PrunePricingHistory.schedule == [{"interval": 60}]


@pytest.mark.asyncio
async def test_cleanup_is_bounded_and_continues_on_every_minute(monkeypatch):
    monkeypatch.setattr(maintenance, "history_cutoff", lambda: 1234)
    store = SimpleNamespace(prune_batch=AsyncMock(return_value=2))
    cleaner = PricingHistoryMaintenance(store)
    first = await cleaner.clean(batch_size=2, max_batches_per_table=3)
    assert set(first["removed_rows"].values()) == {6}
    assert store.prune_batch.await_count == len(HISTORY_TARGETS) * 3
    assert all(
        call.args[1:] == (1234, 2)
        for call in store.prune_batch.await_args_list
    )
    store.prune_batch.reset_mock()
    store.prune_batch.return_value = 0
    next_run = await PrunePricingHistory(cleaner).run()
    assert set(next_run["removed_rows"].values()) == {0}
    assert store.prune_batch.await_count == len(HISTORY_TARGETS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"batch_size": 0},
        {"batch_size": 10001},
        {"max_batches_per_table": 0},
        {"max_batches_per_table": 10001},
    ],
)
async def test_cleanup_rejects_unbounded_batches_before_any_deletion(
    arguments,
):
    store = SimpleNamespace(prune_batch=AsyncMock())
    with pytest.raises(ValueError):
        await PricingHistoryMaintenance(store).clean(**arguments)
    store.prune_batch.assert_not_awaited()
