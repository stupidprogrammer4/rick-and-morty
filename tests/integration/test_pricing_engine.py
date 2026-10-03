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
            original = next(
                row for row in await sources.get_all() if row.code == "tgju"
            )
            edited = await sources.update(
                original.id, SourceUpdate(title="Updated test source")
            )
            assert edited.title == "Updated test source"
            errors = await scope.get(ISourceErrorService)
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
