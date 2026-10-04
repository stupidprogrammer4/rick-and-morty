from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from papilio.api.responses.envelope import APIResponse

from portal_contracts.missions import (
    MissionAccepted,
    MissionCreate,
    MissionOut,
    MissionPage,
    PageRequest,
)
from src.config.security import owner_auth, service_auth
from src.modules.automation.missions.interfaces import (
    IMissionAdmission,
    IMissionService,
)

router = APIRouter(
    prefix="/internal/missions",
    tags=["Missions"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.post("", response_model=APIResponse[MissionAccepted, None])
async def create(
    data: MissionCreate,
    admission: FromDishka[IMissionAdmission],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[MissionAccepted, None]:
    if data.owner_id != owner_id:
        from src.shared.errors import forbidden

        raise forbidden()
    result = await admission.accept(data)
    return APIResponse.from_data(result)


@router.get("", response_model=APIResponse[MissionPage, None])
async def page(
    data: Annotated[PageRequest, Query()],
    service: FromDishka[IMissionService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[MissionPage, None]:
    result = await service.page(owner_id, data)
    return APIResponse.from_data(result)


@router.get("/{id:int}", response_model=APIResponse[MissionOut, None])
async def get(
    id: int,
    service: FromDishka[IMissionService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[MissionOut, None]:
    result = await service.get(id, owner_id)
    return APIResponse.from_data(result)


@router.post("/{id:int}/cancel", response_model=APIResponse[MissionOut, None])
async def cancel(
    id: int,
    service: FromDishka[IMissionService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[MissionOut, None]:
    result = await service.cancel(id, owner_id)
    return APIResponse.from_data(result)
