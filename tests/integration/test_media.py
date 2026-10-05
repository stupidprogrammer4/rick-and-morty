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
from src.modules.media.downloads.domain.dtos import (
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.downloads.interfaces import (
    IMediaCommands,
    IMediaDelivery,
    IMediaItemService,
    IMediaJobService,
    IMediaMaintenance,
    IMediaQueries,
)
from src.modules.media.sources.domain.dtos import (
    DownloadedFile,
    DownloadItem,
    DownloadPlan,
)
from tests.integration.conftest import ExternalTelegramHandler

pytestmark = pytest.mark.integration
USER = 140099


def test_delivery_claim_uses_current_status_after_an_older_snapshot(portal):
    async def workflow():
        async with portal.request() as request:
            accepted = await (await request.get(IMediaCommands)).accept(
                MediaCreate(
                    owner_id=USER,
                    chat_id=USER,
                    bot_id=140003,
                    update_id=401,
                    url="https://example.com/track.mp3",
                    mode="audio",
                )
            )
            jobs = await request.get(IMediaJobService)
            items = await request.get(IMediaItemService)
            async with transaction():
                await items.create_many(
                    accepted.job.id,
                    DownloadPlan(
                        items=[
                            DownloadItem(
                                url="https://example.com/track.mp3",
                                source_url="https://example.com/track.mp3",
                                kind="audio",
                            )
                        ]
                    ),
                )
                item = await items.next(accepted.job.id)
                assert item is not None
                downloaded = DownloadedFile(
                    filename="0" * 32 + ".mp3",
                    kind="audio",
                    title="Already claimed",
                    source_url="https://example.com/track.mp3",
                )
                directory = (
                    Path(portal.settings.media.directory)
                    / str(accepted.job.id)
                    / str(item.id)
                )
                directory.mkdir(parents=True)
                (directory / downloaded.filename).write_bytes(
                    b"previously prepared media"
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
                    accepted.job.id, MediaJobChange(status="running", total=1)
                )
        async with portal.request() as stale:
            delivery = await stale.get(IMediaDelivery)
            reader = await stale.get(IMediaItemService)
            before = await reader.get(item.id)
            assert before.status == "ready"
            async with portal.request() as claimant:
                claim_items = await claimant.get(IMediaItemService)
                async with transaction():
                    await claim_items.change(
                        item.id,
                        MediaItemChange(
                            status="sending",
                            lease_until=datetime.now(UTC)
                            + timedelta(minutes=5),
                        ),
                    )
            await delivery.execute(accepted.job.id)
        async with portal.request() as fresh:
            current = await (await fresh.get(IMediaItemService)).get(item.id)
            assert current.status == "sending"
        assert not ExternalTelegramHandler.media_files

    portal.run(workflow())


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


def external_media(
    tmp_path,
    slow_release=None,
    audio_seconds=1,
    portrait=False,
    native_catalog=False,
    native_hls=False,
    native_hls_fault=None,
    native_spotify_api=None,
    native_youtube_api=False,
):
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
            f"sine=frequency=440:duration={audio_seconds}",
            "-threads",
            "1",
            *(["-write_xing", "0"] if native_hls else []),
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
    m4a = tmp_path / "sample.m4a"
    m4a.write_bytes(mp4.read_bytes())
    if native_catalog:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:r=25",
                "-i",
                str(audio),
                "-t",
                str(audio_seconds),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-threads",
                "1",
                "-c:a",
                "aac",
                *(
                    ["-movflags", "empty_moov+frag_keyframe+default_base_moof"]
                    if native_youtube_api
                    else []
                ),
                str(mp4),
            ],
            check=True,
        )
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
    if portrait:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=720x1280:r=25",
                "-i",
                str(audio),
                "-t",
                "1",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-threads",
                "1",
                "-c:a",
                "aac",
                "-hls_time",
                "1",
                "-hls_list_size",
                "0",
                "-hls_segment_filename",
                str(tmp_path / "portrait-%02d.ts"),
                "-f",
                "hls",
                str(tmp_path / "portrait-stream.m3u8"),
            ],
            check=True,
        )

    arrivals = set()
    arrived = threading.Event()
    arrival_lock = threading.Lock()

    class Source(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def send_json(self, payload):
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def track(self, identifier=1):
            return {
                "id": identifier,
                "title": "Native Song",
                "duration": 8000 if native_hls else 1000,
                "permalink_url": "https://soundcloud.com/native-artist/native-song",
                "uri": "https://api-v2.soundcloud.com/tracks/"
                + str(identifier),
                "user": {"username": "Native Artist", "id": 1},
                "media": {
                    "transcodings": [
                        {
                            "url": "https://api-v2.soundcloud.com/transcoding",
                            "preset": "mp3_0_1",
                            "format": {
                                "protocol": "hls"
                                if native_hls
                                else "progressive",
                                "mime_type": "audio/mpeg",
                            },
                        }
                    ]
                },
            }

        def do_POST(self):
            if native_youtube_api and self.path == "/cobalt":
                payload = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                )
                audio_mode = payload["downloadMode"] == "audio"
                self.send_json(
                    {
                        "status": "tunnel",
                        "url": "https://media.portal-test.example/tunnel-audio"
                        if audio_mode
                        else "https://media.portal-test.example/tunnel-video",
                        "filename": "Native Video.mp3"
                        if audio_mode
                        else "Native Video.mp4",
                    }
                )
                return
            if native_spotify_api and self.path == "/api/token":
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_json({"access_token": "external-test-access"})
                return
            if native_catalog and self.path == "/get_pot":
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_json({"poToken": "ZXh0ZXJuYWwtdGVzdC10b2tlbg=="})
                return
            if native_catalog and self.path.startswith("/youtubei/v1/next"):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_json({})
                return
            if native_catalog and self.path.startswith("/youtubei/v1/player"):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_json(
                    {
                        "playabilityStatus": {"status": "OK"},
                        "videoDetails": {
                            "videoId": "abc123DEF45",
                            "title": "Native Video",
                            "lengthSeconds": "1",
                            "author": "Native Artist",
                        },
                        "streamingData": {
                            "formats": [
                                {
                                    "itag": 18,
                                    "url": "https://media.portal-test.example/direct.mp4",
                                    "mimeType": (
                                        'video/mp4; codecs="avc1.42001E, '
                                        'mp4a.40.2"'
                                    ),
                                    "width": 640,
                                    "height": 360,
                                    "contentLength": str(mp4.stat().st_size),
                                }
                            ],
                            "adaptiveFormats": [
                                {
                                    "itag": 140,
                                    "url": "https://media.portal-test.example/direct.m4a",
                                    "mimeType": (
                                        'audio/mp4; codecs="mp4a.40.2"'
                                    ),
                                    "audioQuality": "AUDIO_QUALITY_MEDIUM",
                                    "audioSampleRate": "44100",
                                    "contentLength": str(m4a.stat().st_size),
                                }
                            ],
                        },
                    }
                )
                return
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
            if native_spotify_api and self.path.startswith("/v1/playlists/"):
                if (
                    self.headers.get("Authorization")
                    != "Bearer external-test-user-token"
                ):
                    self.send_error(403)
                    return
                if self.path == "/v1/playlists/NativePlaylist1":
                    self.send_json({"public": native_spotify_api != "private"})
                    return
                from urllib.parse import parse_qs, urlsplit

                offset = int(parse_qs(urlsplit(self.path).query)["offset"][0])
                rows = [
                    {
                        "item": {
                            "type": "track",
                            "id": "NativeTrack" + str(position),
                            "name": "Native Song",
                            "duration_ms": 1000,
                            "artists": [{"name": "Native Artist"}],
                            "track_number": position,
                            "album": {"name": "Native Album", "images": []},
                        }
                    }
                    for position in range(offset + 1, min(offset + 51, 52))
                ]
                if offset and native_spotify_api == "missing":
                    rows = []
                self.send_json(
                    {
                        "items": rows,
                        "limit": 50,
                        "total": 52
                        if offset and native_spotify_api == "changed"
                        else 51,
                    }
                )
                return
            if native_catalog:
                if self.path.startswith("/search/tracks"):
                    self.send_json(
                        {"collection": [self.track()], "next_href": None}
                    )
                    return
                if self.path.startswith(("/tracks/", "/resolve")):
                    self.send_json(self.track())
                    return
                if self.path.startswith("/transcoding"):
                    self.send_json(
                        {
                            "url": "https://media.portal-test.example/"
                            + ("native.m3u8" if native_hls else "direct.mp3")
                        }
                    )
                    return
                if self.path.startswith("/embed/track/"):
                    entity = {
                        "uri": "spotify:track:NativeTrack1",
                        "name": "Native Song",
                        "artists": [{"name": "Native Artist"}],
                        "duration": 8000 if native_hls else 1000,
                        "visualIdentity": {
                            "image": [
                                {
                                    "url": "https://media.portal-test.example/artwork.png"
                                }
                            ]
                        },
                    }
                    state = {
                        "props": {
                            "pageProps": {
                                "state": {"data": {"entity": entity}}
                            }
                        }
                    }
                    raw = (
                        '<html><script id="__NEXT_DATA__" '
                        'type="application/json">'
                        + json.dumps(state)
                        + "</script></html>"
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if (
                    self.path == "/"
                    and self.headers.get("Host") == "soundcloud.com"
                ):
                    raw = b'<html><script src="https://soundcloud.com/asset.js"></script></html>'
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if self.path == "/asset.js":
                    raw = b'client_id:"abcdefghijklmnopqrstuvwxyz123456"'
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
            if body and self.path == "/slow.mp3" and slow_release is not None:
                slow_release.wait(15)
            if body and self.path in {
                "/parallel-1.mp3",
                "/parallel-2.mp3",
                "/native-1.mp3",
                "/native-2.mp3",
            }:
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
            if self.path == "/artwork.png":
                import base64

                value = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
                    "/x8AAwMCAO+aB9sAAAAASUVORK5CYII="
                )
            if self.path == "/native.m3u8":
                value = (
                    b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n"
                    b"native-1.mp3\n#EXTINF:4,\nnative-2.mp3\n"
                    b"#EXT-X-ENDLIST\n"
                )
                if native_hls_fault == "private":
                    value = value.replace(
                        b"native-1.mp3", b"https://127.0.0.1/private.mp3"
                    )
                elif native_hls_fault == "encrypted":
                    value = value.replace(
                        b"#EXTM3U\n",
                        b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\n',
                    )
            if self.path == "/direct.ogg":
                value = ogg.read_bytes()
            if self.path in {"/direct.mp4", "/tunnel-video"}:
                value = mp4.read_bytes()
            if native_youtube_api == "html" and self.path == "/tunnel-video":
                value = b"<html>Upstream unavailable</html>"
            if self.path == "/direct.m4a":
                value = m4a.read_bytes()
            if portrait and self.path == "/portrait.m3u8":
                value = (
                    b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=300000,"
                    b'RESOLUTION=720x1280,CODECS="avc1.42c01e,mp4a.40.2"\n'
                    b"portrait-stream.m3u8\n"
                )
            elif portrait and self.path.startswith("/portrait-"):
                value = (tmp_path / self.path.lstrip("/")).read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/octet-stream"
                if self.path.startswith("/tunnel-")
                else "application/vnd.apple.mpegurl"
                if self.path.endswith(".m3u8")
                else "video/mp2t"
                if self.path.endswith(".ts")
                else "text/html"
                if self.path.endswith(".html")
                else "image/png"
                if self.path == "/cover.png"
                else "application/ogg"
                if self.path == "/direct.ogg"
                else "video/mp4"
                if self.path == "/direct.mp4"
                else "audio/mp4"
                if self.path == "/direct.m4a"
                else "audio/mpeg",
            )
            declared = len(value)
            if (
                (
                    native_youtube_api == "truncated"
                    and self.path == "/tunnel-video"
                )
                or self.path == "/truncated.mp3"
                or (
                    native_hls_fault == "truncated"
                    and self.path == "/native-2.mp3"
                )
            ):
                declared += 1024
                self.close_connection = True
                self.send_header("Connection", "close")
            self.send_header("Content-Length", str(declared))
            self.end_headers()
            if body:
                self.wfile.write(value)

        def log_message(self, *args):
            self.server.media_requests.append(
                (self.command, self.headers.get("Host"), self.path)
            )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "media.portal-test.example")]
    )
    now = datetime.now(UTC)
    hosts = (
        "media.portal-test.example",
        "www.instagram.com",
        "www.pinterest.com",
    )
    if native_catalog:
        hosts += (
            "www.youtube.com",
            "m.youtube.com",
            "soundcloud.com",
            "api-v2.soundcloud.com",
            "api.soundcloud.com",
            "open.spotify.com",
            "accounts.spotify.com",
            "api.spotify.com",
        )
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
                [x509.DNSName(host) for host in hosts]
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
    server.media_requests = []
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
    host = host.decode() if isinstance(host, bytes) else host
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
# Async HTTP workers use native uvloop sockets; redirect the external
# connection at its public connector boundary after the real DNS guard.
import asyncio, aiohappyeyeballs, uvloop
native_resolve = uvloop.Loop.getaddrinfo
async def external_native_resolve(self, host, port, *args, **kwargs):
    host = host.decode() if isinstance(host, bytes) else host
    if host in {hosts!r}:
        host = "1.1.1.1"
    result = await native_resolve(self, host, port, *args, **kwargs)
    return result
