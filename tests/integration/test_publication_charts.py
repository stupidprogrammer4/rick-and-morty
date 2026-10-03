import asyncio
import base64
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from alembic import command
from alembic.config import Config
from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from PIL import Image
from sqlalchemy import select

from portal_contracts.configuration import SettingScope
from portal_contracts.content import (
    DraftDecision,
    PublicationPage,
    PublicationPages,
    PublicationResolution,
    PublishRequest,
)
from portal_contracts.enums import BotRole
from src.modules.content.interfaces import IDraftService
from src.modules.market.domain.dtos import MarketSnapshot
from src.modules.market.interfaces import IMarketDraftCommands, IMarketQuery
from src.modules.missions.domain.dtos import ScheduledMissionCreate
from src.modules.missions.infra.tables import MissionTable
from src.modules.missions.interfaces import IMissionExecutor, IMissionService
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.calculator.interfaces import ICalculatorService
from src.modules.pricing.candle.app.helpers import WindowClock
from src.modules.pricing.candle.domain.windows import AssetPriceWindow
from src.modules.pricing.candle.infra.cache import AssetWindowCache
from src.modules.pricing.candle.interfaces import ICandleService
from src.modules.pricing.charts.domain.models import AssetChartCard
from src.modules.pricing.charts.interfaces import IAssetChartQuery
from src.modules.publishing.infra.tables import (
    PublicationChartTable,
    PublicationTable,
)
from src.modules.publishing.interfaces import (
    IPublicationChartCommands,
    IPublicationCommands,
    IPublishedPageQuery,
)
from src.shared.dates import as_utc
from tests.integration.conftest import OWNER, ExternalTelegramHandler
from tests.integration.test_pricing_engine import prepare_source_report
from tests.integration.test_workflows import (
    approved_publication,
    dispatch_publication,
)

pytestmark = pytest.mark.integration


