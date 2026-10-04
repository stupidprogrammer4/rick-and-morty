import asyncio
import os
from base64 import b64encode
from functools import lru_cache
from pathlib import Path

from playwright.async_api import async_playwright

from src.modules.pricing.charts.domain.models import BrowserImageRequest


class ChartAssets:
    directory = Path(__file__).parent / "assets"

    @lru_cache(maxsize=32)
    def text(self, name: str) -> str:
        path = (self.directory / name).resolve()
        if path.parent != self.directory.resolve():
            raise ValueError("Invalid chart asset path")
        return path.read_text()

    @lru_cache(maxsize=1)
    def font(self) -> str:
        data = (self.directory / "Vazirmatn.woff2").read_bytes()
        return "data:font/woff2;base64," + b64encode(data).decode("ascii")

    def logo(self, name: str) -> str:
        if not name.endswith(".svg"):
            raise ValueError("Chart logos must reference packaged SVG assets")
        return "data:image/svg+xml;base64," + b64encode(
            self.text(name).encode()
        ).decode("ascii")


class BrowserImageRenderer:
    def __init__(self, assets: ChartAssets):
        self.assets = assets
        self.capacity = asyncio.Semaphore(1)

    async def render(self, request: BrowserImageRequest) -> bytes:
        async with asyncio.timeout(30), self.capacity:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    executable_path=os.getenv("PORTAL_BROWSER_EXECUTABLE")
                    or None,
                    args=["--disable-dev-shm-usage"],
                )
                try:
                    context = await browser.new_context(
                        viewport={
                            "width": request.width,
                            "height": request.height,
                        },
                        device_scale_factor=1,
                        locale="fa-IR",
                        service_workers="block",
                    )
                    await context.route("**/*", lambda route: route.abort())
                    await context.route_web_socket(
                        "**/*", lambda route: route.close()
                    )
                    page = await context.new_page()
                    await page.set_content(request.html)
                    await page.add_script_tag(
                        content=self.assets.text("lightweight-charts.js")
                    )
                    await page.add_script_tag(
                        content=self.assets.text("apexcharts.js")
                    )
                    await page.add_script_tag(content=request.script)
                    await page.wait_for_function("window.chartReady === true")
                    await page.evaluate("document.fonts.ready")
                    image = await page.screenshot(type="png")
                    if len(image) > 256 * 1024:
                        raise ValueError("Chart image exceeds transport limit")
                    return image
                finally:
                    await browser.close()
