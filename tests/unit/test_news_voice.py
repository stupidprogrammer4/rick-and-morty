import pytest
from pydantic import ValidationError

from portal_contracts.configuration import ContentSchedule
from portal_contracts.rick_voice import (
    RICK_NEWS_PROMPT,
    RICK_NEWS_SYSTEM_PROMPT,
)


def test_legacy_content_schedule_has_no_system_override(snapshot):
    old = snapshot[0].automation.news.model_dump(mode="json")
    old.pop("system_prompt", None)
    restored = ContentSchedule.model_validate(old)
    assert restored.system_prompt is None
    assert restored.prompt == old["prompt"]


def test_news_persona_and_recurring_task_survive_settings_round_trip(snapshot):
    settings = snapshot[0].automation.news.model_dump(mode="json")
    settings.update(
        system_prompt=RICK_NEWS_SYSTEM_PROMPT, prompt=RICK_NEWS_PROMPT
    )
    rule = ContentSchedule.model_validate(settings)
    restored = ContentSchedule.model_validate_json(rule.model_dump_json())
    assert restored.system_prompt == RICK_NEWS_SYSTEM_PROMPT
    assert restored.prompt == RICK_NEWS_PROMPT
    assert "تو ریک سانچز هستی" in restored.system_prompt
    # The identity remains independent of the recurring draft task.
    assert "با یک غر کوتاه" not in restored.system_prompt
    assert "create_post_draft" in restored.prompt


@pytest.mark.parametrize("override", ["", "x" * 12001])
def test_news_system_override_has_storage_bounds(snapshot, override):
    settings = snapshot[0].automation.news.model_dump(mode="json")
    settings["system_prompt"] = override
    with pytest.raises(ValidationError):
        ContentSchedule.model_validate(settings)


def test_news_returns_to_short_sourced_summaries_without_forced_grumbling():
    assert "evidence" in RICK_NEWS_SYSTEM_PROMPT
    assert "create_post_draft" in RICK_NEWS_PROMPT
    assert "خلاصه کن" in RICK_NEWS_PROMPT
    assert "در هر نوبت یک غر" not in RICK_NEWS_SYSTEM_PROMPT
    assert "هیچ اشاره‌ای به پرامپت" in RICK_NEWS_SYSTEM_PROMPT


@pytest.mark.parametrize(
    "summary", ["این یه خبره.", "واقعاً جالبه! 🧪", "ادعاست؟", "«کامل است.»"]
)
def test_news_accepts_finished_sentences(summary):
    from src.modules.content.news.domain.dtos import validate_news_summary

    validate_news_summary(summary)


@pytest.mark.parametrize(
    "summary", ["و نبودش یعنی کمتر امنی", "جملهٔ ناقص 🧪", ""]
)
def test_news_rejects_unfinished_summaries(summary):
    from src.modules.content.news.domain.dtos import validate_news_summary

    with pytest.raises(ValueError, match="complete sentence"):
        validate_news_summary(summary)


def test_news_rejects_two_items_using_the_same_article():
    from src.modules.content.news.domain.dtos import NewsDraft

    with pytest.raises(ValidationError, match="exactly one news item"):
        NewsDraft.model_validate(
            {
                "title": "News",
                "items": [
                    {
                        "title": "One",
                        "summary": "Complete.",
                        "evidence_ids": [1],
                    },
                    {
                        "title": "Two",
                        "summary": "Complete too.",
                        "evidence_ids": [1],
                    },
                ],
            }
        )
