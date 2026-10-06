from datetime import timedelta
from decimal import Decimal

import pytest
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from papilio.infra.redis.client import RedisClient, resolve
from sqlalchemy import insert, select, update

from src.modules.automation.agents.domain.models import (
    AgentCheckpointModel,
    LLMRunModel,
)
from src.modules.automation.agents.infra.tables import (
    AgentCheckpointTable,
    AIBudgetTable,
    LLMRunTable,
)
from src.modules.automation.missions.domain.models import (
    MissionEventModel,
    MissionModel,
)
from src.modules.automation.missions.infra.tables import (
    MissionEventTable,
    MissionTable,
)
from src.modules.content.drafts.domain.models import (
    DraftEvidenceModel,
    DraftModel,
)
from src.modules.content.drafts.infra.tables import (
    DraftEvidenceTable,
    DraftTable,
)
from src.modules.content.news.domain.models import ArticleModel
from src.modules.content.news.infra.tables import ArticleTable
from src.modules.content.publications.domain.models import (
    PublicationChartModel,
    PublicationModel,
)
from src.modules.content.publications.infra.tables import (
    PublicationChartTable,
    PublicationTable,
)
from src.modules.content.replies.domain.models import PrivateReplyModel
from src.modules.content.replies.infra.tables import PrivateReplyTable
from src.modules.ops.retention.app import maintenance
from src.modules.ops.retention.app.maintenance import BotHistoryMaintenance
from src.modules.ops.retention.infra.history import (
    HISTORY_TABLES,
    BotHistoryStore,
)
from src.modules.pricing.assets.infra.tables import AssetTable
from src.modules.pricing.calculator.domain.models import AssetPriceModel
from src.modules.pricing.calculator.infra.cache import AssetPriceCache
from src.modules.pricing.reports.domain.models import MarketSnapshotModel
from src.modules.pricing.reports.infra.tables import MarketSnapshotTable
from src.shared.dates import utc_now
from tests.integration.conftest import OWNER

pytestmark = pytest.mark.integration


async def seed_group(uow, identity, clock, child_clock, asset_id):
    async def add(table, model):
        await uow.execute(insert(table).values(**model.model_dump()))

    common = {"id": identity, "created_at": clock, "updated_at": clock}
    child = {**common, "created_at": child_clock, "updated_at": child_clock}
    await add(
        MissionTable,
        MissionModel(
            **common,
            owner_id=OWNER,
            origin_chat_id=OWNER,
            origin_bot="rick",
            origin_message_id=identity,
            bot_id=140001,
            update_id=identity,
            actor="rick",
            intent="news",
            text="fixture",
            status="failed",
            deadline=clock + timedelta(minutes=5),
        ),
    )
    await add(
        MarketSnapshotTable,
        MarketSnapshotModel(
            **child,
            mission_id=identity,
            owner_id=OWNER,
            payload="{}",
            body_hash="fixture",
        ),
    )
    await add(
        DraftTable,
        DraftModel(
            **child,
            owner_id=OWNER,
            origin_bot="rick",
            mission_id=identity,
            idempotency_key=f"fixture-{identity}",
            category="news",
            title="fixture",
            text="fixture",
            publisher_bot="rick",
            market_snapshot_id=identity,
        ),
    )
    await add(
        ArticleTable,
        ArticleModel(
            **child,
            mission_id=identity,
            source_id="fixture",
            url_hash="fixture",
            content_hash="fixture",
            url="https://example.com/article",
            title="fixture",
            fetched_at=child_clock,
            body="fixture",
        ),
    )
    await add(
        DraftEvidenceTable,
        DraftEvidenceModel(
            **child,
            draft_id=identity,
            article_id=identity,
        ),
    )
    await add(
        PublicationTable,
        PublicationModel(
            **child,
            owner_id=OWNER,
            draft_id=identity,
            revision=1,
            key=f"fixture-{identity}",
            bot_role="rick",
            channel_id=-100140001,
            scheduled_at=child_clock,
            deadline=child_clock + timedelta(minutes=5),
        ),
    )
    await add(
        PublicationChartTable,
        PublicationChartModel(
            **child,
            publication_id=identity,
            asset_id=asset_id,
            owner_id=OWNER,
            payload="{}",
            scheduled_at=child_clock,
            deadline=child_clock + timedelta(minutes=5),
        ),
    )
    await add(
        PrivateReplyTable,
        PrivateReplyModel(
            **child,
            mission_id=identity,
            owner_id=OWNER,
            origin_bot="rick",
            text="fixture",
            draft_id=identity,
            scheduled_at=child_clock,
        ),
    )
    await add(
        LLMRunTable,
        LLMRunModel(
            **child,
            mission_id=identity,
            request_no=1,
            budget_day=clock.date(),
            reserved_usd=Decimal("0"),
            status="completed",
        ),
    )
    await add(
        MissionEventTable,
        MissionEventModel(
            **child,
            mission_id=identity,
            event="fixture",
            detail="fixture",
        ),
    )
    await add(
        AgentCheckpointTable,
        AgentCheckpointModel(
            mission_id=identity,
            history="[]",
        ),
    )