uvloop.Loop.getaddrinfo = external_native_resolve
native_connection = uvloop.Loop.create_connection
async def external_native_connection(
    self, factory, host=None, port=None, **kwargs
):
    name = host.decode() if isinstance(host, bytes) else host
    if (name in {hosts!r} or name == "1.1.1.1") and port == 443:
        if kwargs.get("ssl") and not kwargs.get("server_hostname"):
            kwargs["server_hostname"] = name
        host, port = "127.0.0.1", {server.server_port}
    result = await native_connection(self, factory, host, port, **kwargs)
    return result
uvloop.Loop.create_connection = external_native_connection
start_connection = aiohappyeyeballs.start_connection
async def external_async_connection(*, addr_infos, **kwargs):
    redirected = [
        (family, kind, protocol, canonname,
         ("127.0.0.1", {server.server_port})
         if address[:2] == ("1.1.1.1", 443) else address)
        for family, kind, protocol, canonname, address in addr_infos
    ]
    records = redirected if isinstance(
        asyncio.get_running_loop(), uvloop.Loop
    ) else addr_infos
    result = await start_connection(addr_infos=records, **kwargs)
    return result
aiohappyeyeballs.start_connection = external_async_connection
import os, subprocess
if os.getenv("PORTAL_NATIVE_NO_PROCESS") == "1":
    def reject_process(*args, **kwargs):
        raise RuntimeError("Native media workflow started a child process")
    subprocess.Popen.__init__ = reject_process
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
            lambda job: (
                len(ExternalTelegramHandler.media_files) == 1
                or job.status in {"failed", "partial"}
            ),
            timeout=20,
        )

        async def errors():
            async with portal.request() as request:
                page = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                return [item.error for item in page.items]

        assert len(ExternalTelegramHandler.media_files) == 1, portal.run(
            errors()
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

        async def errors():
            async with portal.request() as request:
                page = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                return [item.error for item in page.items]

        assert (result.status, result.total, result.sent, result.failed) == (
            "completed",
            count,
            count,
            0,
        ), (result.error, portal.run(errors()))
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


def test_audio_conversion_over_limit_is_rejected_and_cleaned(portal, tmp_path):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(tmp_path, audio_seconds=80)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            await portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(max_file_bytes=1_000_000).model_dump(mode="json"),
            )
            async with portal.request() as request:
                commands = await request.get(IMediaCommands)
                result = await commands.accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=211,
                        url="https://media.portal-test.example/direct.ogg",
                        mode="audio",
                    )
                )
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"failed", "completed", "partial"},
        )
        assert (result.status, result.sent, result.failed) == ("failed", 0, 1)
        assert not ExternalTelegramHandler.media_files
        assert not (Path(portal.settings.media.directory) / str(id)).exists()

        async def errors():
            async with portal.request() as request:
                page = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                return [item.error for item in page.items]

        assert "file limit" in (portal.run(errors())[0] or "")
    finally:
        server.shutdown()
        server.server_close()


