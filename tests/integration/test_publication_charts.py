import asyncio
import base64
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch

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
from src.modules.automation.missions.domain.dtos import ScheduledMissionCreate
from src.modules.automation.missions.infra.tables import MissionTable
from src.modules.automation.missions.interfaces import (
    IMissionExecutor,
    IMissionService,
)
from src.modules.content.drafts.interfaces import (
    IDraftService,
    IMarketDraftCommands,
)
from src.modules.content.publications.infra.tables import (
    PublicationChartTable,
    PublicationTable,
)
from src.modules.content.publications.interfaces import (
    IPublicationChartCommands,
    IPublicationCommands,
    IPublishedChartPageQuery,
    IPublishedPageQuery,
)
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.calculator.interfaces import ICalculatorService
from src.modules.pricing.candle.app.helpers import WindowClock
from src.modules.pricing.candle.domain.windows import AssetPriceWindow
from src.modules.pricing.candle.infra.cache import AssetWindowCache
from src.modules.pricing.candle.interfaces import ICandleService
from src.modules.pricing.charts.domain.models import ChartGallery
from src.modules.pricing.charts.infra.browser import BrowserImageRenderer
from src.modules.pricing.charts.interfaces import (
    IAssetChartQuery,
    IAssetChartRenderer,
)
from src.modules.pricing.reports.domain.dtos import MarketSnapshot
from src.modules.pricing.reports.interfaces import (
    IMarketQuery,
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


def test_native_scheduler_sends_paginated_prices_and_one_chart_gallery(portal):
    portal.run(prepare_charts(portal))
    portal.start_workers()
    parents, charts = portal.until(
        lambda: read_publications(portal),
        lambda state: (
            len(state[0]) == 1
            and state[0][0][1] == "sent"
            and len(state[1]) == 1
            and all(row[2] == "sent" for row in state[1])
        ),
        timeout=90,
    )
    publication_id, _, message_id, raw_pages = next(iter(parents))
    pages = PublicationPages.model_validate_json(raw_pages)
    assert len(pages.items) == 8
    assert len(ExternalTelegramHandler.messages) == 1
    assert len(ExternalTelegramHandler.photos) == 1
    assert len(ExternalTelegramHandler.photo_attempts) == 1
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
    frozen = ChartGallery.model_validate_json(charts[0][4]).cards
    assert charts[0][1] is None
    assert ExternalTelegramHandler.photos[0]["navigation"]["total"] == 4
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

    async def assert_all_pages_prepared():
        # A new request/process can reuse every page before a user clicks it.
        async with portal.request() as scope:
            renderer = await scope.get(IAssetChartRenderer)
            with patch.object(
                BrowserImageRenderer,
                "render",
                AsyncMock(
                    side_effect=AssertionError("Unexpected browser launch")
                ),
            ):
                for card in frozen:
                    assert (await renderer.render(card)).startswith(b"\x89PNG")

    portal.run(assert_all_pages_prepared())
    frozen_chart_id = next(iter(charts))[0]
    portal.run(pages_and_replay())
    assert len(ExternalTelegramHandler.photo_attempts) == 1

    async def gallery_pages():
        chart_id, _, _, photo_id, _ = charts[0]
        async with portal.request() as scope:
            query = await scope.get(IPublishedChartPageQuery)
            result = await query.get(
                chart_id, 3, BotRole.MORTY, -100140001, photo_id
            )
            assert result.navigation.page == 3 and result.navigation.total == 4
            assert result.navigation.chart_id == chart_id
            image = Image.open(BytesIO(base64.b64decode(result.png_base64)))
            image.verify()
            for role, chat, message, page in [
                (BotRole.RICK, -100140001, photo_id, 0),
                (BotRole.MORTY, -100140002, photo_id, 0),
                (BotRole.MORTY, -100140001, photo_id + 1, 0),
                (BotRole.MORTY, -100140001, photo_id, 4),
            ]:
                with pytest.raises(NotFoundException):
                    await query.get(chart_id, page, role, chat, message)

    portal.run(gallery_pages())
    assert len(ExternalTelegramHandler.photo_attempts) == 1


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
            assert len(charts) == 1
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


# Check chart rollback before the irreversible provider revision.
@pytest.mark.schema_revision("20261024_chart_payload")
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
    config.set_main_option("script_location", portal.migration_scripts)
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
    # MySQL may commit empty descendant downgrades before the chart guard.
    command.upgrade(config, "head")
    command.check(config)


async def independent_chart_policy(portal, *, prices: bool = False):
    await prepare_charts(portal)
    snapshot = await portal.snapshot()
    if prices:
        # This scenario publishes two parents; the harness normally caps one.
        policy = snapshot.configuration.portal.model_dump(
            mode="json", exclude={"dry_run"}
        )
        policy["daily_post_cap"] = 2
        await portal.change("portal.policy", SettingScope.GLOBAL, policy)
    automation = snapshot.configuration.automation.model_dump(mode="json")
    anchor = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    automation["news"]["enabled"] = False
    automation["prices"].update(
        enabled=prices, starts_at=anchor, interval_seconds=7200
    )
    automation["charts"].update(
        enabled=True, starts_at=anchor, interval_seconds=25200
    )
    await portal.change("automation.policy", SettingScope.GLOBAL, automation)


def test_native_independent_chart_scheduler_without_price_mission(portal):
    portal.run(independent_chart_policy(portal))
    portal.start_workers()
    parents, charts = portal.until(
        lambda: read_publications(portal),
        lambda state: (
            len(state[0]) == 1
            and state[0][0][1] == "sent"
            and len(state[1]) == 1
            and all(row[2] == "sent" for row in state[1])
        ),
        timeout=90,
    )
    assert parents[0][3] is None
    assert len(ExternalTelegramHandler.messages) == 1
    assert len(ExternalTelegramHandler.photos) == 1
    assert "نمودارهای بازار" in ExternalTelegramHandler.messages[0]["text"]

    async def mission_and_draft():
        from src.modules.content.drafts.infra.tables import DraftTable

        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            mission = (await uow.execute(select(MissionTable))).scalar_one()
            draft = (await uow.execute(select(DraftTable))).scalar_one()
            assert mission.intent == "charts" and mission.bot_id == -4
            assert mission.automation_key.startswith("charts:")
            assert draft.category == "charts"
            assert draft.market_snapshot_id is None
            assert not draft.synthetic

    portal.run(mission_and_draft())
    gallery = ChartGallery.model_validate_json(charts[0][4])
    assert len(gallery.cards) == 4
    assert all(card.chart.candles for card in gallery.cards)


def test_native_separate_chart_cadence_avoids_price_chart_duplicates(portal):
    portal.run(independent_chart_policy(portal, prices=True))
    portal.start_workers()

    async def checked_state():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            missions = (
                (await uow.execute(select(MissionTable))).scalars().all()
            )
            assert not any(row.status == "failed" for row in missions), [
                (row.intent, row.status, row.failure_reason)
                for row in missions
            ]
        return await read_publications(portal)

    parents, charts = portal.until(
        checked_state,
        lambda state: (
            len(state[0]) == 2
            and all(row[1] == "sent" for row in state[0])
            and len(state[1]) == 1
            and all(row[2] == "sent" for row in state[1])
        ),
        timeout=90,
    )
    assert len(ExternalTelegramHandler.messages) == 2
    assert len(ExternalTelegramHandler.photos) == 1
    chart_parent = next(row for row in parents if row[3] is None)
    price_parent = next(row for row in parents if row[3] is not None)
    assert chart_parent[0] != price_parent[0]
    assert all(
        photo["publication_id"] == chart_parent[0]
        for photo in ExternalTelegramHandler.photos
    )


def test_native_full_twelve_hour_gallery_preserves_all_observations(portal):
    from src.modules.content.publications.infra.charts import (
        PublicationChartRepository,
    )

    portal.run(prepare_parent(portal))
    _, charts = portal.run(read_publications(portal))
    chart_id = charts[0][0]

    async def save_full_history():
        async with portal.request() as scope:
            repo = await scope.get(PublicationChartRepository)
            async with transaction():
                row = await repo.locked(chart_id)
                gallery = ChartGallery.model_validate_json(row.payload)
                for card in gallery.cards:
                    last = card.chart.candles[-1]
                    card.chart.candles = [
                        last.model_copy(
                            update={
                                "st_ts": last.st_ts - offset * 300,
                                "en_ts": last.en_ts - offset * 300,
                            }
                        )
                        for offset in reversed(range(144))
                    ]
                row.payload = gallery.model_dump_json()
                assert 65535 < len(row.payload.encode()) < 256 * 1024
                await repo.save(row)
        async with portal.request() as scope:
            row = await (await scope.get(PublicationChartRepository)).get(
                chart_id
            )
            restored = ChartGallery.model_validate_json(row.payload)
            assert [len(card.chart.candles) for card in restored.cards] == [
                144
            ] * 4

    portal.run(save_full_history())


def test_native_chart_image_cache_has_a_shared_storage_bound(portal):
    from src.modules.pricing.charts.interfaces import IChartImageCache

    async def cache_pages():
        async with portal.request() as scope:
            cache = await scope.get(IChartImageCache)
            for index in range(65):
                await cache.put(
                    str(index), b"\x89PNG\r\n\x1a\n" + bytes([index])
                )
        async with portal.request() as scope:
            cache = await scope.get(IChartImageCache)
            assert await cache.get("0") is None
            assert await cache.get("1") is not None
            assert await cache.get("64") == b"\x89PNG\r\n\x1a\n\x40"

    portal.run(cache_pages())
