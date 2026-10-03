from collections.abc import Awaitable
from typing import Protocol

from portal_contracts.content import (
    PublicationOut,
    PublicationResolution,
    PublishRequest,
)
from portal_contracts.telegram import (
    DeliveryResult,
    ReactionRequest,
    TelegramDelivery,
    TypingRequest,
)
from src.modules.publishing.domain.models import PrivateReplyModel


class ITelegramGateway(Protocol):
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


class IPrivateReplyService(Protocol):
    def create(self, data: PrivateReplyModel) -> Awaitable[None]: ...
    def dispatch(self, id: int) -> Awaitable[None]: ...


class IPublicationRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...


class IReplyRecovery(Protocol):
    def enqueue_pending(self) -> Awaitable[None]: ...
