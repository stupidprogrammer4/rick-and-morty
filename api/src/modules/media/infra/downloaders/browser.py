import os
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlsplit

import httpx

from src.modules.media.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.infra.downloaders.network import validate_url


class BrowserDownloader:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    def plan(self) -> DownloadPlan:
        from playwright.sync_api import Route, sync_playwright

        candidates: dict[str, str] = {}
        total_bytes = 0
        with (
            httpx.Client(trust_env=False, timeout=15) as client,
            sync_playwright() as playwright,
        ):
            if self.request.cookie_file:
                jar = MozillaCookieJar(self.request.cookie_file)
                jar.load()
                for cookie in jar:
                    client.cookies.set(
                        cookie.name,
                        cookie.value or "",
                        domain=cookie.domain,
                        path=cookie.path,
                    )
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=os.getenv("PORTAL_BROWSER_EXECUTABLE") or None,
                args=[
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--host-resolver-rules=MAP * ~NOTFOUND",
                ],
            )
            context = browser.new_context(
                service_workers="block", accept_downloads=False
            )
            context.route_web_socket("**/*", lambda route: route.close())

            def bridge(route: Route) -> None:
                nonlocal total_bytes
                request = route.request
                try:
                    validate_url(request.url)
                    if request.resource_type == "media":
                        candidates[request.url] = "video"
                        route.abort()
                        return
                    headers = {
                        key: value
                        for key, value in request.all_headers().items()
                        if key.lower()
                        not in {
                            "host",
                            "content-length",
                            "connection",
                            "accept-encoding",
                        }
                    }
                    with client.stream(
                        request.method,
                        request.url,
                        headers=headers,
                        content=request.post_data_buffer,
                    ) as response:
                        body = bytearray()
                        for chunk in response.iter_bytes(65536):
                            total_bytes += len(chunk)
                            if (
                                len(body) + len(chunk) > 4_000_000
                                or total_bytes > 20_000_000
                            ):
                                raise ValueError(
                                    "Browser response budget exceeded"
                                )
                            body.extend(chunk)
                        response_headers = {
                            key: value
                            for key, value in response.headers.items()
                            if key.lower()
                            not in {
                                "content-encoding",
                                "content-length",
                                "transfer-encoding",
                            }
                        }
                        route.fulfill(
                            status=response.status_code,
                            headers=response_headers,
                            body=bytes(body),
                        )
                except Exception:
                    route.abort()

            context.route("**/*", bridge)
            try:
                page = context.new_page()
                page.goto(
                    self.request.url,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                page.wait_for_timeout(2500)
                rows = page.evaluate(
                    """() => [...document.querySelectorAll(
                        'video[src], audio[src], video source[src], '
                        + 'audio source[src], meta[property="og:video"], '
                        + 'meta[property="og:video:url"], '
                        + 'meta[property="og:image"]'
                    )].map(n => ({url: n.src || n.content,
                        kind: n.tagName === 'AUDIO' ? 'audio'
                        : n.tagName === 'META'
                        && n.getAttribute('property') === 'og:image'
                        ? 'photo' : 'video'}))"""
                )
                for row in rows:
                    if isinstance(row.get("url"), str) and row[
                        "url"
                    ].startswith("https://"):
                        candidates[row["url"]] = row["kind"]
                title = page.title()[:200] or "Media"
            finally:
                browser.close()
        items = []
        for url, value in candidates.items():
            kind = (
                "audio"
                if value == "audio"
                else "photo"
                if value == "photo"
                else "video"
            )
            if urlsplit(url).path.lower().endswith((".m3u8", ".mpd")):
                items.append(
                    DownloadItem(
                        url=self.request.url,
                        source_url=self.request.url,
                        title=title,
                        engine="video",
                        kind=kind,
                    )
                )
            else:
                items.append(
                    DownloadItem(
                        url=url,
                        source_url=self.request.url,
                        title=title,
                        engine="direct",
                        kind=kind,
                        headers={"Referer": self.request.url},
                    )
                )
        if not items:
            raise ValueError("No downloadable public media found on this page")
        if len(items) > self.request.policy.max_playlist_items:
            raise ValueError("Page exceeds configured item limit")
        return DownloadPlan(items=items)
