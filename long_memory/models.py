from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MemoryRecord:
    id: str
    scope: str
    kind: str
    content: str
    tags: List[str]
    confidence: float
    importance: float
    source_conversation_id: str
    created_at: float
    updated_at: float
    last_accessed_at: float
    expires_at: Optional[float] = None
