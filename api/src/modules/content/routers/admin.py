from typing import Annotated
from uuid import uuid4

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Header, Query
from papilio.api.responses.envelope import APIResponse

from portal_contracts.content import (
    DraftCreate,
    DraftDecision,
    DraftEdit,
    DraftOut,
    DraftPage,
)
from portal_contracts.enums import BotRole
from portal_contracts.missions import PageRequest
from src.config.security import owner_auth, service_auth
from src.modules.content.interfaces import IDraftAdmission, IDraftService

router = APIRouter(
    prefix="/internal/drafts",
    tags=["Drafts"],
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.post("", response_model=APIResponse[DraftOut, None])
async def create(
    data: DraftCreate,
    admission: FromDishka[IDraftAdmission],
    x_portal_bot: BotRole = Header(),
    x_idempotency_key: str = Header(default=""),
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftOut, None]:
    key = f"manual:{owner_id}:{x_portal_bot}:{x_idempotency_key or uuid4()}"
    if len(key) > 96:
        from src.shared.errors import conflict

        raise conflict("کلید درخواست طولانی است.")
    result = await admission.create_manual(owner_id, x_portal_bot, data, key)
    return APIResponse.from_data(result)


@router.get("", response_model=APIResponse[DraftPage, None])
async def page(
    data: Annotated[PageRequest, Query()],
    service: FromDishka[IDraftService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftPage, None]:
    result = await service.page(owner_id, data)
    return APIResponse.from_data(result)


@router.get("/{id:int}", response_model=APIResponse[DraftOut, None])
async def get(
    id: int,
    service: FromDishka[IDraftService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftOut, None]:
    result = await service.get(id, owner_id)
    return APIResponse.from_data(result)


@router.patch("/{id:int}", response_model=APIResponse[DraftOut, None])
async def edit(
    id: int,
    data: DraftEdit,
    service: FromDishka[IDraftService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftOut, None]:
    result = await service.edit(id, owner_id, data)
    return APIResponse.from_data(result)


@router.post("/{id:int}/approve", response_model=APIResponse[DraftOut, None])
async def approve(
    id: int,
    data: DraftDecision,
    service: FromDishka[IDraftService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftOut, None]:
    result = await service.decide(id, owner_id, data, approve=True)
    return APIResponse.from_data(result)


@router.post("/{id:int}/reject", response_model=APIResponse[DraftOut, None])
async def reject(
    id: int,
    data: DraftDecision,
    service: FromDishka[IDraftService],
    owner_id: int = Depends(owner_auth),
) -> APIResponse[DraftOut, None]:
    result = await service.decide(id, owner_id, data, approve=False)
    return APIResponse.from_data(result)
