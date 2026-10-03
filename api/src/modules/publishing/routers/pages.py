from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from portal_contracts.content import (
    PublicationChartOut,
    PublicationResolution,
    PublishedPage,
)
from portal_contracts.enums import BotRole
from src.config.security import owner_auth, service_auth
from src.modules.publishing.interfaces import (
    IPublicationChartCommands,
    IPublicationChartQuery,
    IPublishedPageQuery,
)

router = APIRouter(
    prefix="/internal/publications",
    tags=["Publication pages and charts"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)


@router.get(
    "/{id:int}/pages/{page:int}",
    response_model=APIResponse[PublishedPage, None],
)
async def get_page(
    id: int,
    page: int,
    role: BotRole,
    chat_id: int,
    message_id: int,
    query: FromDishka[IPublishedPageQuery],
):
    result = await query.get(id, page, role, chat_id, message_id)
    return APIResponse(success=True, data=result)


@router.get(
    "/{id:int}/charts",
    response_model=APIResponse[PublicationChartOut, None],
)
async def get_charts(
    id: int,
    query: FromDishka[IPublicationChartQuery],
    owner_id: int = Depends(owner_auth),
):
    rows = await query.get_for_publication(id, owner_id)
    return APIResponse(success=True, data=rows)


@router.post(
    "/charts/{id:int}/resolve",
    response_model=APIResponse[PublicationChartOut, None],
)
async def resolve_chart(
    id: int,
    data: PublicationResolution,
    commands: FromDishka[IPublicationChartCommands],
    owner_id: int = Depends(owner_auth),
):
    result = await commands.resolve(id, owner_id, data)
    return APIResponse(success=True, data=result)
