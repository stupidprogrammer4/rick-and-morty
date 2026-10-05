import json
from pathlib import Path

import pytest

from src.modules.ops.settings.domain.dtos import ConfigurationSeed


@pytest.fixture
def seed() -> ConfigurationSeed:
    return ConfigurationSeed.model_validate_json(
        Path("api/seeds/defaults.json").read_text()
    )


@pytest.fixture
def snapshot(seed):
    from portal_contracts.configuration import (
        AIModelPolicy,
        AutomationPolicy,
        EffectivePortalPolicy,
        MarketPolicy,
        PortalConfiguration,
    )
    from portal_contracts.presentation import PortalPresentation
    from src.modules.pricing.reports.domain.dtos import PriceMapping

    values = {
        (item.key, item.scope.value): json.loads(item.value)
        for item in seed.values
    }
    configuration = PortalConfiguration(
        portal=EffectivePortalPolicy(
            **values["portal.policy", "global"], dry_run=True
        ),
        ai=AIModelPolicy(**values["ai.model", "global"]),
        market=MarketPolicy(**values["market.policy", "global"]),
        automation=AutomationPolicy(**values["automation.policy", "global"]),
    )
    presentation = PortalPresentation(
        **values["presentation", "global"],
        voices={role: values["voice", role] for role in ("rick", "morty")},
        posts={
            category: values["post.style", category]
            for category in (
                "news",
                "tech",
                "market",
                "music",
                "notice",
                "charts",
            )
        },
    )
    mapping = PriceMapping(
        allowed_hosts=configuration.market.allowed_hosts,
        quotes=[
            values["market.quote", symbol]
            for symbol in ("gold", "usd", "silver")
        ],
    )
    return configuration, presentation, mapping
