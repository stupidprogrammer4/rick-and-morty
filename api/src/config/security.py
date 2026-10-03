from hmac import compare_digest

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Header, HTTPException

from src.config.settings import PortalAppSettings


@inject
async def service_auth(
    settings: FromDishka[PortalAppSettings],
    authorization: str = Header(default=""),
) -> None:
    expected = "Bearer " + settings.security.service_key.get_secret_value()
    if not compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Service key required")


@inject
async def owner_auth(
    settings: FromDishka[PortalAppSettings],
    x_portal_owner: int = Header(),
) -> int:
    if x_portal_owner not in settings.security.admin_ids:
        raise HTTPException(status_code=403, detail="Owner required")
    return x_portal_owner
