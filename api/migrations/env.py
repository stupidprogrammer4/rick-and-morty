import asyncio
import os

from alembic import context
from dotenv import load_dotenv
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import get_settings
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from src.config.settings import PortalAppSettings

load_dotenv(os.getenv("PORTAL_ENV_FILE", ".env"))
settings = get_settings(PortalAppSettings)
Bootstrapper(settings.app.modules).boot_sqlmodels()
target_metadata = SQLModel.metadata
if settings.db is None:
    raise RuntimeError("MySQL settings required")
url = context.config.get_main_option("sqlalchemy.url") or settings.db.dsn


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := context.config.attributes.get("connection")) is not None:
    run_migrations(connection)
else:
    asyncio.run(run_online())
