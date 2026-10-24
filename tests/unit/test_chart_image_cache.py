import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.pricing.charts.app.renderer import AssetChartRenderer
from src.modules.pricing.charts.domain.models import BrowserImageRequest
from src.modules.pricing.charts.infra.browser import ChartAssets


class MemoryImages:
    def __init__(self):
        self.images = {}

    async def get(self, key):
        return self.images.get(key)

    async def put(self, key, image):
        self.images[key] = image


@pytest.mark.asyncio
async def test_pages_share_images_across_renderers_and_coalesce_clicks():
    cache = MemoryImages()
    browser = SimpleNamespace(render=AsyncMock(return_value=b"png"))
    renderer = AssetChartRenderer(browser, ChartAssets(), cache)
    document = BrowserImageRequest(
        html="snapshot", script="v1", width=800, height=900
    )
    renderer.document = lambda card: document
    images = await asyncio.gather(*(renderer.render(None) for _ in range(10)))
    assert images == [b"png"] * 10
    browser.render.assert_awaited_once()
    second_process = AssetChartRenderer(browser, ChartAssets(), cache)
    second_process.document = lambda card: document
    assert await second_process.render(None) == b"png"
    browser.render.assert_awaited_once()
    # Rendering code and data are both part of the key: no stale visual reuse.
    document.script = "v2"
    await renderer.render(None)
    document.html = "new snapshot"
    await renderer.render(None)
    assert browser.render.await_count == 3


@pytest.mark.asyncio
async def test_image_cache_roundtrips_text_redis_with_bounded_retention():
    from src.modules.pricing.charts.infra.images import ChartImageCache

    client = SimpleNamespace(eval=AsyncMock(), get=AsyncMock())
    cache = ChartImageCache(
        SimpleNamespace(client=client),
        SimpleNamespace(tasks=SimpleNamespace(queue_name="isolated")),
    )
    image = b"\x89PNG\r\n\x1a\n\xff\x80"
    await cache.put("snapshot", image)
    script, keys, key, index, encoded, score = client.eval.await_args.args
    assert isinstance(encoded, str)
    assert keys == 2 and index.endswith(":index")
    assert "43200" in script and "> 64" in script
    assert key.startswith("isolated:")
    client.get.return_value = encoded
    assert await cache.get("snapshot") == image
    client.get.return_value = None
    assert await cache.get("missing") is None
    with pytest.raises(ValueError):
        await cache.put("invalid", b"not PNG")
