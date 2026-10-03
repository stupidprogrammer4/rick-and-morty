import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PORTAL_TRANSPORT_TESTS") != "1",
        reason=(
            "Set PORTAL_TRANSPORT_TESTS=1 where socketpair writes are allowed"
        ),
    ),
]


@pytest.mark.asyncio
async def test_mcp_discovers_tools_through_native_stdio(monkeypatch):
    monkeypatch.setenv(
        "PYTHONPATH",
        str(Path("api").resolve())
        + ":"
        + str(Path("packages/contracts").resolve()),
    )
    monkeypatch.setenv("PORTAL_ENV_FILE", "/tmp/nonexistent-portal-env")
    monkeypatch.setenv("PAPILIO_CONFIG", "config.yml.sample")
    monkeypatch.setenv("PORTAL_SERVICE_KEY", "test-service-key-" * 4)
    monkeypatch.setenv("PORTAL_ADMIN_USER_IDS", "140001")
    from src.modules.rick.app.context import ToolContext
    from src.modules.rick.infra.mcp import MissionMCPClient

    client = MissionMCPClient()
    async with client.connect(
        ToolContext(owner_id=140001, mission_id=0)
    ) as session:
        tools = await client.tools(session)
    names = {item["function"]["name"] for item in tools}
    assert names == {
        "collect_news",
        "search_news",
        "read_article",
        "get_market_prices",
        "react_to_message",
        "create_post_draft",
    }
    assert not any("publish" in name for name in names)
