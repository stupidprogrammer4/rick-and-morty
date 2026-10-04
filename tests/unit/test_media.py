import pytest
from pydantic import ValidationError

from portal_contracts.media import MediaCreate
from src.modules.media.app.commands import media_provider
from src.modules.media.infra.downloaders.network import public_address


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
