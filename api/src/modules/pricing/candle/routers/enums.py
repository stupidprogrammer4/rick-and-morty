from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.candle.domain.enums import TimeFrame

router = APIRouter(
    prefix="/internal/pricing/panel/candles",
    tags=["Panel Candles"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.get(
    "/enums",
    response_model=EnumsResponse,
)
async def get_candle_enums() -> EnumsResponse:
    """
    List the enums this panel offers — the time frames candles are rolled into.
    """
    groups = EnumGroupOut.of(
        [
            TimeFrame,
        ]
    )
    return APIResponse.from_data(groups)
