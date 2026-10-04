import json
import os
import ssl
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from sqlalchemy import text

from portal_contracts.media import MediaCreate
from src.modules.media.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.interfaces import (
    IMediaCommands,
    IMediaItemService,
    IMediaJobService,
    IMediaMaintenance,
    IMediaQueries,
)
from tests.integration.conftest import ExternalTelegramHandler

pytestmark = pytest.mark.integration
USER = 140099


def test_media_migration_preserves_populated_previous_schema(portal):
    config = Config("api/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        portal.environment["PORTAL_DATABASE_URL"].replace("%", "%%"),
    )
    command.downgrade(config, "20261003_chart_precision")

    async def records():
        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            async with transaction():
                values = await unit.execute(
                    text("SELECT * FROM tbl_setting_values ORDER BY id")
                )
                sources = await unit.execute(
                    text("SELECT * FROM tbl_news_sources ORDER BY id")
                )
                return list(values), list(sources)

    before = portal.run(records())
    assert before[0] and before[1]
    command.upgrade(config, "head")
    command.check(config)
    assert portal.run(records()) == before


def test_parallel_migration_preserves_recorded_items_and_active_leases(portal):
    config = Config("api/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        portal.environment["PORTAL_DATABASE_URL"].replace("%", "%%"),
    )
    command.downgrade(config, "20261004_media")

    async def seed():
        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            async with transaction():
                await unit.execute(
                    text("""INSERT INTO tbl_media_jobs
                    (id,owner_id,chat_id,bot_id,update_id,url,mode,provider,
                    status,total,sent,failed,lease_until)
                    VALUES (801,:user,:user,140003,801,:url,'audio','video',
                    'completed',1,1,0,NULL),
                    (802,:user,:user,140003,802,:url,'audio','video',
                    'running',1,0,0,'2026-10-05 00:00:00')"""),
                    {"user": USER, "url": "https://example.com/track.mp3"},
                )
                payload = DownloadItem(
                    url="https://example.com/track.mp3",
                    source_url="https://example.com/track.mp3",
                ).model_dump_json()
                await unit.execute(
                    text("""INSERT INTO tbl_media_items
                    (id,job_id,position,title,payload,source_url,status,message_id)
                    VALUES (801,801,1,'Recorded track',:payload,
                    :url,'sent',8700), (802,802,1,'Interrupted track',
                    :payload,:url,'sending',NULL)
                    """),
                    {
                        "payload": payload,
                        "url": "https://example.com/track.mp3",
                    },
                )
            result = await unit.execute(
                text(
                    "SELECT id,job_id,position,title,payload,source_url,"
                    "status,message_id FROM tbl_media_items ORDER BY id"
                )
            )
            return list(result)

    before = portal.run(seed())
    command.upgrade(config, "head")
    command.check(config)

    async def verify():
        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            result = await unit.execute(
                text(
                    "SELECT id,job_id,position,title,payload,source_url,"
                    "status,message_id FROM tbl_media_items ORDER BY id"
                )
            )
            assert list(result) == before
            items = await request.get(IMediaItemService)
            sent = await items.get(801)
            active = await items.get(802)
            assert sent.message_id == 8700 and sent.lease_until is None
            assert (
                active.status == "sending"
                and active.lease_until == datetime(2026, 10, 5)
            )
            assert active.downloaded_payload is None

    portal.run(verify())


def test_prepared_audio_retries_rate_limit_without_downloading_again(
    portal, tmp_path
):
    server, _ = external_media(tmp_path)
    try:

        async def prepare():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=9,
                        url="https://example.com/track.mp3",
                        mode="audio",
                    )
                )
                jobs = await request.get(IMediaJobService)
                items = await request.get(IMediaItemService)
                async with transaction():
                    await items.create_many(
                        result.job.id,
                        DownloadPlan(
                            items=[
                                DownloadItem(
                                    url="https://example.com/track.mp3",
                                    source_url="https://example.com/track.mp3",
                                    engine="direct",
                                    kind="audio",
                                )
                            ]
                        ),
                    )
                    item = await items.next(result.job.id)
                    assert item is not None
                    downloaded = DownloadedFile(
                        filename="0" * 32 + ".mp3",
                        kind="audio",
                        title="Prepared audio",
                        source_url="https://example.com/track.mp3",
                    )
                    directory = (
                        Path(portal.settings.media.directory)
                        / str(result.job.id)
                        / str(item.id)
                    )
                    directory.mkdir(parents=True)
                    (directory / downloaded.filename).write_bytes(
                        (tmp_path / "sample.mp3").read_bytes()
                    )
                    await items.change(
                        item.id,
                        MediaItemChange(
                            status="ready",
                            filename=downloaded.filename,
                            downloaded_payload=downloaded.model_dump_json(),
                        ),
                    )
                    await jobs.change(
                        result.job.id,
                        MediaJobChange(status="running", total=1),
                    )
                return result.job.id, directory / downloaded.filename

        id, file = portal.run(prepare())
        ExternalTelegramHandler.media_delivery_status = "rate_limited"
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
                return result

        portal.until(
            read,
            lambda job: (
                len(ExternalTelegramHandler.media_files) == 1
                and job.status == "running"
            ),
            timeout=20,
        )
        assert file.is_file()
        ExternalTelegramHandler.media_delivery_status = "sent"
        result = portal.until(
            read,
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=20,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            1,
            0,
        )
        assert len(ExternalTelegramHandler.media_files) == 2
        assert {
            record["filename"]
            for record in ExternalTelegramHandler.media_files
        } == {file.name}
        assert not file.parent.parent.exists()
    finally:
        server.shutdown()
        server.server_close()


