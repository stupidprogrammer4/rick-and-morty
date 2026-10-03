from portal_contracts.configuration import (
    AIModelPolicy,
    EffectivePortalPolicy,
    MarketPolicy,
    PortalConfiguration,
    PortalPolicy,
    SettingKey,
    SettingScope,
    SettingValueOut,
)
from portal_contracts.enums import BotRole, Category
from portal_contracts.presentation import (
    PortalPresentation,
    PostStyle,
    PresentationSettings,
    VoiceProfile,
)
from src.config.settings import PortalAppSettings
from src.modules.configuration.domain.dtos import (
    ConfigurationSnapshot,
    NewsSourceCatalog,
    NewsSourcePage,
)
from src.modules.configuration.infra.readers import ConfigurationReader
from src.modules.market.domain.dtos import PriceMapping, QuoteMapping
from src.modules.news.domain.dtos import NewsSource
from src.shared.errors import conflict


class ConfigurationQueries:
    def __init__(
        self, reader: ConfigurationReader, settings: PortalAppSettings
    ):
        self.reader = reader
        self.runtime = settings

    async def editable(self) -> list[SettingValueOut]:
        rows = await self.reader.settings()
        return rows

    async def sources(self, page: int, per_page: int) -> NewsSourcePage:
        result = await self.reader.sources(page, per_page)
        return result

    async def news_catalog(self) -> NewsSourceCatalog:
        result = await self.reader.sources(1, 100, enabled_only=True)
        if result.total > 100:
            raise conflict("حداکثر ۱۰۰ منبع فعال قابل استفاده است.")
        return NewsSourceCatalog(
            sources=[
                NewsSource(
                    id=row.code,
                    kind=row.kind,
                    feed_url=row.feed_url,
                    enabled=row.enabled,
                    **row.options.model_dump(),
                )
                for row in result.items
            ]
        )

    async def snapshot(self) -> ConfigurationSnapshot:
        rows = await self.reader.settings()
        values = {(row.key, row.scope): row.value for row in rows}

        def value(
            key: SettingKey, scope: SettingScope = SettingScope.GLOBAL
        ) -> str:
            found = values.get((key, scope))
            if found is None:
                raise conflict(
                    f"تنظیمات {key}/{scope} موجود نیست؛ seed را اجرا کن."
                )
            return found

        portal = PortalPolicy.model_validate_json(value(SettingKey.PORTAL))
        ai = AIModelPolicy.model_validate_json(value(SettingKey.AI))
        if ai.mode == "fake" and not self.runtime.portal.dry_run:
            raise conflict("مدل آزمایشی نیاز به dry_run دارد.")
        market = MarketPolicy.model_validate_json(value(SettingKey.MARKET))
        common = PresentationSettings.model_validate_json(
            value(SettingKey.PRESENTATION)
        )
        voices = {
            role: VoiceProfile.model_validate_json(
                value(SettingKey.VOICE, SettingScope(role.value))
            )
            for role in BotRole
        }
        posts = {
            category: PostStyle.model_validate_json(
                value(SettingKey.POST, SettingScope(category.value))
            )
            for category in Category
        }
        quotes = [
            QuoteMapping.model_validate_json(value(SettingKey.QUOTE, scope))
            for scope in (
                SettingScope.GOLD,
                SettingScope.USD,
                SettingScope.SILVER,
            )
        ]
        return ConfigurationSnapshot(
            configuration=PortalConfiguration(
                portal=EffectivePortalPolicy(
                    **portal.model_dump(), dry_run=self.runtime.portal.dry_run
                ),
                ai=ai,
                market=market,
            ),
            presentation=PortalPresentation(
                **common.model_dump(), voices=voices, posts=posts
            ),
            prices=PriceMapping(
                allowed_hosts=market.allowed_hosts, quotes=quotes
            ),
        )
