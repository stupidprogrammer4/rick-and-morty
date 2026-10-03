from papilio.infra.db.schema.entity import BaseEntity

from src.modules.pricing.sources.domain.enums import SourceCode


class LoginContext(BaseEntity):
    code: SourceCode
    id: int
    auth_credentials: dict[str, str]
    login: dict