def external_media(tmp_path, slow_release=None):
    audio = tmp_path / "sample.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-threads",
            "1",
            str(audio),
        ],
        check=True,
    )
    data = audio.read_bytes()
    mp4 = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio),
            "-threads",
            "1",
            str(mp4),
        ],
        check=True,
    )
    ogg = tmp_path / "sample.ogg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio),
            "-threads",
            "1",
            str(ogg),
        ],
        check=True,
    )
    arrivals = set()
    arrived = threading.Event()
    arrival_lock = threading.Lock()

    class Source(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/instagram-query":
                result = {
                    "data": {
                        "xig_polaris_media": {
                            "if_not_gated_logged_out": {
                                "caption": {"text": "Owned slides"},
                                "carousel_media_count": 2,
                                "carousel_media": [
                                    {
                                        "image_versions2": {
                                            "candidates": [
                                                {
                                                    "url": "https://media.portal-test.example/cover.png",
                                                    "width": 128,
                                                    "height": 128,
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "image_versions2": {
                                            "candidates": [
                                                {
                                                    "url": "https://media.portal-test.example/cover.png",
                                                    "width": 128,
                                                    "height": 128,
                                                }
                                            ]
                                        }
                                    },
                                ],
                            }
                        }
                    }
                }
                value = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(value)))
                self.end_headers()
                self.wfile.write(value)
            else:
                self.send_error(404)

        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            if body and self.path == "/slow.mp3" and slow_release is not None:
                slow_release.wait(15)
            if body and self.path in {"/parallel-1.mp3", "/parallel-2.mp3"}:
                with arrival_lock:
                    arrivals.add(self.path)
                    if len(arrivals) == 2:
                        arrived.set()
                if not arrived.wait(8):
                    self.send_error(503, "Downloads did not overlap")
                    return
            playlist = (
                b"<html><head><title>Owned audio playlist</title></head>"
                b'<body><audio controls src="/one.mp3"></audio>'
                b'<audio controls src="/two.mp3"></audio></body></html>'
            )
            browser = (
                b"<html><head><title>Dynamic audio page</title>"
                b'<meta property="og:image" '
                b'content="https://media.portal-test.example/cover.png">'
                b"</head>"
                b"<body><script>const audio = document.createElement('audio');"
                b"audio.src = 'https://media.portal-test.example/one.mp3';"
                b"document.body.appendChild(audio);</script></body></html>"
            )
            value = (
                playlist
                if self.path == "/playlist.html"
                else browser
                if self.path == "/browser.html"
                else data
            )
            if self.path.startswith("/p/"):
                value = (
                    b'<html><script>["LSD",[],'
                    b'{"token":"owned-fixture"}]</script></html>'
                )
            if self.path.startswith("/pinterest-api"):
                value = json.dumps(
                    {
                        "resource_response": {
                            "data": {
                                "id": "12345",
                                "title": "Owned pin",
                                "images": {
                                    "orig": {
                                        "url": "https://media.portal-test.example/cover.png"
                                    }
                                },
                            }
                        }
                    }
                ).encode()
            if self.path == "/pin/54321/":
                pin = {
                    "entityId": "54321",
                    "title": "Owned slide pin",
                    "storyPinData": {
                        "pages": [
                            {
                                "blocks": [
                                    {
                                        "__typename": "StoryPinImageBlock",
                                        "images_750x": {
                                            "url": "https://media.portal-test.example/cover.png",
                                            "width": 750,
                                            "height": 750,
                                        },
                                    }
                                ],
                            }
                            for _ in range(3)
                        ],
                    },
                }
                payload = {"data": {"v3GetPinQueryv2": {"data": pin}}}
                value = (
                    "<script>window.__PWS_RELAY_REGISTER_COMPLETED_REQUEST__("
                    '"owned-request", ' + json.dumps(payload) + ");</script>"
                ).encode()
            if self.path == "/cover.png":
                value = Path(
                    "bots/portal_bots/media/assets/avatar.png"
                ).read_bytes()
            if self.path == "/direct.ogg":
                value = ogg.read_bytes()
            if self.path == "/direct.mp4":
                value = mp4.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html"
                if self.path.endswith(".html")
                else "image/png"
                if self.path == "/cover.png"
                else "application/ogg"
                if self.path == "/direct.ogg"
                else "video/mp4"
                if self.path == "/direct.mp4"
                else "audio/mpeg",
            )
            self.send_header("Content-Length", str(len(value)))
            self.end_headers()
            if body:
                self.wfile.write(value)

        def log_message(self, *args):
            pass

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "media.portal-test.example")]
    )
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("media.portal-test.example"),
                    x509.DNSName("www.instagram.com"),
                    x509.DNSName("www.pinterest.com"),
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    cert = tmp_path / "external-ca.pem"
    secret = tmp_path / "external-key.pem"
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    secret.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Source)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, secret)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    boundary = tmp_path / "external-network"
    boundary.mkdir()
    hosts = (
        "media.portal-test.example",
        "www.instagram.com",
        "www.pinterest.com",
    )
    # Redirect only the controlled external hostname; native DB/Redis are real.
    (boundary / "sitecustomize.py").write_text(f"""
import socket, ssl
resolve = socket.getaddrinfo
connect = socket.socket.connect
load = ssl.SSLContext.load_verify_locations
def external_resolve(host, port, *args, **kwargs):
    if host in {hosts!r}:
        host = "1.1.1.1"
    return resolve(host, port, *args, **kwargs)
def external_connect(self, address):
    if isinstance(address, tuple) and address[:2] == ("1.1.1.1", 443):
        address = ("127.0.0.1", {server.server_port})
    return connect(self, address)
def external_trust(self, *args, **kwargs):
    result = load(self, *args, **kwargs)
    load(self, cafile={str(cert)!r})
    return result
socket.getaddrinfo = external_resolve
socket.socket.connect = external_connect
ssl.SSLContext.load_verify_locations = external_trust
""")
    return server, boundary


