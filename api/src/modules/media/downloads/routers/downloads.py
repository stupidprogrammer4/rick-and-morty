from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Header, Query
from papilio.api.responses.envelope import APIResponse

from portal_contracts.media import (
    MediaAccepted,
    MediaCreate,
    MediaFileAuthorization,
    MediaFileDelivery,
    MediaItemPage,
    MediaJobOut,
    MediaJobPage,
    MediaPolicy,
)
from src.config.security import service_auth
from src.modules.media.downloads.interfaces import (
    IMediaCommands,
    IMediaJobService,
    IMediaQueries,
)
from src.shared.errors import forbidden


def media_user(x_portal_owner: int = Header(gt=0)) -> int:
    return x_portal_owner


router = APIRouter(
    prefix="/internal/media",
    tags=["Media"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.get("/policy", response_model=APIResponse[MediaPolicy, None])
async def policy(
    policy: FromDishka[MediaPolicy],
) -> APIResponse[MediaPolicy, None]:
    return APIResponse.from_data(policy)


@router.post("/jobs", response_model=APIResponse[MediaAccepted, None])
async def create(
    data: MediaCreate,
    commands: FromDishka[IMediaCommands],
    owner_id: int = Depends(media_user),
) -> APIResponse[MediaAccepted, None]:
    if data.owner_id != owner_id:
        raise forbidden()
    result = await commands.accept(data)
    return APIResponse.from_data(result)


@router.get("/jobs", response_model=APIResponse[MediaJobPage, None])
async def page(
    queries: FromDishka[IMediaQueries],
    owner_id: int = Depends(media_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(5, ge=1, le=50),
) -> APIResponse[MediaJobPage, None]:
    result = await queries.page(owner_id, page, per_page)
    return APIResponse.from_data(result)


@router.get("/jobs/{id:int}", response_model=APIResponse[MediaJobOut, None])
async def get(
    id: int,
    jobs: FromDishka[IMediaJobService],
    owner_id: int = Depends(media_user),
) -> APIResponse[MediaJobOut, None]:
    result = await jobs.get(id, owner_id)
    return APIResponse.from_data(result)


@router.get(
    "/jobs/{id:int}/items", response_model=APIResponse[MediaItemPage, None]
)
async def items(
    id: int,
    queries: FromDishka[IMediaQueries],
    owner_id: int = Depends(media_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
) -> APIResponse[MediaItemPage, None]:
    result = await queries.items(id, owner_id, page, per_page)
    return APIResponse.from_data(result)


@router.post(
    "/jobs/{id:int}/cancel", response_model=APIResponse[MediaJobOut, None]
)
async def cancel(
    id: int,
    commands: FromDishka[IMediaCommands],
    owner_id: int = Depends(media_user),
) -> APIResponse[MediaJobOut, None]:
    result = await commands.cancel(id, owner_id)
    return APIResponse.from_data(result)


@router.post(
    "/authorize-file", response_model=APIResponse[MediaFileAuthorization, None]
)
async def authorize(
    data: MediaFileDelivery,
    queries: FromDishka[IMediaQueries],
    owner_id: int = Depends(media_user),
) -> APIResponse[MediaFileAuthorization, None]:
    if data.owner_id != owner_id:
        raise forbidden()
    result = await queries.authorize_file(data)
    return APIResponse.from_data(MediaFileAuthorization(authorized=result))
