from papilio.core.logger import logger
from papilio.infra.db.tools.conflicts import handle_conflicts
from papilio.infra.db.tools.decorators import transactional

from src.modules.pricing.logins.domain.events import SourceUnauthorizedInput
from src.modules.pricing.logins.interfaces import ISourceLoginService


class SourceUnauthorizedHandler:
    def __init__(self, service: ISourceLoginService) -> None:
        self.service = service

    @handle_conflicts
    @transactional
    async def handle(self, data: SourceUnauthorizedInput) -> int:
        """
        Desc: Sign refused sources back in after a crawl was rejected.
        Args:
            data (SourceUnauthorizedInput): Codes of the refused sources.
        Returns:
            return (int): How many sources were signed back in.
        """
        saved = await self.service.login_codes(data.codes)
        logger.info(
            "signed %s of %s sources back in after a refused crawl",
            saved,
            len(data.codes),
        )
        return saved
