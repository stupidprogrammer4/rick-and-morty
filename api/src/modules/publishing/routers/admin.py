from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from portal_contracts.content import (
    PublicationOut,
    PublicationResolution,
    PublishRequest,
)
from src.config.security import owner_auth, service_auth
from src.modules.publishing.interfaces import IPublicationCommands

router = APIRouter(
    prefix="/internal",
    tags=["Publishing"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.post(
    "/drafts/{id:int}/publish",
    response_model=APIResponse[PublicationOut, None],
)
async def publish(
    id: int,
    data: PublishRequest,
    command: FromDishka[IPublicationCommands],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[PublicationOut, None]:
    result = await command.schedule(id, owner_id, data)
    return APIResponse.from_data(result)


@router.post(
    "/publications/{id:int}/resolve",
    response_model=APIResponse[PublicationOut, None],
)
async def resolve(
    id: int,
    data: PublicationResolution,
    command: FromDishka[IPublicationCommands],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[PublicationOut, None]:
    result = await command.resolve(id, owner_id, data)
    return APIResponse.from_data(result)
