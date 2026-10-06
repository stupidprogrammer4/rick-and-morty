import asyncio
import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from defusedxml import ElementTree

from src.modules.content.news.domain.dtos import (
    ArticleInput,
    CollectNews,
    NewsSource,
)
from src.modules.content.news.infra.hackernews import HackerNewsSource
from src.modules.ops.settings.domain.dtos import NewsSourceCatalog
from src.shared.dates import utc_now
from src.shared.http import SourceHTTPClient


class ArticleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "header", "footer", "aside"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "header", "footer", "aside"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if not key.startswith("utm_") and key not in {"fbclid", "gclid"}
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


class NewsCollector:
    def __init__(self, client: SourceHTTPClient, catalog: NewsSourceCatalog):
        self.client = client
        self.sources = catalog.sources

    async def collect(self, data: CollectNews) -> list[ArticleInput]:
        sources = [
            source
            for source in self.sources
            if source.enabled
            and (
                source.kind == "hackernews"
                or source.topics.intersection(data.topic.lower().split())
            )
        ]
        if not sources:
            raise ValueError("برای این موضوع منبع فعال انتخاب نشده.")
        feeds = await asyncio.gather(
            *(
                HackerNewsSource(self.client, source).search(data)
                if source.kind == "hackernews"
                else self.feed(source, data.since)
                for source in sources[:6]
            ),
            return_exceptions=True,
        )
        entries = [
            entry for feed in feeds if isinstance(feed, list) for entry in feed
        ]
        unique = {canonical_url(entry.url): entry for entry in entries}
        selected = sorted(
            (
                entry
                for entry in unique.values()
                if digest(canonical_url(entry.url))
                not in data.excluded_url_hashes
            ),
            key=lambda x: x.published_at or data.since,
            reverse=True,
        )[:12]
        articles: list[ArticleInput] = []
        for offset in range(0, len(selected), 3):
            batch = await asyncio.gather(
                *(
                    self.article(entry)
                    for entry in selected[offset : offset + 3]
                ),
                return_exceptions=True,
            )
            articles.extend(
                article
                for article in batch
                if isinstance(article, ArticleInput)
                and len(article.body) >= 250
            )
            if len(articles) >= data.limit:
                break
        return articles[: data.limit]

    async def feed(
        self, source: NewsSource, since: datetime
    ) -> list[ArticleInput]:
        raw = await self.client.get(
            str(source.feed_url), source.allowed_hosts, maximum_bytes=500_000
        )
        root = ElementTree.fromstring(raw)
        atom = "{http://www.w3.org/2005/Atom}"
        elements = [*root.findall(".//item"), *root.findall(f"{atom}entry")]
        entries: list[ArticleInput] = []
        for item in elements[:100]:
            title = item.findtext("title") or item.findtext(f"{atom}title")
            url = item.findtext("link")
            if not url:
                link = item.find(f"{atom}link")
                url = link.get("href") if link is not None else None
            raw_date = (
                item.findtext("pubDate")
                or item.findtext(f"{atom}published")
                or item.findtext(f"{atom}updated")
            )
            if not title or not url or not raw_date:
                continue
            try:
                date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                try:
                    date = parsedate_to_datetime(raw_date)
                except (ValueError, TypeError):
                    continue
            if date.tzinfo is None or date < since or date > utc_now():
                continue
            entries.append(
                ArticleInput(
                    source_id=source.id,
                    url=canonical_url(url),
                    title=title[:300],
                    published_at=date,
                    fetched_at=utc_now(),
                    body="",
                )
            )
        return entries

    async def article(self, entry: ArticleInput) -> ArticleInput:
        source = next(x for x in self.sources if x.id == entry.source_id)
        hosts = source.allowed_hosts
        if source.external_articles:
            host = urlsplit(entry.url).hostname
            if host is None:
                raise ValueError("Article has no public host")
            hosts = {host}
        raw = await self.client.get(entry.url, hosts)
        parser = ArticleTextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        body = "\n".join(parser.parts)
        return entry.model_copy(
            update={
                "body": body[:8000],
                "truncated": len(body) > 8000,
                "fetched_at": utc_now(),
            }
        )

    async def read_url(self, url: str) -> ArticleInput:
        host = urlsplit(url).hostname
        source = next(
            (
                source
                for source in self.sources
                if source.enabled and host in source.allowed_hosts
            ),
            None,
        )
        if source is None:
            raise ValueError("دامنه این مقاله در منابع فعال نیست.")
        entry = ArticleInput(
            source_id=source.id,
            url=canonical_url(url),
            title="مقاله انتخاب‌شده",
            published_at=None,
            fetched_at=utc_now(),
            body="",
        )
        result = await self.article(entry)
        if len(result.body) < 250:
            raise ValueError("متن کافی از مقاله دریافت نشد.")
        return result


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