def test_first_ready_track_is_sent_while_later_download_is_pending(
    portal, tmp_path
):
    release = threading.Event()
    server, boundary = external_media(tmp_path, release)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def prepare():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=10,
                        url="https://media.portal-test.example/playlist.html",
                        mode="audio",
                    )
                )
                jobs = await request.get(IMediaJobService)
                items = await request.get(IMediaItemService)
                async with transaction():
                    await items.create_many(
                        result.job.id,
                        DownloadPlan(
                            items=[
                                DownloadItem(
                                    url="https://media.portal-test.example/"
                                    + file,
                                    source_url="https://media.portal-test.example/"
                                    + file,
                                    title=title,
                                    kind="audio",
                                    engine="direct",
                                )
                                for file, title in (
                                    ("fast.mp3", "First"),
                                    ("slow.mp3", "Second"),
                                )
                            ]
                        ),
                    )
                    await jobs.change(
                        result.job.id, MediaJobChange(status="queued", total=2)
                    )
                return result.job.id

        id = portal.run(prepare())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
                return result

        portal.until(
            read,
            lambda job: len(ExternalTelegramHandler.media_files) == 1,
            timeout=20,
        )
        assert ExternalTelegramHandler.media_files[0]["title"] == "First"
        release.set()
        result = portal.until(
            read,
            lambda job: job.status in {"completed", "failed", "partial"},
            timeout=20,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            2,
            0,
        )
        assert [
            file["title"] for file in ExternalTelegramHandler.media_files
        ] == ["First", "Second"]
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        release.set()
        server.shutdown()
        server.server_close()


