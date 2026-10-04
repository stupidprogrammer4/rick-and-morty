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


def external_media(tmp_path):
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

    class Source(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            playlist = (
                b"<html><head><title>Owned audio playlist</title></head>"
                b'<body><audio controls src="/one.mp3"></audio>'
                b'<audio controls src="/two.mp3"></audio></body></html>'
            )
            browser = (
                b"<html><head><title>Dynamic audio page</title></head>"
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
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html" if self.path.endswith(".html") else "audio/mpeg",
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
                [x509.DNSName("media.portal-test.example")]
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
    # Redirect only the controlled external hostname; native DB/Redis are real.
    (boundary / "sitecustomize.py").write_text(f"""
import socket, ssl
resolve = socket.getaddrinfo
connect = socket.socket.connect
load = ssl.SSLContext.load_verify_locations
def external_resolve(host, port, *args, **kwargs):
    if host == "media.portal-test.example":
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