def test_portrait_hls_downloads_complete_video_and_cleans_files(
    portal, tmp_path
):
    server, boundary = external_media(tmp_path, portrait=True)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=213,
                        url="https://media.portal-test.example/portrait.m3u8",
                    )
                )
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"failed", "completed", "partial"},
        )

        async def errors():
            async with portal.request() as request:
                page = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                return [item.error for item in page.items]

        assert (result.status, result.total, result.sent, result.failed) == (
            "completed",
            1,
            1,
            0,
        ), (result.error, portal.run(errors()))
        assert len(ExternalTelegramHandler.media_files) == 1
        assert ExternalTelegramHandler.media_files[0]["kind"] == "video"
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


def test_incomplete_stream_is_failed_without_sending_partial_file(
    portal, tmp_path
):
    server, boundary = external_media(tmp_path)
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    try:

        async def accept():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=215,
                        url="https://media.portal-test.example/truncated.mp3",
                        mode="audio",
                    )
                )
                return result.job.id

        id = portal.run(accept())
        portal.start_workers("src.apps.media")

        async def read():
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        result = portal.until(
            read,
            lambda job: job.status in {"failed", "completed", "partial"},
        )
        assert (result.status, result.sent, result.failed) == ("failed", 0, 1)
        assert not ExternalTelegramHandler.media_files
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "url,mode,hls,api",
    [
        ("https://www.youtube.com/watch?v=abc123DEF45", "audio", False, False),
        ("https://www.youtube.com/watch?v=abc123DEF45", "audio", False, True),
        ("https://www.youtube.com/watch?v=abc123DEF45", "media", False, False),
        ("https://www.youtube.com/watch?v=abc123DEF45", "media", False, True),
        ("https://open.spotify.com/track/NativeTrack1", "audio", False, False),
        ("https://open.spotify.com/track/NativeTrack1", "audio", True, False),
    ],
)
def test_native_music_download_delivery_and_reuse_without_child_processes(
    portal, tmp_path, url, mode, hls, api
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path,
        native_catalog=True,
        native_hls=hls,
        native_youtube_api=api,
        audio_seconds=4 if hls else 1,
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    portal.environment["PORTAL_YOUTUBE_TOKEN_PROVIDER_URL"] = (
        "https://media.portal-test.example"
    )
    try:

        async def accept(update_id):
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=update_id,
                        url=url,
                        mode=mode,
                    )
                )
                return result.job.id

        async def read(id):
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        async def errors(id):
            async with portal.request() as request:
                page = await (await request.get(IMediaQueries)).items(
                    id, USER, 1, 50
                )
                return [item.error for item in page.items]

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(
                    youtube_clients=["mweb"],
                    youtube_api_url="https://media.portal-test.example/cobalt"
                    if api
                    else None,
                ).model_dump(mode="json"),
            )
        )
        first = portal.run(accept(501))
        portal.start_workers("src.apps.media")
        result = portal.until(
            lambda: read(first),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=40,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            1,
            0,
        ), (result.error, portal.run(errors(first)), server.media_requests)
        assert len(ExternalTelegramHandler.media_files) == 1
        if api:
            assert not any(
                "/youtubei/" in path for _, _, path in server.media_requests
            )
            assert (
                sum(path == "/cobalt" for _, _, path in server.media_requests)
                == 1
            )
        original = ExternalTelegramHandler.media_files[0]
        assert not original.get("file_id")
        assert not (
            Path(portal.settings.media.directory) / str(first)
        ).exists()
        if "spotify" in url:
            assert original["title"] == "Native Song"
            assert original["performer"] == "Native Artist"
            assert "soundcloud.com" in original["caption"]
        second = portal.run(accept(502))
        result = portal.until(
            lambda: read(second),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=40,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            1,
            0,
        ), (result.error, portal.run(errors(second)))
        assert len(ExternalTelegramHandler.media_files) == 2
        assert (
            ExternalTelegramHandler.media_files[1]["file_id"]
            == "external-test-media-file"
        )
        ExternalTelegramHandler.media_cache_miss_once = True
        third = portal.run(accept(503))
        result = portal.until(
            lambda: read(third),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=40,
        )
        assert (result.status, result.sent, result.failed) == (
            "completed",
            1,
            0,
        )
        assert len(ExternalTelegramHandler.media_files) == 4
        assert ExternalTelegramHandler.media_files[2]["file_id"]
        assert not ExternalTelegramHandler.media_files[3].get("file_id")
        assert not (
            Path(portal.settings.media.directory) / str(third)
        ).exists()
        assert not (
            Path(portal.settings.media.directory) / str(second)
        ).exists()
    finally:
        server.shutdown()
        server.server_close()


