import asyncio
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from src.shared.dates import utc_now

pytestmark = pytest.mark.integration


async def populate(client, stream):
    pipe = client.pipeline()
    for position in range(1, 5):
        pipe.xadd(stream, {"data": "retention fixture"}, id=f"{position}-0")
    pipe.xadd(stream, {"data": "recent fixture"})
    await pipe.execute()
    await client.xgroup_create(stream, "first", id="0-0")
    await client.xgroup_create(stream, "second", id="0-0")
    await client.xreadgroup("first", "fixture", {stream: ">"}, count=5)
    await client.xack(stream, "first", "1-0", "3-0")
    await client.xreadgroup("second", "fixture", {stream: ">"}, count=2)
    await client.xack(stream, "second", "1-0")
    await client.xadd(stream, {"data": "recent unread fixture"})


def test_retention_expires_old_pending_and_preserves_recent_work(portal):
    from src.modules.ops.queues.interfaces import ITaskHistoryMaintenance

    async def workflow():
        client = Redis.from_url(portal.settings.tasks.url)
        streams = (portal.settings.tasks.queue_name,)
        try:
            await asyncio.gather(
                *(populate(client, stream) for stream in streams)
            )
            async with portal.request() as scope:
                maintenance = await scope.get(ITaskHistoryMaintenance)
                removed = await maintenance.clean()
            assert removed == 4
            rows = await asyncio.gather(
                *(client.xrange(stream) for stream in streams)
            )
            assert all(
                len(entries) == 2
                and all(int(row[0].split(b"-")[0]) > 4 for row in entries)
                for entries in rows
            )
            groups = await asyncio.gather(
                *(client.xinfo_groups(stream) for stream in streams)
            )
            assert all(
                {group["name"]: group["pending"] for group in stream}
                == {b"first": 1, b"second": 0}
                for stream in groups
            )
        finally:
            await client.aclose()

    portal.run(workflow())


def test_native_scheduler_prunes_acknowledged_history_through_worker(portal):
    async def prepare():
        from src.apps.scheduler import app

        client = Redis.from_url(portal.settings.tasks.url)
        stream = portal.settings.tasks.queue_name
        group = portal.settings.tasks.consumer_group
        try:
            await client.xadd(stream, {"data": "completed fixture"}, id="1-0")
            await client.xgroup_create(stream, group, id="0-0")
            await client.xreadgroup(group, "fixture", {stream: ">"}, count=1)
            await client.xack(stream, group, "1-0")
            await app.connect()
            task = app.broker.find_task(
                "src.modules.ops.tasks.schedulers.maintenance.PruneTaskHistory"
            )
            assert task is not None
            await task.schedule_by_time(
                app.source.native, utc_now() + timedelta(seconds=2)
            )
        finally:
            await client.aclose()

    portal.run(prepare())
    portal.start_workers()

    async def remaining():
        client = Redis.from_url(portal.settings.tasks.url)
        try:
            rows = await client.xrange(
                portal.settings.tasks.queue_name, "1-0", "1-0"
            )
            return len(rows)
        finally:
            await client.aclose()

    assert portal.until(remaining, lambda count: count == 0) == 0
