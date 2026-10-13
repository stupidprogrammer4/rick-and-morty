from amupouya_calendar.models import OccasionDay
from pydantic import ValidationError

from src.modules.automation.agents.domain.dtos import AgentHistory


def calendar_evidence(history: AgentHistory) -> OccasionDay | None:
    calls = {
        call.id
        for message in history.messages
        for call in message.tool_calls or []
        if call.function.name == "get_calendar_occasions"
    }
    for message in reversed(history.messages):
        if message.role == "tool" and message.tool_call_id in calls:
            try:
                day = OccasionDay.model_validate_json(message.content or "")
            except ValidationError:
                continue
            return day
    return None