def test_six_tracks_download_concurrently_and_clean_separate_workspaces(
    portal, tmp_path
):
    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def prepare():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=7,
                        url="https://media.portal-test.example/playlist.html",
                        mode="audio",
                    )
                )
                jobs = await request.get(IMediaJobService)
                items = await request.get(IMediaItemService)
                async with transaction():
                    await items.create_many(
                        result.job.id,
                        DownloadPlan(
                            items=[
                                DownloadItem(
                                    url=f"https://media.portal-test.example/parallel-{n}.mp3",
                                    source_url=f"https://media.portal-test.example/parallel-{n}.mp3",
                                    title=f"Track {n}",
                                    engine="direct",
                                    kind="audio",
                                )
                                for n in range(1, 7)
                            ]
                        ),
                    )
                    await jobs.change(
                        result.job.id, MediaJobChange(status="queued", total=6)
                    )
                return result.job.id

        id = portal.run(prepare())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"completed", "failed", "partial"},
            timeout=90,
        )
        assert (result.status, result.total, result.sent, result.failed) == (
            "completed",
            6,
            6,
            0,
        )
        assert len(ExternalTelegramHandler.media_files) == 6
        assert [
            file["title"] for file in ExternalTelegramHandler.media_files
        ] == [f"Track {n}" for n in range(1, 7)]
        assert (
            len(
                {
                    file["item_id"]
                    for file in ExternalTelegramHandler.media_files
                }
            )
            == 6
        )
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    ("name", "mode"), [("direct.ogg", "media"), ("direct.mp4", "audio")]
)
def test_direct_media_is_normalized_for_telegram_audio(
    portal, tmp_path, name, mode
):
    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=8,
                        url="https://media.portal-test.example/" + name,
                        mode=mode,
                    )
                )
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"completed", "failed", "partial"},
            timeout=90,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            1,
            0,
        )
        delivered = ExternalTelegramHandler.media_files[0]
        assert delivered["kind"] == "audio" and delivered["filename"].endswith(
            ".mp3"
        )
    finally:
        server.shutdown()
        server.server_close()


def test_public_playlist_runs_native_worker_and_cleans_files(portal, tmp_path):
    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                data = MediaCreate(
                    owner_id=USER,
                    chat_id=USER,
                    bot_id=140003,
                    update_id=1,
                    url="https://media.portal-test.example/playlist.html",
                    mode="audio",
                )
                result = await commands.accept(data)
                replay = await commands.accept(data)
                assert replay.duplicate and replay.job.id == result.job.id
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
            return result

        result = portal.until(
            read,
            lambda job: job.status in {"completed", "failed", "partial"},
            timeout=90,
        )
        assert result.status == "completed", result.error
        assert (result.total, result.sent, result.failed) == (2, 2, 0)
        assert len(ExternalTelegramHandler.media_files) == 2
        assert all(
            item["kind"] == "audio"
            for item in ExternalTelegramHandler.media_files
        )
        assert all(
            item["owner_id"] == USER
            for item in ExternalTelegramHandler.media_files
        )
        assert not (Path(portal.settings.media.directory) / str(id)).exists()

        async def page():
            async with portal.request() as request:
                queries = await request.get(IMediaQueries)
                result = await queries.items(id, USER, 1, 1)
                denied = await queries.page(USER + 1, 1, 5)
                assert denied.total == 0
                return result

        items = portal.run(page())
        assert items.total == 2 and len(items.items) == 1
        assert items.items[0].message_id is not None
    finally:
        server.shutdown()
        server.server_close()


def test_admission_cancel_ownership(portal):
    async def scenario():
        async with portal.request() as request:
            commands = await request.get(IMediaCommands)
            result = await commands.accept(
                MediaCreate(
                    owner_id=USER,
                    chat_id=USER,
                    bot_id=140003,
                    update_id=2,
                    url="https://example.com/file.mp3",
                )
            )
            with pytest.raises(NotFoundException):
                await commands.cancel(result.job.id, USER + 1)
            cancelled = await commands.cancel(result.job.id, USER)
            assert cancelled.status == "cancelled"
        async with portal.request() as request:
            queries = await request.get(IMediaQueries)
            result = await queries.page(USER, 1, 5)
            assert result.total == 1 and result.items[0].status == "cancelled"

    portal.run(scenario())


def test_cleaner_removes_only_aged_inactive_owned_directories(portal):
    async def scenario():
        async with portal.request() as request:
            commands = await request.get(IMediaCommands)
            jobs = await request.get(IMediaJobService)
            result = await commands.accept(
                MediaCreate(
                    owner_id=USER,
                    chat_id=USER,
                    bot_id=140003,
                    update_id=5,
                    url="https://example.com/track.mp3",
                )
            )
            async with transaction():
                await jobs.change(
                    result.job.id,
                    MediaJobChange(
                        status="running",
                        lease_until=datetime.now(UTC) + timedelta(minutes=10),
                    ),
                )
        root = Path(portal.settings.media.directory)
        active = root / str(result.job.id)
        aged = root / "90001"
        recent = root / "90002"
        unrelated = root / "other-app"
        for directory in (active, aged, recent, unrelated):
            directory.mkdir(parents=True)
            (directory / "sample.mp3").write_bytes(b"owned media")
        for directory in (active, aged, unrelated):
            timestamp = time.time() - 7200
            os.utime(directory / "sample.mp3", (timestamp, timestamp))
            os.utime(directory, (timestamp, timestamp))
        async with portal.request() as request:
            maintenance = await request.get(IMediaMaintenance)
            await maintenance.clean()
        assert not aged.exists()
        assert active.exists() and recent.exists() and unrelated.exists()

    portal.run(scenario())