def test_24_hour_history_cleanup_preserves_seeds_and_recent_dependencies(
    portal, monkeypatch
):
    now = utc_now().replace(microsecond=0)
    monkeypatch.setattr(maintenance, "utc_now", lambda: now)

    async def workflow():
        snapshot_before = (await portal.snapshot()).model_dump(mode="json")
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            assets = (await uow.execute(select(AssetTable))).scalars().all()
            asset_ids = [asset.id for asset in assets]
            async with transaction():
                # Old seed records must never become cleanup candidates.
                await uow.execute(
                    update(AssetTable).values(
                        created_at=now - timedelta(days=5)
                    )
                )
                for identity, age in ((101, 86401), (102, 86400), (103, 1)):
                    clock = now - timedelta(seconds=age)
                    await seed_group(
                        uow,
                        identity,
                        clock,
                        now if identity == 101 else clock,
                        asset_ids[0],
                    )
                await uow.execute(
                    insert(AIBudgetTable).values(
                        day=(now - timedelta(days=1)).date(),
                        reserved_usd=Decimal("1"),
                    )
                )
                await uow.execute(
                    insert(AIBudgetTable).values(
                        day=now.date(), reserved_usd=Decimal("2")
                    )
                )
            store = await scope.get(BotHistoryStore)
            with pytest.raises(ValueError):
                await store.prune_batch(AssetTable, now, 100)
            result = await (await scope.get(BotHistoryMaintenance)).clean(
                batch_size=1
            )
            assert result["removed_rows"]["tbl_missions"] == 1
            for table in HISTORY_TABLES:
                rows = (await uow.execute(select(table.id))).scalars().all()
                assert sorted(rows) == [102, 103], table.__tablename__
            checkpoints = (
                (await uow.execute(select(AgentCheckpointTable.mission_id)))
                .scalars()
                .all()
            )
            assert sorted(checkpoints) == [102, 103]
            budgets = (
                (await uow.execute(select(AIBudgetTable))).scalars().all()
            )
            assert len(budgets) == 1 and budgets[0].day == now.date()
            assert budgets[0].reserved_usd == Decimal("2")
            assert (
                await uow.execute(select(AssetTable.id))
            ).scalars().all() == asset_ids
            assert not any(
                (await store.expired_counts(now - timedelta(days=1))).values()
            )
        assert (await portal.snapshot()).model_dump(
            mode="json"
        ) == snapshot_before

    portal.run(workflow())


def test_quote_cache_expires_fields_independently_and_cleans_legacy_values(
    portal,
):
    async def workflow():
        async with portal.request() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            assets = (await uow.execute(select(AssetTable))).scalars().all()
            redis = await scope.get(RedisClient)
            cache = await scope.get(AssetPriceCache)
            now = utc_now()

            def quote(asset, clock):
                return AssetPriceModel(
                    asset_id=asset.id,
                    price=120,
                    buy_price=120,
                    sell_price=120,
                    buy_spread=0,
                    sell_spread=0,
                    buy_spread_rate=0,
                    sell_spread_rate=0,
                    priced_at=clock,
                )

            expired = quote(assets[0], now - timedelta(hours=25))
            recent = quote(assets[1], now)
            await cache.set_many(
                {assets[0].code: expired, assets[1].code: recent}
            )
            assert await cache.get(assets[0].code) is None
            assert await cache.get(assets[1].code) == recent
            # Upgrade previously persisted fields that have no expiry.
            await resolve(
                redis.client.hset(
                    cache.namespace, assets[0].code, expired.model_dump_json()
                )
            )
            result = await (await scope.get(BotHistoryMaintenance)).clean()
            assert result["removed_cache_fields"] == 1
            assert await cache.get(assets[0].code) is None
            assert await cache.get(assets[1].code) == recent
            ttl = await resolve(
                redis.client.httl(cache.namespace, assets[1].code)
            )
            assert 0 < ttl[0] <= 86400

    portal.run(workflow())
