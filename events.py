from typing import Any, Dict, Optional


def make_event(
    event_type: str,
    *,
    conversation_id: Optional[str] = None,
    agent: str = "coordinator",
    message: str = "",
    payload: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "type": event_type,
        "agent": agent,
        "message": message,
        "payload": payload or {},
    }
    if conversation_id:
        event["conversation_id"] = conversation_id
    event.update(extra)
    return event
