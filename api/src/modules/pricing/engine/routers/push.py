from fastapi import APIRouter, Depends

from src.config.security import owner_auth, service_auth
from src.modules.pricing.engine.domain.push import SupplierPricePush
from src.modules.pricing.engine.tasks.schedulers.price import (
    PersistSupplierPrice,
)

router = APIRouter(
    prefix="/internal/pricing",
    tags=["Supplier prices"],
    dependencies=[Depends(service_auth), Depends(owner_auth)],
)


@router.post("/supplier-prices", status_code=202)
async def push_price(data: SupplierPricePush) -> dict[str, bool]:
    """Queue a timestamped supplier quote in rials."""
    await PersistSupplierPrice.enqueue(data=data.model_dump(mode="json"))
    return {"queued": True}
