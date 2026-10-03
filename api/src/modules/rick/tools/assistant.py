from dishka import FromDishka
from papilio.mcp.router import MCPRouter

from portal_contracts.content import DraftOut
from portal_contracts.telegram import ReactionEmoji
from src.modules.news.domain.dtos import ArticleEvidence, NewsDraft
from src.modules.rick.interfaces import IAgentToolCommands

router = MCPRouter()


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
    description="Save an evidence-linked draft. This does not publish."
)
async def create_post_draft(
    draft: NewsDraft, command: FromDishka[IAgentToolCommands]
) -> DraftOut:
    result = await command.create_post_draft(draft)
    return result