def test_dynamic_browser_page_runs_native_worker_and_sends_audio(
    portal, tmp_path
):
    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    if Path("/usr/bin/google-chrome").exists():
        portal.environment["PORTAL_BROWSER_EXECUTABLE"] = (
            "/usr/bin/google-chrome"
        )
    try:

        async def accept():
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=6,
                        url="https://media.portal-test.example/browser.html",
                        mode="audio",
                    )
                )
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
            return result

        result = portal.until(
            read,
            lambda job: job.status in {"completed", "failed", "partial"},
            timeout=90,
        )
        assert result.status == "completed", result.error
        assert (result.total, result.sent, result.failed) == (1, 1, 0)
        assert ExternalTelegramHandler.media_files[0]["kind"] == "audio"
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


def test_recovery_never_replays_unknown_delivery(portal):
    async def prepare():
        async with portal.request() as request:
            commands = await request.get(IMediaCommands)
            result = await commands.accept(
                MediaCreate(
                    owner_id=USER,
                    chat_id=USER,
                    bot_id=140003,
                    update_id=3,
                    url="https://example.com/track.mp3",
                )
            )
            jobs = await request.get(IMediaJobService)
            items = await request.get(IMediaItemService)
            async with transaction():
                await items.create_many(
                    result.job.id,
                    DownloadPlan(
                        items=[
                            DownloadItem(
                                url="https://example.com/track.mp3",
                                source_url="https://example.com/track.mp3",
                            )
                        ]
                    ),
                )
                item = await items.next(result.job.id)
                assert item is not None
                await items.change(item.id, MediaItemChange(status="sending"))
                await jobs.change(
                    result.job.id,
                    MediaJobChange(
                        status="running",
                        total=1,
                        lease_until=datetime.now(UTC) - timedelta(seconds=10),
                    ),
                )
            return result.job.id

    id = portal.run(prepare())
    portal.start_workers("src.apps.media")

    async def read():
        async with portal.request() as request:
            queries = await request.get(IMediaQueries)
            result = await queries.items(id, USER, 1, 5)
        return result

    result = portal.until(
        read, lambda page: page.items[0].status == "unknown", timeout=40
    )
    assert result.items[0].message_id is None
    assert not ExternalTelegramHandler.media_files


@pytest.mark.parametrize(
    ("url", "provider", "count"),
    [
        ("https://www.pinterest.com/pin/12345/", "pinterest", 1),
        ("https://www.pinterest.com/pin/54321/", "pinterest", 3),
        ("https://www.instagram.com/p/ABC/", "instagram", 2),
    ],
)
def test_provider_http_metadata_download_delivery_and_cleanup(
    portal, tmp_path, url, provider, count
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            policy = MediaPolicy(
                pinterest_api_url="https://media.portal-test.example/pinterest-api",
                instagram_query_url="https://media.portal-test.example/instagram-query",
            )
            await portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                policy.model_dump(mode="json"),
            )
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                accepted = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=101,
                        url=url,
                    )
                )
                assert accepted.job.provider == provider
                return accepted.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                jobs = await request.get(IMediaJobService)
                result = await jobs.get(id, USER)
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=60,
        )
        assert (result.status, result.total, result.sent, result.failed) == (
            "completed",
            count,
            count,
            0,
        ), result.error
        assert len(ExternalTelegramHandler.media_files) == count
        assert all(
            f["kind"] == "photo" for f in ExternalTelegramHandler.media_files
        )
        assert not (Path(portal.settings.media.directory) / str(id)).exists()

        async def committed():
            async with portal.request() as request:
                items = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                assert [row.position for row in items.items] == list(
                    range(1, count + 1)
                )
                assert all(
                    row.status == "sent" and row.source_url == url
                    for row in items.items
                )
                messages = [row.message_id for row in items.items]
                assert messages == sorted(messages)

        portal.run(committed())
    finally:
        server.shutdown()
        server.server_close()