def test_planning_and_dispatch_complete_concurrent_jobs_without_deadlocks(
    portal, tmp_path
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path, native_catalog=True, native_youtube_api=True
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    try:

        async def prepare():
            async with portal.request() as request:
                unit = await request.get(MySQLUnitOfWork)
                await unit.execute(
                    text("""
                    CREATE TRIGGER portal_test_plan_wait
                    BEFORE UPDATE ON tbl_media_jobs
                    FOR EACH ROW BEGIN
                      IF OLD.status='queued' AND NEW.status='planning' THEN
                        DO SLEEP(3);
                      END IF;
                    END
                """)
                )

        async def accept(update_id, video):
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=update_id,
                        url="https://www.youtube.com/watch?v=" + video,
                    )
                )
                return result.job.id

        async def waiting_claim():
            async with portal.request() as request:
                unit = await request.get(MySQLUnitOfWork)
                result = await unit.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.processlist "
                        "WHERE DB=DATABASE() AND STATE='User sleep'"
                    )
                )
                return result.scalar_one() > 0

        async def read(ids):
            async with portal.request() as request:
                query = await request.get(IMediaQueries)
                page = await query.page(USER, 1, 50)
                return [job for job in page.items if job.id in ids]

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(
                    youtube_api_url="https://media.portal-test.example/cobalt"
                ).model_dump(mode="json"),
            )
        )
        portal.run(prepare())
        first = portal.run(accept(781, "abc123DEF45"))
        portal.start_workers("src.apps.media")
        portal.until(waiting_claim, bool, timeout=20)
        second = portal.run(accept(782, "abc123DEF46"))
        result = portal.until(
            lambda: read({first, second}),
            lambda jobs: (
                len(jobs) == 2
                and all(
                    job.status in {"completed", "failed", "partial"}
                    for job in jobs
                )
            ),
            timeout=25,
        )
        assert [(job.status, job.sent, job.failed) for job in result] == [
            ("completed", 1, 0),
            ("completed", 1, 0),
        ]
        assert len(ExternalTelegramHandler.media_files) == 2
        assert not (
            Path(portal.settings.media.directory) / str(first)
        ).exists()
        assert not (
            Path(portal.settings.media.directory) / str(second)
        ).exists()
    finally:
        server.shutdown()
        server.server_close()


