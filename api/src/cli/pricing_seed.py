import json
from pathlib import Path

from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import inspect
from sqlmodel import select

from src.modules.ops.guards.infra.mysql import PortalGuardRepository
from src.modules.pricing.assets.domain.models import (
    AssetConfigModel,
    AssetModel,
    AssetSwitchModel,
)
from src.modules.pricing.assets.infra.mysql import (
    AssetConfigRepository,
    AssetRepository,
    AssetSwitchRepository,
)
from src.modules.pricing.assets.infra.tables import (
    AssetConfigTable,
    AssetSwitchTable,
)
from src.modules.pricing.bubbles.domain.models import (
    BubbleConfigModel,
    BubbleModel,
)
from src.modules.pricing.bubbles.infra.mysql import (
    BubbleConfigRepository,
    BubbleRepository,
)
from src.modules.pricing.bubbles.infra.tables import (
    BubbleConfigTable,
)
from src.modules.pricing.sources.domain.models import (
    SourceConfigModel,
    SourceModel,
)
from src.modules.pricing.sources.infra.mysql import (
    SourceConfigRepository,
    SourceRepository,
)
from src.modules.pricing.sources.infra.tables import (
    SourceConfigTable,
)
from src.modules.pricing.symbols.domain.models import SymbolModel
from src.modules.pricing.symbols.infra.mysql import SymbolRepository


async def insert_new(repo, rows, existing_keys, field: str) -> None:
    pending = [row for row in rows if getattr(row, field) not in existing_keys]
    if pending:
        await repo.bulk_insert(
            pending,
            insert_columns={
                name: inspect(repo.table).columns[name]
                for name in pending[0].to_row()
            },
        )


async def seed_pricing(uow: MySQLUnitOfWork, path: Path) -> None:
    data = json.loads(path.read_text())
    defaults = data["defaults"]
    async with transaction():
        await PortalGuardRepository(uow).lock("pricing:seed")
        assets_repo = AssetRepository(uow)
        assets = await assets_repo.get_all()
        await insert_new(
            assets_repo,
            [
                AssetModel(
                    **{k: v for k, v in item.items() if k != "switches"}
                )
                for item in data["assets"]
            ],
            {row.code for row in assets},
            "code",
        )
        assets = await assets_repo.get_all()
        by_asset = {row.code: row.id for row in assets}
        result = await uow.execute(select(AssetConfigTable))
        await insert_new(
            AssetConfigRepository(uow),
            [
                AssetConfigModel(
                    asset_id=row.id,
                    scheduler_on=False,
                    scheduler_seconds=defaults["usd_interval"]
                    if row.code == "usd"
                    else defaults["asset_interval"],
                    agg_type=defaults["aggregation"],
                )
                for row in assets
            ],
            {row.asset_id for row in result.scalars().all()},
            "asset_id",
        )
        result = await uow.execute(select(AssetSwitchTable))
        switches = result.scalars().all()
        missing = [
            AssetSwitchModel(asset_id=by_asset[item["code"]], **switch)
            for item in data["assets"]
            for switch in item["switches"]
            if (by_asset[item["code"]], switch["switch"])
            not in {(row.asset_id, row.switch) for row in switches}
        ]
        if missing:
            await AssetSwitchRepository(uow).bulk_insert(
                missing,
                insert_columns={
                    name: inspect(AssetSwitchTable).columns[name]
                    for name in missing[0].to_row()
                },
            )
        sources_repo = SourceRepository(uow)
        sources = await sources_repo.get_all()
        await insert_new(
            sources_repo,
            [
                SourceModel(
                    title=item["title"],
                    code=item["code"],
                    website_url=item["website_url"],
                    icon_url=item["website_url"] + "/favicon.ico",
                    primary_color=item["primary_color"],
                    source_type=item["switch"],
                    update_type=item["update_type"],
                    is_active=item["active"],
                )
                for item in data["sources"]
            ],
            {row.code for row in sources},
            "code",
        )
        sources = await sources_repo.get_all()
        by_source = {row.code: row.id for row in sources}
        result = await uow.execute(select(SourceConfigTable))
        await insert_new(
            SourceConfigRepository(uow),
            [
                SourceConfigModel(
                    source_id=by_source[item["code"]],
                    timeout=defaults["source_timeout"],
                    fetchers=item["fetchers"],
                    login=item["login"],
                )
                for item in data["sources"]
            ],
            {row.source_id for row in result.scalars().all()},
            "source_id",
        )
        symbols_repo = SymbolRepository(uow)
        symbols = await symbols_repo.get_all()
        await insert_new(
            symbols_repo,
            [
                SymbolModel(
                    asset_id=by_asset[item["asset"]],
                    **{k: v for k, v in item.items() if k != "asset"},
                )
                for item in data["symbols"]
            ],
            {row.code for row in symbols},
            "code",
        )
        bubbles_repo = BubbleRepository(uow)
        bubbles = await bubbles_repo.get_all()
        await insert_new(
            bubbles_repo,
            [BubbleModel(**item) for item in data["bubbles"]],
            {row.code for row in bubbles},
            "code",
        )
        bubbles = await bubbles_repo.get_all()
        result = await uow.execute(select(BubbleConfigTable))
        await insert_new(
            BubbleConfigRepository(uow),
            [
                BubbleConfigModel(
                    bubble_id=row.id,
                    scheduler_on=False,
                    scheduler_seconds=defaults["asset_interval"],
                    agg_type=defaults["aggregation"],
                )
                for row in bubbles
            ],
            {row.bubble_id for row in result.scalars().all()},
            "bubble_id",
        )
