from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentStep:
    index: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    final_answer: Optional[str] = None
    raw_output: str = ""


@dataclass
class AgentResult:
    final_answer: str
    steps: List[AgentStep] = field(default_factory=list)
