import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import get_settings
from llm_client import LLMClient, LLMEmptyResponseError
from memory import ConversationMemory
from tools import run_tool


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


class MiniReActAgent:
    def __init__(self, llm: Optional[LLMClient] = None, memory: Optional[ConversationMemory] = None) -> None:
        settings = get_settings()
        self.max_steps = settings.max_steps
        self.llm = llm or LLMClient()
        self.memory = memory or ConversationMemory()

    def run(self, user_input: str) -> AgentResult:
        self.memory.add_user(user_input)
        steps: List[AgentStep] = []

        for step_index in range(1, self.max_steps + 1):
            try:
                raw_output = self.llm.chat(self.memory.get_messages())
            except LLMEmptyResponseError:
                final_answer = (
                    "模型接口这次返回了空内容，通常是服务端临时失败或安全过滤导致的。"
                    "请换一种更明确的说法重试，例如说明是在游戏、学习或软件使用场景中提问。"
                )
                steps.append(
                    AgentStep(
                        index=step_index,
                        thought="LLM API 返回空 choices",
                        final_answer=final_answer,
                    )
                )
                return AgentResult(final_answer=final_answer, steps=steps)
            self.memory.add_assistant(raw_output)
            parsed = self._parse_json(raw_output)

            if parsed is None:
                observation = "模型输出不是合法 JSON。请只输出一个 JSON 对象。"
                self.memory.add_observation(observation)
                steps.append(
                    AgentStep(
                        index=step_index,
                        thought="解析失败",
                        observation=observation,
                        raw_output=raw_output,
                    )
                )
                continue

            thought = str(parsed.get("thought", ""))

            if "final_answer" in parsed:
                final_answer = str(parsed["final_answer"])
                steps.append(
                    AgentStep(
                        index=step_index,
                        thought=thought,
                        final_answer=final_answer,
                        raw_output=raw_output,
                    )
                )
                return AgentResult(final_answer=final_answer, steps=steps)

            action = parsed.get("action")
            action_input = parsed.get("action_input", {})
            if not isinstance(action, str):
                observation = "缺少 action 字段。请输出 final_answer 或合法工具调用。"
                self.memory.add_observation(observation)
                steps.append(
                    AgentStep(
                        index=step_index,
                        thought=thought,
                        observation=observation,
                        raw_output=raw_output,
                    )
                )
                continue

            observation = run_tool(action, action_input)
            self.memory.add_observation(
                json.dumps(
                    {
                        "action": action,
                        "action_input": action_input,
                        "result": observation,
                    },
                    ensure_ascii=False,
                )
            )
            steps.append(
                AgentStep(
                    index=step_index,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation,
                    raw_output=raw_output,
                )
            )

        final_answer = "达到最大思考步数，任务尚未完成。请缩小问题范围或稍后重试。"
        return AgentResult(final_answer=final_answer, steps=steps)

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                return None
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
