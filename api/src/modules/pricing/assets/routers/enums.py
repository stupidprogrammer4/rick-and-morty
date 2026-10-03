from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.assets.domain.enums import (
    AggregationType,
    AssetCode,
)

router = APIRouter(
    prefix="/internal/pricing/panel/assets",
    tags=["Panel Assets"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.get(
    "/enums",
    response_model=EnumsResponse,
)
async def get_asset_enums() -> EnumsResponse:
    """
    List the enums this panel offers — the assets themselves and the rules
    their sources are folded by.
    """
    groups = EnumGroupOut.of(
        [
            AggregationType,
            AssetCode,
        ]
    )
    return APIResponse.from_data(groups)
