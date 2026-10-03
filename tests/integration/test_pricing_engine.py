import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import func, select

from portal_contracts.configuration import SettingScope
from src.cli.pricing_seed import seed_pricing
from src.modules.market.interfaces import IMarketQuery
from src.modules.missions.infra.tables import MissionTable
from src.modules.missions.interfaces import IScheduledMissionCommands
from src.modules.pricing.assets.infra.tables import AssetTable
from src.modules.pricing.engine.domain.quotes import (
    IranSourceQuote,
    SourceQuote,
)
from src.modules.pricing.engine.interfaces import (
    ICacheFlusherService,
    ICFGReaderService,
)
from src.modules.pricing.sources.domain.enums import SourceCode
from src.modules.pricing.sources.infra.tables import (
    SourceConfigTable,
    SourceTable,
)
from src.modules.pricing.symbols.domain.enums import SymbolCode
from src.modules.pricing.symbols.infra.tables import SymbolTable
from src.modules.publishing.infra.tables import (
    PrivateReplyTable,
    PublicationTable,
)

pytestmark = pytest.mark.integration
OWNER = 140001


async def prepare_market(portal):
    snapshot = await portal.snapshot()
    market = snapshot.configuration.market.model_dump(mode="json")
    market["backend"] = "auryx"
    await portal.change("market.policy", SettingScope.GLOBAL, market)
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        async with transaction():
            result = await uow.execute(
                select(SourceTable).where(
                    SourceTable.code.in_(["tgju", "goldika", "meligold"])
                )
            )
            rows = result.scalars().all()
            configs = (
                (
                    await uow.execute(
                        select(SourceConfigTable).where(
                            SourceConfigTable.source_id.in_(
                                [row.id for row in rows]
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                row.is_active = True
            # Controlled external quote inputs; crawler performs no HTTP.
            for config in configs:
                config.fetchers = {}
            await uow.flush()
        cfg = await (await scope.get(ICFGReaderService)).read_context()
        flusher = await scope.get(ICacheFlusherService)
        irans = [
            IranSourceQuote.from_buying_selling(
                code, SymbolCode.GOLD18_GRAM, amount, amount
            )
            for code, amount in [
                (SourceCode.TGJU, 100_000_000),
                (SourceCode.GOLDIKA, 102_000_000),
                (SourceCode.MELIGOLD, 1_000_000_000),
            ]
        ]
        irans += [
            IranSourceQuote.from_buying_selling(
                SourceCode.TGJU, SymbolCode.USD_RIAL, 2_000_000, 2_000_000
            ),
            IranSourceQuote.from_buying_selling(
                SourceCode.TGJU, SymbolCode.SILVER_GRAM, 5_000_000, 5_000_000
            ),
        ]
        await flusher.flush_results(
            cfg, SourceQuote(irans=irans, globals=[], suppliers=[], bubbles=[])
        )


def test_native_market_seed_and_aggregation_preserve_configuration(portal):
    async def workflow():
        await prepare_market(portal)
        async with portal.request() as scope:
            market = await scope.get(IMarketQuery)
            prices = await market.snapshot()
            amounts = {row.symbol: row.amount for row in prices.quotes}
            assert amounts == {
                "gold": 101_000_000,
                "silver": 5_000_000,
                "usd": 2_000_000,
            }
            assert all(
                row.timestamp_kind == "fetched" for row in prices.quotes
            )
            gold = next(row for row in prices.quotes if row.symbol == "gold")
            assert len(gold.sources) == 2
            report = await market.report()
            assert (
                "#طلا_۱۸_عیار" in report
                and "#دلار" in report
                and "#نقره_۹۹۹" in report
            )
            assert "🟡✨" in report and "💵💸" in report and "⚪💎" in report
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            await seed_pricing(uow, Path("api/seeds/pricing.json"))
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            sources = (await uow.execute(select(SourceTable))).scalars().all()
            assert len(sources) == 18
            assert sum(row.is_active for row in sources) == 3
            assert (
                await uow.execute(select(func.count()).select_from(AssetTable))
            ).scalar_one() == 3
            assert (
                await uow.execute(
                    select(func.count()).select_from(SymbolTable)
                )
            ).scalar_one() == 6

    portal.run(workflow())


def test_native_scheduler_publishes_one_scheduled_market_slot(portal):
    portal.settings.portal.dry_run = False
    portal.environment["PORTAL_DRY_RUN"] = "false"

    async def prepare():
        await prepare_market(portal)
        snapshot = await portal.snapshot()
        policy = snapshot.configuration.automation.model_dump(mode="json")
        policy["owner_id"] = OWNER
        policy["prices"].update(
            enabled=True,
            starts_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        )
        await portal.change("automation.policy", SettingScope.GLOBAL, policy)

    portal.run(prepare())
    portal.start_workers()

    async def read():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            rows = await uow.execute(select(PublicationTable))
            return [(row.id, row.status) for row in rows.scalars().all()]

    sent = portal.until(
        read, lambda rows: len(rows) == 1 and rows[0][1] == "sent", timeout=85
    )
    assert len(sent) == 1

    async def replay():
        async def tick():
            async with portal.request() as scope:
                await (await scope.get(IScheduledMissionCommands)).tick()

        await asyncio.gather(tick(), tick())
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            assert (
                await uow.execute(
                    select(func.count()).select_from(MissionTable)
                )
            ).scalar_one() == 1
            assert (
                await uow.execute(
                    select(func.count()).select_from(PrivateReplyTable)
                )
            ).scalar_one() == 0

    portal.run(replay())
    from tests.integration.conftest import ExternalTelegramHandler

    assert len(ExternalTelegramHandler.messages) == 1
    payload = ExternalTelegramHandler.messages[0]
    assert payload["role"] == "morty" and payload["chat_id"] == -100140001
    assert "#قیمت_پورتال" in payload["text"] and "#نقره_۹۹۹" in payload["text"]


def test_mysql_source_errors_credentials_and_loaded_update_are_persisted(
    portal,
):
    from src.modules.pricing.sources.domain.dtos import SourceUpdate
    from src.modules.pricing.sources.domain.enums import ErrorType
    from src.modules.pricing.sources.interfaces import (
        ISourceConfigService,
        ISourceErrorService,
        ISourceService,
    )

    async def workflow():
        async with portal.request() as scope:
            sources = await scope.get(ISourceService)
            source_rows = await sources.get_all()
            original = next(row for row in source_rows if row.code == "tgju")
            edited = await sources.update(
                original.id, SourceUpdate(title="Updated test source")
            )
            assert edited.title == "Updated test source"
            errors = await scope.get(ISourceErrorService)
            updated = await errors.apply_error(original.id, None)
            assert updated.error is None
            await errors.apply_errors(
                {
                    original.id: {
                        "kind": ErrorType.HTTP_ERROR,
                        "message": "Refused",
                        "status_code": 503,
                    }
                }
            )
            configs = await scope.get(ISourceConfigService)
            await configs.update_headers_credentials(
                {original.id: {"X-Test-Header": "test-only-value"}}
            )
        async with portal.request() as scope:
            sources = await scope.get(ISourceService)
            saved = await sources.get_by_id(original.id)
            assert saved.title == "Updated test source"
            assert saved.error["status_code"] == 503
            configs = await scope.get(ISourceConfigService)
            saved_config = await configs.get_by_source_id(original.id)
            assert saved_config.headers_credentials == {
                "X-Test-Header": "test-only-value"
            }

    portal.run(workflow())


def test_native_pricing_schedules_reach_the_worker_and_settle_prices(portal):
    from sqlalchemy import update

    from src.modules.pricing.assets.infra.tables import AssetConfigTable
    from src.modules.pricing.calculator.infra.cache import AssetPriceCache

    async def prepare():
        await prepare_market(portal)
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            async with transaction():
                await uow.execute(
                    update(AssetConfigTable).values(
                        scheduler_on=True, scheduler_seconds=20
                    )
                )
            cache = await scope.get(AssetPriceCache)
            assert not await cache.get_all()

    portal.run(prepare())
    portal.start_workers()

    async def read():
        async with portal.request() as scope:
            cache = await scope.get(AssetPriceCache)
            rows = await cache.get_all()
            from papilio_tasks.apps.schedulers.redis import (
                SchedulerApplication,
            )

            from src.modules.pricing.calculator.infra.schedules import (
                ScheduleReader,
            )

            source = (await scope.get(SchedulerApplication)).source
            configs = await (await scope.get(ScheduleReader)).get_all()
            schedules = await source.list_schedules()
            return {
                "prices": {str(code): row.price for code, row in rows.items()},
                "schedules": [s.model_dump() for s in schedules],
                "configs": [c.model_dump() for c in configs],
            }

    state = portal.until(
        read, lambda rows: len(rows["prices"]) == 3, timeout=65
    )
    assert state["prices"] == {
        "gold18": 101_000_000,
        "silver999": 5_000_000,
        "usd": 2_000_000,
    }


def test_pricing_configuration_creation_and_switch_removal_keep_owner(portal):
    from sqlalchemy import delete

    from src.modules.pricing.assets.config.constants import (
        ASSET_SWITCH_ID_ENCRYPTION,
    )
    from src.modules.pricing.assets.domain.dtos import (
        AssetSwitchBatchCreate,
        AssetSwitchBatchDelete,
        AssetSwitchCreate,
    )
    from src.modules.pricing.assets.infra.tables import AssetConfigTable
    from src.modules.pricing.assets.interfaces import (
        IAssetConfigService,
        IAssetSwitchService,
    )
    from src.modules.pricing.bubbles.infra.tables import (
        BubbleConfigTable,
        BubbleTable,
    )
    from src.modules.pricing.bubbles.interfaces import IBubbleConfigService
    from src.modules.pricing.sources.interfaces import ISourceConfigService

    async def workflow():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            assets = (await uow.execute(select(AssetTable))).scalars().all()
            by_code = {row.code: row.id for row in assets}
            sources = (await uow.execute(select(SourceTable))).scalars().all()
            by_source = {row.code: row.id for row in sources}
            bubble = (await uow.execute(select(BubbleTable))).scalar_one()
            from src.modules.pricing.calculator.infra.readers import (
                BubbleReader,
            )

            context = await (await scope.get(BubbleReader)).get_bubble_config(
                bubble.id
            )
            assert context.asset_id == by_code["gold18"]
            async with transaction():
                await uow.execute(delete(AssetConfigTable))
                await uow.execute(delete(SourceConfigTable))
                await uow.execute(delete(BubbleConfigTable))
            configs = await scope.get(IAssetConfigService)
            usd = await configs.create_default(by_code["usd"], "usd")
            assert usd.asset_id == by_code["usd"]
            assert usd.scheduler_seconds == 30
            metals = await configs.create_defaults(
                {row.id: row.code for row in assets if row.code != "usd"}
            )
            assert {row.asset_id for row in metals} == {
                by_code["gold18"],
                by_code["silver999"],
            }
            source_configs = await scope.get(ISourceConfigService)
            tgju = await source_configs.create_default(by_source["tgju"])
            assert tgju.source_id == by_source["tgju"]
            other = await source_configs.create_defaults(
                [by_source["goldika"], by_source["meligold"]]
            )
            assert {row.source_id for row in other} == {
                by_source["goldika"],
                by_source["meligold"],
            }
            bubbles = await scope.get(IBubbleConfigService)
            created = await bubbles.create_default(bubble.id)
            assert created.bubble_id == bubble.id
            switches = await scope.get(IAssetSwitchService)
            entries = await switches.batch_create(
                by_code["usd"],
                AssetSwitchBatchCreate(
                    items=[
                        AssetSwitchCreate(switch="supplier", priority=2),
                        AssetSwitchCreate(switch="global_market", priority=3),
                    ]
                ),
            )
            supplier = next(row for row in entries if row.switch == "supplier")
            global_market = next(
                row for row in entries if row.switch == "global_market"
            )
            supplier_id = supplier.id
            global_market_id = global_market.id
            removed = await switches.remove(by_code["usd"], supplier_id)
            assert removed.id == supplier_id
            from papilio.errors.exceptions import ValidationException

            with pytest.raises(ValidationException):
                await switches.batch_remove(
                    by_code["gold18"],
                    AssetSwitchBatchDelete(
                        ids=[
                            ASSET_SWITCH_ID_ENCRYPTION.encode(global_market_id)
                        ]
                    ),
                )
        async with portal.request() as scope:
            configs = await scope.get(IAssetConfigService)
            assert len(await configs.get_all()) == 3
            source_configs = await scope.get(ISourceConfigService)
            assert len(await source_configs.get_all()) == 3
            switches = await scope.get(IAssetSwitchService)
            saved = await switches.get_by_asset_id(by_code["usd"])
            assert any(row.id == global_market_id for row in saved)
            assert not any(row.id == supplier_id for row in saved)

    portal.run(workflow())


def test_native_supplier_batch_preserves_quote_versions(portal):
    from sqlalchemy import update
    from taskiq import ScheduleSource

    from src.modules.pricing.engine.interfaces import ICacheReaderService
    from src.modules.pricing.engine.tasks.schedulers.price import (
        PersistSupplierPrice,
    )

    now = datetime.now(UTC)
    payload = {
        "source": "talaland",
        "quotes": [
            {
                "symbol": "gold18_gram",
                "buying_rial": 100_000_000,
                "selling_rial": 102_000_000,
                "quoted_at": now.isoformat(),
            },
            {
                "symbol": "silver_gram",
                "buying_rial": 5_000_000,
                "selling_rial": 5_200_000,
                "quoted_at": now.isoformat(),
            },
        ],
    }

    async def prepare():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            supplier = (
                await uow.execute(
                    select(SourceTable).where(
                        SourceTable.code == SourceCode.TALALAND
                    )
                )
            ).scalar_one()
            async with transaction():
                await uow.execute(
                    update(SourceConfigTable)
                    .where(SourceConfigTable.source_id == supplier.id)
                    .values(fetchers={})
                )
                await uow.execute(
                    update(SourceTable)
                    .where(SourceTable.code == SourceCode.TALALAND)
                    .values(is_active=True)
                )
            source = await scope.get(ScheduleSource)
            await PersistSupplierPrice.task().schedule_by_time(
                source, now + timedelta(seconds=1), data=payload
            )

    portal.run(prepare())
    portal.start_workers()

    async def read():
        async with portal.request() as scope:
            cache = await scope.get(ICacheReaderService)
            rows = await cache.get_many_by_symbols(
                [SymbolCode.GOLD18_GRAM, SymbolCode.SILVER_GRAM]
            )
            return {
                str(code): (line.buy_price, line.sell_price, line.priced_at)
                for code, readings in rows.items()
                for line in readings
            }

    current = portal.until(read, lambda rows: len(rows) == 2, timeout=35)
    assert current["gold18_gram"][:2] == (100_000_000, 102_000_000)
    assert current["silver_gram"][:2] == (5_000_000, 5_200_000)
    older = {
        **payload,
        "quotes": [
            {
                **quote,
                "buying_rial": 1,
                "selling_rial": 2,
                "quoted_at": (now - timedelta(seconds=1)).isoformat(),
            }
            for quote in payload["quotes"]
        ],
    }

    async def replay():
        task = await PersistSupplierPrice.enqueue(data=older)
        result = await task.wait_result(timeout=20)
        assert not result.is_err

    portal.run(replay())
    assert portal.run(read()) == current
