import pytest
from pydantic import ValidationError

from portal_contracts.media import MediaCreate
from src.modules.media.downloads.app.commands import media_provider
from src.modules.media.sources.infra.downloaders.network import public_address


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
        "192.168.1.5",
    ],
)
def test_public_downloader_blocks_private_destinations(address):
    assert not public_address(address)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a",
        "https://user:pass@example.com/a",
        "https://example.com:8443/a",
        "file:///etc/passwd",
    ],
)
def test_download_requires_https_without_url_credentials(url):
    with pytest.raises(ValidationError):
        MediaCreate(owner_id=1, chat_id=1, bot_id=2, update_id=3, url=url)


def test_provider_identity_does_not_accept_hostname_spoof():
    assert media_provider("https://instagram.com.evil.example/p/a") == "video"
    assert media_provider("https://www.instagram.com/p/a") == "instagram"


@pytest.mark.parametrize(
    "title,artist,candidate,performer,duration,accepted",
    [
        (
            "Native Song",
            "Native Artist",
            "Native Song",
            "Native Artist",
            200,
            True,
        ),
        ("Song", "Artist", "Artist - Song (Official Audio)", None, 200, True),
        ("Song", "Artist", "Song", "Someone Else", 200, False),
        ("Song", "Artist", "Song (Live)", "Artist", 200, False),
        ("Song", "Artist", "Song", "Artist", 30, False),
        ("Alive", "Artist", "Alive", "Artist", 200, True),
        ("Song", "Artist", "Song (Remastered)", "Artist", 200, False),
        (
            "Horizons",
            "Scott Buckley",
            "Horizons (CC-BY)",
            "Scott Buckley",
            200,
            True,
        ),
    ],
)
def test_music_matches_full_track_artist_and_version(
    title, artist, candidate, performer, duration, accepted
):
    from portal_contracts.media import MediaPolicy
    from src.modules.media.sources.app.matching import MusicMatching
    from src.modules.media.sources.domain.dtos import DownloadItem
    from src.modules.media.sources.domain.music import MusicCandidate

    policy = MediaPolicy()
    item = DownloadItem(
        url="https://open.spotify.com/track/Track",
        source_url="https://open.spotify.com/track/Track",
        title=title,
        performer=artist,
        duration=200,
    )
    found = MusicCandidate(
        url="https://soundcloud.com/artist/song",
        title=candidate,
        performer=performer,
        duration=duration,
    )
    assert (
        MusicMatching(policy).score(item, found)
        >= policy.music_match_threshold
    ) is accepted


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/a",
        "https://169.254.169.254/a",
        "https://[::1]/a",
        "https://[::ffff:127.0.0.1]/a",
    ],
)
def test_native_media_urls_reject_private_address_literals(url):
    from src.modules.media.sources.infra.downloaders.http import MediaHTTP

    with pytest.raises(ValueError):
        MediaHTTP.validate(url)
