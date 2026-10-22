from amupouya_calendar.models import OccasionDay
from pydantic import ValidationError

from src.modules.automation.agents.domain.dtos import AgentHistory
from src.modules.content.news.domain.dtos import ArticleEvidence


def calendar_evidence(history: AgentHistory) -> OccasionDay | None:
    calls = {
        call.id
        for message in history.messages
        for call in message.tool_calls or []
        if call.function.name == "get_calendar_occasions"
    }
    for message in reversed(history.messages):
        if message.role == "tool" and message.tool_call_id in calls:
            try:
                day = OccasionDay.model_validate_json(message.content or "")
            except ValidationError:
                continue
            return day
    return None


def news_evidence(
    articles: list[ArticleEvidence], max_body_chars: int
) -> list[dict]:
    """Bound model context without changing stored evidence."""
    if max_body_chars <= 0:
        raise ValueError("Evidence budget must be positive")
    if not articles:
        return []
    allowance = max_body_chars // len(articles)
    result = []
    for article in articles:
        item = article.model_dump(mode="json")
        body = article.body
        excerpt = body[:allowance]
        if len(body) > allowance:
            boundary = max(excerpt.rfind(". "), excerpt.rfind("\n"))
            if boundary >= allowance // 2:
                excerpt = excerpt[: boundary + 1]
        item["body"] = excerpt
        item["truncated"] = article.truncated or excerpt != body
        result.append(item)
    return result
