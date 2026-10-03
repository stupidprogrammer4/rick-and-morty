from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.sources.domain.enums import (
    ErrorType,
    SourceCode,
    SourceSwitch,
    SourceUpdateType,
)

router = APIRouter(
    prefix="/internal/pricing/panel/sources",
    tags=["Panel Sources"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.get(
    "/enums",
    response_model=EnumsResponse,
)
async def get_source_enums() -> EnumsResponse:
    """
    List the enums this panel offers — the markets, how a source is read, and
    the kinds of error it can report.
    """
    groups = EnumGroupOut.of(
        [
            ErrorType,
            SourceCode,
            SourceSwitch,
            SourceUpdateType,
        ]
    )
    return APIResponse.from_data(groups)
