from collections.abc import Awaitable
from typing import Protocol

from portal_contracts.content import (
    PublicationChartOut,
    PublicationOut,
    PublicationResolution,
    PublishedPage,
    PublishRequest,
)
from portal_contracts.enums import BotRole
from portal_contracts.telegram import (
    DeliveryResult,
    ReactionRequest,
    TelegramDelivery,
    TelegramPhotoDelivery,
    TypingRequest,
)
from src.modules.content.publications.domain.models import PublicationModel


class ITelegramGateway(Protocol):
    def send_photo(
        self, data: TelegramPhotoDelivery
    ) -> Awaitable[DeliveryResult]: ...
    def send(self, data: TelegramDelivery) -> Awaitable[DeliveryResult]: ...
    def react(self, data: ReactionRequest) -> Awaitable[None]: ...
    def typing(self, data: TypingRequest) -> Awaitable[None]: ...


class IPublicationCommands(Protocol):
    def schedule(
        self, draft_id: int, owner_id: int, data: PublishRequest
    ) -> Awaitable[PublicationOut]: ...
    def dispatch(self, publication_id: int) -> Awaitable[None]: ...
    def resolve(
        self, id: int, owner_id: int, data: PublicationResolution
    ) -> Awaitable[PublicationOut]: ...


class IPublicationRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...


class IPublicationChartCommands(Protocol):
    def schedule(self, publication: PublicationModel) -> Awaitable[None]: ...
    def dispatch(self, chart_id: int) -> Awaitable[None]: ...
    def resolve(
        self, id: int, owner_id: int, data: PublicationResolution
    ) -> Awaitable[PublicationChartOut]: ...


class IPublicationChartRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...


class IPublicationChartQuery(Protocol):
    def get_for_publication(
        self, publication_id: int, owner_id: int
    ) -> Awaitable[list[PublicationChartOut]]: ...


class IPublishedPageQuery(Protocol):
    def get(
        self,
        publication_id: int,
        page: int,
        role: BotRole,
        chat_id: int,
        message_id: int,
    ) -> Awaitable[PublishedPage]: ...
