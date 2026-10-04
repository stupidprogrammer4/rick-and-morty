from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse

from src.config.security import owner_auth, service_auth
from src.modules.ops.status.domain.dtos import PortalStatus
from src.modules.ops.status.interfaces import IPortalStatusQuery

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
