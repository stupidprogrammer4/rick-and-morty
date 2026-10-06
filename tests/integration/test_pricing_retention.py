from datetime import UTC, datetime, timedelta

import pytest
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import insert, select

from portal_contracts.content import DraftCreate
from portal_contracts.enums import BotRole, Category
from src.cli.pricing_retention import run as run_retention
from src.modules.content.drafts.infra.tables import DraftTable
from src.modules.content.drafts.interfaces import IDraftService
from src.modules.pricing.assets.infra.tables import AssetTable
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.candle.domain.enums import TimeFrame
from src.modules.pricing.retention.app import maintenance
from src.modules.pricing.retention.app.maintenance import (
    PricingHistoryMaintenance,
)
from src.modules.pricing.retention.infra.history import HISTORY_TARGETS
from src.modules.pricing.sources.infra.tables import SourceTable
from src.modules.pricing.symbols.infra.tables import SymbolTable
from src.shared.dates import utc_now
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


async def seed_history(portal, now):
    cutoff = int(now.timestamp()) - 86400
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        asset = (await uow.execute(select(AssetTable))).scalars().first()
        source = (await uow.execute(select(SourceTable))).scalars().first()
        symbol = (await uow.execute(select(SymbolTable))).scalars().first()
        async with transaction():
            for target in HISTORY_TARGETS:
                rows = []
                for stamp in (cutoff - 1, cutoff, int(now.timestamp()) - 1):
                    if target.clock_column == "st_ts":
                        for frame in TimeFrame:
                            row = {
                                "open": 100,
                                "high": 110,
                                "low": 90,
                                "close": 105,
                                "timeframe": frame.value,
                                "st_ts": stamp,
                                "en_ts": stamp + frame.seconds,
                            }
                            if target.name == "tbl_candles":
                                row["asset_id"] = asset.id
                            else:
                                row.update(
                                    symbol_id=symbol.id, source_id=source.id
                                )
                            rows.append(row)
                    else:
                        row = {"price": 100, "timestamp": stamp}
                        if target.name == "tbl_source_price_tickers":
                            row.update(
                                symbol_id=symbol.id, source_id=source.id
                            )
                        else:
                            row["asset_id"] = asset.id
                            if target.name == "tbl_source_bubble_tickers":
                                row["source_id"] = source.id
                        rows.append(row)
                await uow.execute(insert(target.table).values(rows))
        quote = AssetPriceModel(
            asset_id=asset.id,
            price=120,
            buy_price=120,
            sell_price=120,
            buy_spread=0,
            sell_spread=0,
            buy_spread_rate=0,
            sell_spread_rate=0,
            priced_at=now,
        )
        await (await scope.get(AssetPriceCache)).set(asset.code, quote)
        draft = await (await scope.get(IDraftService)).create(
            OWNER,
            BotRole.RICK,
            DraftCreate(
                category=Category.NEWS,
                title="Unrelated bot audit",
                text="Preserved publication content",
                publisher_bot=BotRole.RICK,
            ),
            key="pricing-retention-unrelated",
        )
    return cutoff, asset.code, quote, draft.id


async def history_rows(portal):
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        return {
            target.name: (await uow.execute(select(target.table)))
            .scalars()
            .all()
            for target in HISTORY_TARGETS
        }


def test_native_retention_cli_preserves_boundary_latest_quote_and_bot_audit(
    portal, monkeypatch
):
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    monkeypatch.setattr(maintenance, "utc_now", lambda: now)

    async def workflow():
        cutoff, asset_code, quote, draft_id = await seed_history(portal, now)
        initial = await history_rows(portal)
        stats = await run_retention(
            apply=False, batch_size=2, max_batches_per_table=20
        )
        assert stats["dry_run"]
        assert stats["cutoff_timestamp"] == cutoff
        assert sorted(stats["expired_rows"].values()) == [1, 1, 1, 1, 4, 4]
        unchanged = await history_rows(portal)
        assert {key: len(rows) for key, rows in unchanged.items()} == {
            key: len(rows) for key, rows in initial.items()
        }
        result = await run_retention(
            apply=True, batch_size=2, max_batches_per_table=20
        )
        assert result["removed_rows"] == stats["expired_rows"]
        assert set(result["remaining_expired_rows"].values()) == {0}
        remaining = await history_rows(portal)
        for target in HISTORY_TARGETS:
            clocks = [
                getattr(row, target.clock_column)
                for row in remaining[target.name]
            ]
            assert cutoff in clocks
            assert all(stamp >= cutoff for stamp in clocks)
            assert len(clocks) == (8 if target.clock_column == "st_ts" else 2)
        async with portal.request() as scope:
            assert (
                await (await scope.get(AssetPriceCache)).get(asset_code)
                == quote
            )
            uow = await scope.get(MySQLUnitOfWork)
            retained = (
                await uow.execute(
                    select(DraftTable).where(DraftTable.id == draft_id)
                )
            ).scalar_one()
            assert retained.text == "Preserved publication content"
            cleaner = await scope.get(PricingHistoryMaintenance)
            repeated = await cleaner.clean()
            assert set(repeated["removed_rows"].values()) == {0}

    portal.run(workflow())


def test_native_retention_scheduler_is_registered_and_executes_cleanup(portal):
    async def prepare():
        from src.apps.scheduler import app

        now = utc_now().replace(microsecond=0)
        await seed_history(portal, now)
        await app.connect()
        task = app.broker.find_task(
            "src.modules.pricing.retention.tasks.schedulers.prune."
            "PrunePricingHistory"
        )
        assert task is not None
        await task.schedule_by_time(
            app.source.native, utc_now() + timedelta(seconds=2)
        )

    portal.run(prepare())
    portal.start_workers()

    async def remaining():
        async with portal.request() as scope:
            cleaner = await scope.get(PricingHistoryMaintenance)
            result = await cleaner.stats()
            return sum(result["expired_rows"].values())

    assert portal.until(remaining, lambda count: count == 0) == 0