def test_youtube_api_checks_known_source_duration_before_delivery(
    portal, tmp_path
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path, native_catalog=True, native_youtube_api=True
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    try:

        async def prepare():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=791,
                        url="https://www.youtube.com/watch?v=abc123DEF45",
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
                                    url=result.job.url,
                                    source_url=result.job.url,
                                    engine="youtube",
                                    title="Full source",
                                    duration=60,
                                )
                            ]
                        ),
                    )
                    await jobs.change(
                        result.job.id, MediaJobChange(status="queued", total=1)
                    )
                return result.job.id

        async def read(id):
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(
                    youtube_api_url="https://media.portal-test.example/cobalt"
                ).model_dump(mode="json"),
            )
        )
        id = portal.run(prepare())
        portal.start_workers("src.apps.media")
        result = portal.until(
            lambda: read(id),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=30,
        )
        assert (result.status, result.sent, result.failed) == ("failed", 0, 1)
        assert not ExternalTelegramHandler.media_files
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("fault", ["html", "truncated"])
def test_youtube_tunnel_failure_never_sends_a_partial_file(
    portal, tmp_path, fault
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path, native_catalog=True, native_youtube_api=fault
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    try:

        async def accept():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=751,
                        url="https://www.youtube.com/watch?v=abc123DEF45",
                    )
                )
                return result.job.id

        async def read(id):
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(
                    youtube_api_url="https://media.portal-test.example/cobalt"
                ).model_dump(mode="json"),
            )
        )
        id = portal.run(accept())
        portal.start_workers("src.apps.media")
        result = portal.until(
            lambda: read(id),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=40,
        )
        assert (result.status, result.sent, result.failed) == ("failed", 0, 1)
        assert not ExternalTelegramHandler.media_files
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("fault", ["private", "encrypted", "truncated"])
def test_native_hls_rejects_unsafe_or_incomplete_audio_and_cleans_files(
    portal, tmp_path, fault
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path,
        native_catalog=True,
        native_hls=True,
        native_hls_fault=fault,
        audio_seconds=4,
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    try:

        async def accept():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=701,
                        url="https://open.spotify.com/track/NativeTrack1",
                        mode="audio",
                    )
                )
                return result.job.id

        async def read(id):
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(music_sources=["soundcloud"]).model_dump(
                    mode="json"
                ),
            )
        )
        id = portal.run(accept())
        portal.start_workers("src.apps.media")
        result = portal.until(
            lambda: read(id),
            lambda job: job.status in {"completed", "partial", "failed"},
            timeout=40,
        )
        assert (result.status, result.sent, result.failed) == ("failed", 0, 1)
        assert not ExternalTelegramHandler.media_files
        assert not (Path(portal.settings.media.directory) / str(id)).exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "catalog", ["complete", "missing", "changed", "private"]
)
def test_spotify_catalog_keeps_all_pages_or_rejects_incomplete_plan(
    portal, tmp_path, catalog
):
    from portal_contracts.configuration import SettingScope
    from portal_contracts.media import MediaPolicy

    server, boundary = external_media(
        tmp_path, native_catalog=True, native_spotify_api=catalog
    )
    portal.environment["PYTHONPATH"] = (
        str(boundary) + os.pathsep + portal.environment["PYTHONPATH"]
    )
    portal.environment["PORTAL_NATIVE_NO_PROCESS"] = "1"
    portal.environment["SPOTIPY_CLIENT_ID"] = "external-test-client"
    portal.environment["SPOTIPY_CLIENT_SECRET"] = "external-test-secret"
    portal.environment["PORTAL_SPOTIFY_ACCESS_TOKEN"] = (
        "external-test-user-token"
    )
    try:

        async def accept():
            async with portal.request() as request:
                result = await (await request.get(IMediaCommands)).accept(
                    MediaCreate(
                        owner_id=USER,
                        chat_id=USER,
                        bot_id=140003,
                        update_id=801,
                        url="https://open.spotify.com/playlist/NativePlaylist1",
                        mode="audio",
                    )
                )
                return result.job.id

        async def read(id):
            async with portal.request() as request:
                result = await (await request.get(IMediaJobService)).get(
                    id, USER
                )
                return result

        async def cancel_and_read_pages(id):
            async with portal.request() as request:
                await (await request.get(IMediaCommands)).cancel(id, USER)
            async with portal.request() as request:
                queries = await request.get(IMediaQueries)
                first = await queries.items(id, USER, 1, 50)
                last = await queries.items(id, USER, 2, 50)
                return first, last

        portal.run(
            portal.change(
                "media.policy",
                SettingScope.GLOBAL,
                MediaPolicy(music_sources=["soundcloud"]).model_dump(
                    mode="json"
                ),
            )
        )
        id = portal.run(accept())
        portal.start_workers("src.apps.media")
        job = portal.until(
            lambda: read(id),
            lambda job: job.total == 51 or job.status == "failed",
            timeout=40,
        )
        if catalog == "complete":
            assert job.total == 51
            first, last = portal.run(cancel_and_read_pages(id))
            assert first.total == last.total == 51
            assert [item.position for item in first.items] == list(
                range(1, 51)
            )
            assert [item.position for item in last.items] == [51]
            assert (portal.run(read(id))).status == "cancelled"
        else:
            assert (job.status, job.total, job.sent) == ("failed", 0, 0)
            assert not ExternalTelegramHandler.media_files
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "prior_revision,missing",
    [
        (
            "20261004_media_parallel",
            ["music_sources", "file_cache_seconds", "hls_max_segments"],
        ),
        ("20261005_media_policy", ["youtube_api_url"]),
    ],
)
def test_media_policy_upgrade_persists_defaults_and_preserves_custom_options(
    portal,
    prior_revision,
    missing,
):
    config = Config("api/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        portal.environment["PORTAL_DATABASE_URL"].replace("%", "%%"),
    )
    command.downgrade(config, prior_revision)

    async def prior_policy():
        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            async with transaction():
                result = await unit.execute(
                    text(
                        "SELECT v.id, v.value FROM tbl_setting_values v "
                        "JOIN tbl_setting_definitions d "
                        "ON d.id = v.definition_id "
                        "WHERE d.`key` = 'media.policy'"
                    )
                )
                id, raw = result.one()
                value = json.loads(raw)
                for key in missing:
                    value.pop(key)
                value["requests_per_hour"] = 7
                value["music_match_threshold"] = 0.95
                await unit.execute(
                    text(
                        "UPDATE tbl_setting_values SET value=:value, "
                        "revision=3 WHERE id=:id"
                    ),
                    {"value": json.dumps(value), "id": id},
                )
                return value

    async def read_policy():
        async with portal.request() as request:
            unit = await request.get(MySQLUnitOfWork)
            result = await unit.execute(
                text(
                    "SELECT v.value, v.revision FROM tbl_setting_values v "
                    "JOIN tbl_setting_definitions d ON d.id = v.definition_id "
                    "WHERE d.`key` = 'media.policy'"
                )
            )
            raw, revision = result.one()
            return json.loads(raw), revision

    before = portal.run(prior_policy())
    command.upgrade(config, "head")
    command.check(config)
    saved, revision = portal.run(read_policy())
    assert all(saved[key] == value for key, value in before.items())
    assert saved["music_sources"] == ["soundcloud", "youtube"]
    assert saved["file_cache_seconds"] == 604800
    assert saved["hls_max_segments"] == 512
    assert saved["youtube_api_url"] is None
    assert revision == 4
    command.upgrade(config, "head")
    assert portal.run(read_policy()) == (saved, revision)
