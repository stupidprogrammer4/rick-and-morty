from copy import deepcopy
from typing import Any


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt the native tool schema to Groq's strict JSON subset."""
    result = deepcopy(schema)
    pending: list[Any] = [result]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            pending.extend(node.values())
        if isinstance(node, list):
            pending.extend(node)
    return result
