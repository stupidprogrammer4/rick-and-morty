from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from portal_contracts.content import PauseChange
from src.config.security import owner_auth, service_auth
from src.modules.ops.domain.dtos import PortalStatus
from src.modules.ops.interfaces import IPortalGuard, IPortalStatusQuery

router = APIRouter(route_class=DishkaRoute, tags=["Operations"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get(
    "/internal/status",
    dependencies=[Depends(service_auth), Depends(owner_auth)],
    response_model=APIResponse[PortalStatus, None],
)
async def status(
    query: FromDishka[IPortalStatusQuery],
) -> APIResponse[PortalStatus, None]:
    result = await query.get()
    return APIResponse.from_data(result)


@router.put(
    "/internal/pause",
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)
async def pause(
    data: PauseChange,
    service: FromDishka[IPortalGuard],
) -> APIResponse[PauseChange, None]:
    await service.pause(data.paused)
    return APIResponse.from_data(data)
