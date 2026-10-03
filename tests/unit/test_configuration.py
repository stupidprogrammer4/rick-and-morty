import json

import pytest
from papilio.errors.exceptions import ValidationException
from pydantic import ValidationError

from portal_bots.app.voice import BotVoice
from portal_contracts.configuration import SettingKey, SettingScope
from portal_contracts.enums import BotRole
from portal_contracts.presentation import VoiceProfile
from src.modules.configuration.app.validation import SettingValueValidator
from src.modules.publishing.app.renderer import PostRenderer


def test_seed_has_complete_validated_scopes(seed):
    validator = SettingValueValidator()
    identities = {(item.key, item.scope) for item in seed.values}
    assert len(identities) == len(seed.values)
    assert {item.key for item in seed.definitions} == set(SettingKey)
    for item in seed.values:
        normalized = validator.validate(
            SettingKey(item.key), item.scope, item.value
        )
        assert json.loads(normalized) == json.loads(item.value)


def test_wrong_setting_scope_is_rejected(seed):
    value = next(item.value for item in seed.values if item.key == "ai.model")
    with pytest.raises(ValidationException):
        SettingValueValidator().validate(
            SettingKey.AI, SettingScope.RICK, value
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("accepted", "{id.__class__}"),
        ("error", "{secret}"),
        ("welcome", "{id}"),
        ("failed", "{detail:10000000}"),
    ],
)
def test_voice_placeholders_cannot_access_objects(snapshot, field, value):
    profile = snapshot[1].voices[BotRole.RICK].model_dump()
    profile[field] = value
    with pytest.raises(ValidationError):
        VoiceProfile.model_validate(profile)


def test_changed_database_voice_and_post_style_are_consumed(snapshot):
    presentation = snapshot[1].model_copy(deep=True)
    presentation.voices[BotRole.MORTY].accepted = "Updated #{id} 👀"
    presentation.posts["news"].heading = "Updated news 🧪"
    assert (
        BotVoice(presentation).accepted(BotRole.MORTY, 17) == "Updated #17 👀"
    )
    rendered = PostRenderer(presentation).render("<unsafe>", "A & B", "news")
    assert "Updated news 🧪" in rendered
    assert "&lt;unsafe&gt;" in rendered
    assert "A &amp; B" in rendered
    assert "<unsafe>" not in rendered


def test_rendered_post_limit_includes_headers_and_footer(snapshot):
    presentation = snapshot[1].model_copy(deep=True)
    presentation.maximum_post_characters = 200
    with pytest.raises(ValueError):
        PostRenderer(presentation).render("title", "body " * 60, "news")