async def prepare_charts(portal):
    await prepare_source_report(portal, full=True)
    snapshot = await portal.snapshot()
    market = snapshot.configuration.market.model_dump(mode="json")
    market["charts"]["enabled"] = True
    await portal.change("market.policy", SettingScope.GLOBAL, market)
    presentation = snapshot.presentation.model_dump(
        mode="json", exclude={"voices", "posts"}
    )
    presentation.update(
        market_pagination_enabled=True, maximum_post_characters=4000
    )
    await portal.change("presentation", SettingScope.GLOBAL, presentation)
    automation = snapshot.configuration.automation.model_dump(mode="json")
    automation["owner_id"] = OWNER
    automation["prices"].update(
        enabled=True,
        starts_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    await portal.change("automation.policy", SettingScope.GLOBAL, automation)
    async with portal.request() as scope:
        calculator = await scope.get(ICalculatorService)
        await calculator.calculate_usd()
        await calculator.calculate_all()
        priced = await (await scope.get(AssetPriceCache)).get_all()
        assert len(priced) == 4
        # Controlled observations pass through the native cache builder.
        closed = WindowClock().last_closed()
        windows = {
            code: AssetPriceWindow(
                asset_id=row.asset_id,
                open=row.price,
                high=row.price + 1000,
                low=row.price - 1000,
                close=row.price + 500,
            )
            for code, row in priced.items()
        }
        await (await scope.get(AssetWindowCache)).set_many(closed, windows)
        assert await (await scope.get(ICandleService)).build_from_cache() == 4
    portal.settings.portal.dry_run = False
    portal.environment["PORTAL_DRY_RUN"] = "false"


async def read_publications(portal):
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        parents = (await uow.execute(select(PublicationTable))).scalars().all()
        charts = (
            (await uow.execute(select(PublicationChartTable))).scalars().all()
        )
        return (
            [
                (row.id, row.status, row.message_id, row.pages)
                for row in parents
            ],
            [
                (row.id, row.asset_id, row.status, row.message_id, row.payload)
                for row in charts
            ],
        )


def test_native_scheduler_sends_paginated_prices_and_four_chart_images(portal):
    portal.run(prepare_charts(portal))
    portal.start_workers()
    parents, charts = portal.until(
        lambda: read_publications(portal),
        lambda state: (
            len(state[0]) == 1
            and state[0][0][1] == "sent"
            and len(state[1]) == 4
            and all(row[2] == "sent" for row in state[1])
        ),
        timeout=90,
    )
    publication_id, _, message_id, raw_pages = next(iter(parents))
    pages = PublicationPages.model_validate_json(raw_pages)
    assert len(pages.items) == 8
    assert len(ExternalTelegramHandler.messages) == 1
    assert len(ExternalTelegramHandler.photos) == 4
    assert len(ExternalTelegramHandler.photo_attempts) == 4
    page_text = "\n".join(page.text for page in pages.items)
    assert "والکس" in page_text and "#تتر" in page_text
    assert "<a href=" in page_text and "🟢" in page_text and "🔴" in page_text
    assert all(len(page.text) <= 4000 for page in pages.items)
    assert ExternalTelegramHandler.messages[0]["navigation"]["total"] == 8
    for photo in ExternalTelegramHandler.photos:
        assert photo["reply_to_message_id"] == message_id
        assert photo["publication_id"] == publication_id
        image = Image.open(BytesIO(base64.b64decode(photo["png_base64"])))
        assert image.format == "PNG" and image.size == (1000, 760)
        image.verify()
    frozen = [AssetChartCard.model_validate_json(row[4]) for row in charts]
    assert all(card.asset.id == row[1] for card, row in zip(frozen, charts))
    assert {card.asset.code.value for card in frozen} == {
        "gold18",
        "silver999",
        "usd",
        "usdt",
    }
    assert all(len(card.chart.candles) == 1 for card in frozen)
    assert all(
        card.chart.candles[0].high - card.chart.candles[0].low == 2000
        for card in frozen
    )

    async def pages_and_replay():
        async with portal.request() as scope:
            query = await scope.get(IPublishedPageQuery)
            page = await query.get(
                publication_id, 7, BotRole.MORTY, -100140001, message_id
            )
            assert page.text == pages.items[7].text
            with pytest.raises(NotFoundException):
                await query.get(
                    publication_id, 0, BotRole.RICK, -100140001, message_id
                )
            with pytest.raises(NotFoundException):
                await query.get(
                    publication_id,
                    0,
                    BotRole.MORTY,
                    -100140001,
                    message_id + 1,
                )
            with pytest.raises(NotFoundException):
                await query.get(
                    publication_id, 0, BotRole.MORTY, -100140002, message_id
                )
            with pytest.raises(NotFoundException):
                await query.get(
                    publication_id, 8, BotRole.MORTY, -100140001, message_id
                )
        async with portal.request() as scope:
            commands = await scope.get(IPublicationChartCommands)
            await commands.dispatch(frozen_chart_id)

    frozen_chart_id = next(iter(charts))[0]
    portal.run(pages_and_replay())
    assert len(ExternalTelegramHandler.photo_attempts) == 4


async def prepare_parent(portal):
    await prepare_charts(portal)
    stamp = datetime.now(UTC)
    key = f"prices:{int(stamp.timestamp() * 1_000_000)}"
    async with portal.request() as scope:
        await (await scope.get(IMissionService)).create_scheduled(
            ScheduledMissionCreate(
                owner_id=OWNER,
                role=BotRole.MORTY,
                intent="prices",
                text="Market",
                scheduled_at=stamp,
            )
        )
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        mission_id = (
            await uow.execute(
                select(MissionTable.id).where(
                    MissionTable.automation_key == key
                )
            )
        ).scalar_one()
        await (await scope.get(IMissionExecutor)).execute(mission_id)
    async with portal.request() as scope:
        uow = await scope.get(MySQLUnitOfWork)
        parent_id = (
            await uow.execute(select(PublicationTable.id))
        ).scalar_one()
        await (await scope.get(IPublicationCommands)).dispatch(parent_id)
    return parent_id


def test_native_chart_unknown_delivery_requires_explicit_resolution(portal):
    parent_id = portal.run(prepare_parent(portal))
    _, rows = portal.run(read_publications(portal))
    chart_id = next(iter(rows))[0]
    ExternalTelegramHandler.photo_delivery_status = "unknown"

    async def unknown():
        async with portal.request() as scope:
            await (await scope.get(IPublicationChartCommands)).dispatch(
                chart_id
            )
        async with portal.request() as scope:
            await (await scope.get(IPublicationChartCommands)).dispatch(
                chart_id
            )

    portal.run(unknown())
    assert len(ExternalTelegramHandler.photo_attempts) == 1
    _, rows = portal.run(read_publications(portal))
    assert next(row for row in rows if row[0] == chart_id)[2] == "unknown"
    ExternalTelegramHandler.photo_delivery_status = "sent"

    async def resend():
        async with portal.request() as scope:
            await (await scope.get(IPublicationChartCommands)).resolve(
                chart_id, OWNER, PublicationResolution(resend=True)
            )
        async with portal.request() as scope:
            await (await scope.get(IPublicationChartCommands)).dispatch(
                chart_id
            )

    portal.run(resend())
    assert len(ExternalTelegramHandler.photo_attempts) == 2
    assert ExternalTelegramHandler.photos[0]["publication_id"] == parent_id


def test_native_chart_rendering_keeps_event_loop_responsive(portal):
    portal.run(prepare_parent(portal))
    _, rows = portal.run(read_publications(portal))
    chart_id = next(iter(rows))[0]

    async def render_with_heartbeat():
        loop = asyncio.get_running_loop()
        ticks = []
        active = True

        def heartbeat():
            ticks.append(time.monotonic())
            if active:
                loop.call_later(0.01, heartbeat)

        heartbeat()
        async with portal.request() as scope:
            await (await scope.get(IPublicationChartCommands)).dispatch(
                chart_id
            )
        active = False
        ticks.append(time.monotonic())
        assert len(ticks) >= 3
        assert (
            max(after - before for before, after in zip(ticks, ticks[1:]))
            < 0.25
        )

    portal.run(render_with_heartbeat())
    assert len(ExternalTelegramHandler.photos) == 1


def test_native_chart_schedules_preserve_parent_microseconds(portal):
    parent_id = portal.run(prepare_parent(portal))

    async def read():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            parent = (
                await uow.execute(
                    select(PublicationTable).where(
                        PublicationTable.id == parent_id
                    )
                )
            ).scalar_one()
            charts = (
                (
                    await uow.execute(
                        select(PublicationChartTable).where(
                            PublicationChartTable.publication_id == parent.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(charts) == 4
            assert parent.scheduled_at.microsecond != 0
            assert all(
                as_utc(row.scheduled_at) == as_utc(parent.scheduled_at)
                for row in charts
            )

    portal.run(read())


def test_native_single_and_batch_chart_reads_preserve_closed_history(portal):
    portal.run(prepare_charts(portal))

    async def read():
        async with portal.request() as scope:
            query = await scope.get(IAssetChartQuery)
            cards = await query.get_all()
            selected = next(
                card for card in cards if card.asset.code.value == "usdt"
            )
            single = await query.get(selected.asset.id)
            assert single.chart.candles == selected.chart.candles
            assert single.asset.code.value == "usdt"
            assert all(
                row.en_ts <= single.chart.to_timestamp
                for row in single.chart.candles
            )

    portal.run(read())


def test_native_large_price_report_retains_every_source_in_pages(portal):
    portal.run(prepare_charts(portal))

    async def publish():
        stamp = datetime.now(UTC)
        async with portal.request() as scope:
            await (await scope.get(IMissionService)).create_scheduled(
                ScheduledMissionCreate(
                    owner_id=OWNER,
                    role=BotRole.MORTY,
                    intent="prices",
                    text="All accepted sources",
                    scheduled_at=stamp,
                )
            )
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            mission = (await uow.execute(select(MissionTable))).scalar_one()
            snapshot = await (await scope.get(IMarketQuery)).snapshot()
            gold = next(
                quote for quote in snapshot.quotes if quote.symbol == "gold"
            )
            controlled = MarketSnapshot(
                mode="sources",
                fetched_at=snapshot.fetched_at,
                quotes=[
                    gold.model_copy(
                        update={
                            "source_code": f"test-{i:03}",
                            "source_name": f"Provider-{i:03}",
                        }
                    )
                    for i in range(100)
                ],
            )
            draft = await (
                await scope.get(IMarketDraftCommands)
            ).from_snapshot(mission, controlled)
            assert len(draft.text) <= 4000 and "1/25" in draft.text
        async with portal.request() as scope:
            await (await scope.get(IDraftService)).decide(
                draft.id,
                OWNER,
                DraftDecision(revision=1, origin_bot=BotRole.MORTY),
                approve=True,
            )
        async with portal.request() as scope:
            parent = await (await scope.get(IPublicationCommands)).schedule(
                draft.id,
                OWNER,
                PublishRequest(revision=1, origin_bot=BotRole.MORTY),
            )
        async with portal.request() as scope:
            await (await scope.get(IPublicationCommands)).dispatch(parent.id)

    portal.run(publish())
    parents, _ = portal.run(read_publications(portal))
    pages = PublicationPages.model_validate_json(next(iter(parents))[3])
    assert len(pages.items) == 25
    text = "\n".join(page.text for page in pages.items)
    assert all(f"Provider-{i:03}" in text for i in range(100))
    assert next(iter(parents))[1] == "sent"


def test_chart_migration_preserves_existing_publication_and_blocks_data_loss(
    portal,
):
    portal.settings.portal.dry_run = False
    publication = portal.run(
        approved_publication(portal, "prior-chart-release")
    )
    portal.run(dispatch_publication(portal, publication.id))

    async def historical():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            row = (await uow.execute(select(PublicationTable))).scalar_one()
            return row.model_dump()

    before = portal.run(historical())
    assert before["status"] == "sent" and before["pages"] is None
    config = Config("api/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        portal.environment["PORTAL_DATABASE_URL"].replace("%", "%%"),
    )
    command.downgrade(config, "20261003_market_engine")
    command.upgrade(config, "head")
    command.check(config)
    assert portal.run(historical()) == before

    async def freeze_page():
        from sqlalchemy import update

        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            async with transaction():
                await uow.execute(
                    update(PublicationTable)
                    .where(PublicationTable.id == publication.id)
                    .values(
                        pages=PublicationPages(
                            items=[
                                PublicationPage(
                                    title="History", text="Recorded rates"
                                )
                            ],
                            previous_label="Previous",
                            next_label="Next",
                            page_label="{page}/{total}",
                        ).model_dump_json()
                    )
                )

    portal.run(freeze_page())
    with pytest.raises(RuntimeError, match="destructive downgrade"):
        command.downgrade(config, "20261003_market_engine")
    after = portal.run(historical())
    assert after["message_id"] == before["message_id"]
    assert after["pages"] is not None
    command.check(config)
