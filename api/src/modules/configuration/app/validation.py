from typing import Any

from papilio.errors.exceptions import ValidationException
from pydantic import BaseModel

from portal_contracts.configuration import (
    AIModelPolicy,
    MarketPolicy,
    PortalPolicy,
    SettingKey,
    SettingScope,
)
from portal_contracts.presentation import (
    PostStyle,
    PresentationSettings,
    VoiceProfile,
)
from src.modules.market.domain.dtos import QuoteMapping


class SettingValueValidator:
    schemas: dict[SettingKey, type[BaseModel]] = {
        SettingKey.PORTAL: PortalPolicy,
        SettingKey.AI: AIModelPolicy,
        SettingKey.MARKET: MarketPolicy,
        SettingKey.PRESENTATION: PresentationSettings,
        SettingKey.VOICE: VoiceProfile,
        SettingKey.POST: PostStyle,
        SettingKey.QUOTE: QuoteMapping,
    }

    def validate(
        self, key: SettingKey, scope: SettingScope, value: str
    ) -> str:
        scopes = {SettingScope.GLOBAL}
        if key == SettingKey.VOICE:
            scopes = {SettingScope.RICK, SettingScope.MORTY}
        elif key == SettingKey.POST:
            scopes = {
                SettingScope.NEWS,
                SettingScope.TECH,
                SettingScope.MARKET,
                SettingScope.MUSIC,
                SettingScope.NOTICE,
            }
        elif key == SettingKey.QUOTE:
            scopes = {SettingScope.GOLD, SettingScope.USD, SettingScope.SILVER}
        if scope not in scopes:
            raise ValidationException(
                message="Scope does not belong to definition",
                message_code="invalid_setting_scope",
                loc=["scope"],
            )
        try:
            parsed = self.schemas[key].model_validate_json(value)
        except ValueError as exc:
            raise ValidationException(
                message="Invalid typed setting value",
                message_code="invalid_setting_value",
                loc=["value"],
            ) from exc
        if isinstance(parsed, QuoteMapping) and parsed.symbol != scope.value:
            raise ValidationException(
                message="Quote scope and symbol must match",
                message_code="invalid_quote_scope",
                loc=["scope"],
            )
        normalized = parsed.model_dump_json()
        if len(normalized.encode()) > 60000:
            raise ValidationException(
                message="Setting value is too large",
                message_code="setting_too_large",
                loc=["value"],
            )
        return normalized

    def schema(self, key: SettingKey) -> dict[str, Any]:
        return self.schemas[key].model_json_schema()
