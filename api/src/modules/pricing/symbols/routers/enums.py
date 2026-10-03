from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Depends
from papilio.api.responses.envelope import APIResponse
from papilio.schemas.outputs import EnumGroupOut

from src.config.security import owner_auth, service_auth
from src.modules.pricing.symbols.domain.enums import (
    CurrencyType,
    SymbolCode,
)

router = APIRouter(
    prefix="/internal/pricing/panel/symbols",
    tags=["Panel Symbols"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)

EnumsResponse = APIResponse[EnumGroupOut, None]


@router.get(
    "/enums",
    response_model=EnumsResponse,
)
async def get_symbol_enums() -> EnumsResponse:
    """
    List the enums this panel offers — the symbols themselves and the
    currencies they quote in.
    """
    groups = EnumGroupOut.of(
        [
            CurrencyType,
            SymbolCode,
        ]
    )
    return APIResponse.from_data(groups)
