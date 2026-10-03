from portal_contracts.content import PublicationPages, PublishedPage
from portal_contracts.enums import BotRole
from src.modules.publishing.infra.mysql import PublicationRepository
from src.shared.errors import missing


class PublishedPageQuery:
    def __init__(self, repo: PublicationRepository):
        self.repo = repo

    async def get(
        self,
        publication_id: int,
        page: int,
        role: BotRole,
        chat_id: int,
        message_id: int,
    ) -> PublishedPage:
        row = await self.repo.get(publication_id)
        if (
            row is None
            or row.status != "sent"
            or row.pages is None
            or row.bot_role != role
            or row.channel_id != chat_id
            or row.message_id != message_id
        ):
            raise missing("published page", publication_id)
        pages = PublicationPages.model_validate_json(row.pages)
        if not 0 <= page < len(pages.items):
            raise missing("published page", page)
        return PublishedPage(
            role=role,
            chat_id=chat_id,
            message_id=message_id,
            text=pages.items[page].text,
            navigation=pages.navigation(publication_id, page),
        )
