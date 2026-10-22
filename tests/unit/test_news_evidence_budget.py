from datetime import UTC, datetime

from src.modules.automation.agents.app.evidence import news_evidence
from src.modules.content.news.domain.dtos import ArticleEvidence


def article(id, body, truncated=False):
    return ArticleEvidence(
        id=id,
        source_id="source",
        url=f"https://example.org/{id}",
        title=f"Article {id}",
        published_at=None,
        fetched_at=datetime.now(UTC),
        body=body,
        truncated=truncated,
    )


def test_context_is_bounded_without_changing_full_evidence():
    originals = [article(i, "A complete sentence. " * 800) for i in range(3)]
    result = news_evidence(originals, 6000)
    assert sum(len(x["body"]) for x in result) <= 6000
    assert [x["id"] for x in result] == [0, 1, 2]
    assert [x["url"] for x in result] == [x.url for x in originals]
    assert all(x["truncated"] for x in result)
    assert all(x["body"].rstrip().endswith(".") for x in result)
    assert all(len(x.body) > 6000 and not x.truncated for x in originals)


def test_short_evidence_and_existing_truncation_are_preserved():
    values = [article(1, "Short fact."), article(2, "Earlier excerpt.", True)]
    assert news_evidence(values, 6000) == [
        x.model_dump(mode="json") for x in values
    ]
    assert news_evidence([], 6000) == []
