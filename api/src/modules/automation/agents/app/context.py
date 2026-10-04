from dataclasses import dataclass


@dataclass(frozen=True)
class ToolContext:
    owner_id: int
    mission_id: int
