import asyncio
import socket

import aiohttp
import httpx
import pytest

from src.shared.http import PublicResolver, SourceHTTPClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a",
        "https://127.0.0.1/a",
        "https://[::1]/a",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.1/a",
        "https://user:password@example.com/a",
        "https://example.com:444/a",
        "https://evil.example/a",
        "file:///etc/passwd",
    ],
)
async def test_sources_reject_private_and_unconfigured_targets(url):
    class NoNetwork:
        def get(self, *args, **kwargs):
            raise AssertionError("Forbidden URL reached network")

    with pytest.raises(ValueError):
        await SourceHTTPClient(NoNetwork()).get(
            url,
            {"example.com", "127.0.0.1", "::1", "169.254.169.254", "10.0.0.1"},
        )


@pytest.mark.asyncio
async def test_mixed_dns_results_cannot_rebind_to_private_ip(monkeypatch):
    async def dns(self, host, port=0, family=socket.AF_INET):
        return [dict(host="8.8.8.8"), dict(host="127.0.0.1")]

    monkeypatch.setattr(aiohttp.ThreadedResolver, "resolve", dns)
    resolver = PublicResolver()
    try:
        with pytest.raises(ValueError):
            await resolver.resolve("example.com", 443)
    finally:
        await resolver.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,size,body",
    [
        (302, None, b"redirect"),
        (200, 100, b"large"),
        (200, None, b"01234567890"),
    ],
)
async def test_sources_reject_redirects_and_large_responses(
    status, size, body
):
    class Content:
        async def readexactly(self, length):
            if len(body) < length:
                raise asyncio.IncompleteReadError(body, length)
            return body[:length]

    class Response:
        content = Content()
        content_length = size

        async def __aenter__(self):
            self.status = status
            return self

        async def __aexit__(self, *args):
            pass

    class ExternalHTTP:
        def get(self, url, **kwargs):
            assert kwargs["allow_redirects"] is False
            return Response()

    with pytest.raises(ValueError):
        await SourceHTTPClient(ExternalHTTP()).get(
            "https://example.com/a", {"example.com"}, maximum_bytes=10
        )


@pytest.mark.asyncio
async def test_api_requires_service_key_before_loading_business_data(
    monkeypatch,
):
    monkeypatch.setenv("PORTAL_ENV_FILE", "/tmp/nonexistent-portal-env")
    monkeypatch.setenv("PAPILIO_CONFIG", "config.yml.sample")
    monkeypatch.setenv("PORTAL_SERVICE_KEY", "test-service-key-" * 4)
    monkeypatch.setenv("PORTAL_ADMIN_USER_IDS", "140001")
    from papilio.api.application import create_app
    from papilio.core.config import get_settings

    from src.config.providers import infrastructure_providers
    from src.config.settings import PortalAppSettings

    settings = get_settings(PortalAppSettings)
    app = create_app(
        settings, providers=infrastructure_providers(settings), middleware=[]
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/internal/configuration/values")
            assert response.status_code == 401
            response = await client.get(
                "/internal/configuration/values",
                headers=[(b"Authorization", b"Bearer \xff")],
            )
            assert response.status_code == 401
            response = await client.get(
                "/internal/configuration/values",
                headers={
                    "Authorization": "Bearer "
                    + settings.security.service_key.get_secret_value(),
                    "X-Portal-Owner": "140002",
                },
            )
            assert response.status_code == 403
