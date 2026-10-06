from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from src.modules.content.news.domain.dtos import CollectNews, NewsSource
from src.modules.content.news.infra.sources import NewsCollector, digest
from src.modules.ops.settings.domain.dtos import NewsSourceCatalog


@pytest.mark.asyncio
async def test_collection_skips_published_and_unreadable_candidates():
    now = datetime.now(UTC)
    urls = [f"https://articles.test/{index}" for index in range(16)]
    items = "".join(
        f"<item><title>News {index}</title><link>{url}</link>"
        f"<pubDate>{format_datetime(now - timedelta(hours=index))}</pubDate>"
        "</item>"
        for index, url in enumerate(urls)
    )

    class HTTP:
        def __init__(self):
            self.read = []

        async def get(self, url, *args, **kwargs):
            if url.endswith("/broken-feed"):
                raise ValueError("Source returned HTTP 503")
            if url.endswith("/feed"):
                return f"<rss><channel>{items}</channel></rss>".encode()
            self.read.append(url)
            if url in urls[1:4]:
                raise ValueError("Source returned HTTP 403")
            return (
                b"<article>"
                + b"Verified scientific news. " * 30
                + b"</article>"
            )

    sources = [
        NewsSource(
            id=path,
            feed_url=f"https://articles.test/{path}",
            allowed_hosts={"articles.test"},
            topics={"ai"},
            enabled=True,
        )
        for path in ("broken-feed", "feed")
    ]
    http = HTTP()
    collector = NewsCollector(http, NewsSourceCatalog(sources=sources))
    result = await collector.collect(
        CollectNews(
            topic="ai",
            since=now - timedelta(hours=24),
            excluded_url_hashes={digest(urls[0])},
        )
    )
    assert [article.url for article in result] == urls[4:7]
    assert urls[0] not in http.read
    assert len(http.read) == 6


@pytest.mark.asyncio
async def test_collection_bounds_unreadable_article_requests():
    from src.modules.content.news.domain.dtos import ArticleInput

    now = datetime.now(UTC)
    source = NewsSource(
        id="feed",
        feed_url="https://articles.test/feed",
        allowed_hosts={"articles.test"},
        topics={"ai"},
        enabled=True,
    )

    class UnreadableCollector(NewsCollector):
        reads = 0

        async def feed(self, source, since):
            return [
                ArticleInput(
                    source_id=source.id,
                    url=f"https://articles.test/{index}",
                    title=f"News {index}",
                    published_at=now - timedelta(minutes=index),
                    fetched_at=now,
                    body="",
                )
                for index in range(50)
            ]

        async def article(self, entry):
            self.reads += 1
            return entry.model_copy(update={"body": "Too short."})

    collector = UnreadableCollector(None, NewsSourceCatalog(sources=[source]))
    assert (
        await collector.collect(
            CollectNews(topic="ai", since=now - timedelta(hours=24))
        )
        == []
    )
    assert collector.reads == 12
