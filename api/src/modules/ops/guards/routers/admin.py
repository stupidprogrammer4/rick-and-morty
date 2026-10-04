from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from portal_contracts.content import PauseChange
from src.config.security import owner_auth, service_auth
from src.modules.ops.guards.interfaces import IPortalGuard

router = APIRouter(route_class=DishkaRoute, tags=["Operations"])


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
