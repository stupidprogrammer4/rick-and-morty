from dishka import FromDishka
from papilio.mcp.router import MCPRouter

from portal_contracts.content import DraftOut
from portal_contracts.occasions import OccasionDay, OccasionDraft
from portal_contracts.telegram import ReactionEmoji
from src.modules.automation.agents.interfaces import IAgentToolCommands
from src.modules.content.news.domain.dtos import ArticleEvidence, NewsDraft

router = MCPRouter()


@router.tool(
    description=(
        "Read every recorded Iranian, ancient, religious and international "
        "occasion for an ISO Gregorian date, or today in the portal timezone. "
        "Scheduled occasions missions are bound to their own date. "
        "The response "
        "contains event IDs, calendar sources and coverage warnings."
    )
)
async def get_calendar_occasions(
    command: FromDishka[IAgentToolCommands], on_date: str | None = None
) -> OccasionDay:
    return await command.get_calendar_occasions(on_date)


@router.tool(
    description=(
        "Save Rick's daily draft after reading get_calendar_occasions. "
        "Include every returned event_id exactly once with a short Rick-style "
        "comment, intro and outro. Dates, titles and sources are supplied "
        "by the calendar. Empty calendar days require an empty comments list. "
        "This tool does not publish."
    )
)
async def create_occasion_draft(
    draft: OccasionDraft, command: FromDishka[IAgentToolCommands]
) -> DraftOut:
    return await command.create_occasion_draft(draft)


@router.tool(
    description="Morty collects at most 3 current articles from allowed feeds."
)
async def collect_news(
    topic: str, command: FromDishka[IAgentToolCommands]
) -> list[ArticleEvidence]:
    result = await command.collect_news(topic)
    return result


@router.tool(description="Read collected evidence belonging to this mission.")
async def search_news(
    command: FromDishka[IAgentToolCommands],
) -> list[ArticleEvidence]:
    result = await command.search_news()
    return result


@router.tool(description="Read one article by its recorded evidence ID.")
async def read_article(
    article_id: int, command: FromDishka[IAgentToolCommands]
) -> ArticleEvidence:
    result = await command.read_article(article_id)
    return result


@router.tool(
    description="Get validated prices from the owner's configured site."
)
async def get_market_prices(command: FromDishka[IAgentToolCommands]) -> str:
    result = await command.get_market_prices()
    return result


@router.tool(description="React to the owner's original private message only.")
async def react_to_message(
    emoji: ReactionEmoji, command: FromDishka[IAgentToolCommands]
) -> str:
    result = await command.react_to_message(emoji)
    return result


@router.tool(
    description=(
        "Save one evidence-linked draft containing at most two articles. "
        "Call this tool once per response. This does not publish."
    )
)
async def create_post_draft(
    draft: NewsDraft, command: FromDishka[IAgentToolCommands]
) -> DraftOut:
    result = await command.create_post_draft(draft)
    return result
