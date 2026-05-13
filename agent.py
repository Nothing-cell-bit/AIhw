import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

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
        final_result = None
        for event in self.run_events(user_input):
            if event["type"] == "done":
                final_result = event["result"]
        if final_result is None:
            return AgentResult(final_answer="任务没有返回结果。")
        return final_result

    def run_events(self, user_input: str) -> Iterator[Dict[str, Any]]:
        self.memory.add_user(user_input)
        steps: List[AgentStep] = []

        for step_index in range(1, self.max_steps + 1):
            yield {
                "type": "status",
                "message": f"第 {step_index} 轮：正在让模型判断下一步该怎么做。",
            }
            try:
                raw_output = self.llm.chat(self.memory.get_messages())
            except LLMEmptyResponseError:
                final_answer = self._fallback_answer(user_input, steps)
                step = AgentStep(
                    index=step_index,
                    thought="模型接口返回空内容，使用已获得的工具观察结果兜底回答",
                    final_answer=final_answer,
                )
                steps.append(step)
                self.memory.add_assistant(
                    json.dumps(
                        {
                            "thought": "模型接口返回空内容，使用工具观察结果兜底回答",
                            "final_answer": final_answer,
                        },
                        ensure_ascii=False,
                    )
                )
                yield {"type": "step", "step": self._step_to_dict(step)}
                yield {"type": "done", "result": AgentResult(final_answer=final_answer, steps=steps)}
                return
            self.memory.add_assistant(raw_output)
            parsed = self._parse_json(raw_output)

            if parsed is None:
                observation = "模型输出不是合法 JSON。请只输出一个 JSON 对象。"
                self.memory.add_observation(observation)
                step = AgentStep(
                    index=step_index,
                    thought="模型输出格式不正确，已要求模型按 JSON 格式重试",
                    observation=observation,
                    raw_output=raw_output,
                )
                steps.append(step)
                yield {"type": "step", "step": self._step_to_dict(step)}
                continue

            thought = str(parsed.get("thought", ""))

            if "final_answer" in parsed:
                final_answer = str(parsed["final_answer"])
                step = AgentStep(
                    index=step_index,
                    thought=thought,
                    final_answer=final_answer,
                    raw_output=raw_output,
                )
                steps.append(step)
                yield {"type": "step", "step": self._step_to_dict(step)}
                yield {"type": "done", "result": AgentResult(final_answer=final_answer, steps=steps)}
                return

            action = parsed.get("action")
            action_input = parsed.get("action_input", {})
            if not isinstance(action, str):
                observation = "缺少 action 字段。请输出 final_answer 或合法工具调用。"
                self.memory.add_observation(observation)
                step = AgentStep(
                    index=step_index,
                    thought=thought or "模型没有给出可执行动作，已要求它重试",
                    observation=observation,
                    raw_output=raw_output,
                )
                steps.append(step)
                yield {"type": "step", "step": self._step_to_dict(step)}
                continue

            yield {
                "type": "status",
                "message": self._action_status(action, action_input),
            }
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
            step = AgentStep(
                index=step_index,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                raw_output=raw_output,
            )
            steps.append(step)
            yield {"type": "step", "step": self._step_to_dict(step)}

        final_answer = "达到最大思考步数，任务尚未完成。请缩小问题范围或稍后重试。"
        yield {"type": "done", "result": AgentResult(final_answer=final_answer, steps=steps)}

    @staticmethod
    def _fallback_answer(user_input: str, steps: List[AgentStep]) -> str:
        tool_steps = [step for step in steps if step.action and step.observation]
        if not tool_steps:
            return (
                "模型接口连续返回空内容，当前还没有可用的工具结果可以兜底。"
                "请稍后重试，或把问题说得更具体一些。"
            )

        last = tool_steps[-1]
        observation = last.observation or ""
        action = last.action or ""

        if observation.startswith("工具错误") or observation.startswith("工具执行失败"):
            return f"工具调用没有成功完成：{observation}"

        if action == "calculator":
            return f"计算结果是：{observation}"

        if action == "file_write":
            return observation

        if action == "file_read":
            return f"读取到的文件内容如下：\n{observation}"

        if action == "wikipedia_search":
            return MiniReActAgent._format_wikipedia_fallback(observation)

        return f"我已经拿到工具结果，但模型接口在总结时返回空内容。工具结果如下：\n{observation}"

    @staticmethod
    def _format_wikipedia_fallback(observation: str) -> str:
        title, sep, summary = observation.partition(": ")
        if sep:
            return (
                f"模型接口在总结阶段返回了空内容，我先根据工具查询结果直接回答：\n\n"
                f"{title}：{summary}"
            )
        return f"根据查询结果：{observation}"

    @staticmethod
    def _step_to_dict(step: AgentStep) -> Dict[str, Any]:
        return {
            "index": step.index,
            "thought": step.thought,
            "action": step.action,
            "action_input": step.action_input,
            "observation": step.observation,
            "final_answer": step.final_answer,
            "summary": MiniReActAgent._natural_step_summary(step),
        }

    @staticmethod
    def _natural_step_summary(step: AgentStep) -> str:
        if step.final_answer:
            return "模型已经整理出最终回答。"
        if step.action:
            tool_name = MiniReActAgent._tool_label(step.action)
            target = MiniReActAgent._action_target(step.action, step.action_input or {})
            if target:
                return f"模型决定使用{tool_name}，目标是：{target}。工具已经返回结果。"
            return f"模型决定使用{tool_name}，工具已经返回结果。"
        if step.observation:
            return f"本轮没有成功执行工具，系统反馈：{step.observation}"
        return "模型完成了一轮思考。"

    @staticmethod
    def _action_status(action: str, action_input: Dict[str, Any]) -> str:
        tool_name = MiniReActAgent._tool_label(action)
        target = MiniReActAgent._action_target(action, action_input)
        if target:
            return f"准备调用{tool_name}：{target}"
        return f"准备调用{tool_name}。"

    @staticmethod
    def _tool_label(action: str) -> str:
        labels = {
            "calculator": "计算器",
            "wikipedia_search": "维基百科搜索",
            "file_write": "本地文件写入",
            "file_read": "本地文件读取",
        }
        return labels.get(action, action)

    @staticmethod
    def _action_target(action: str, action_input: Dict[str, Any]) -> str:
        if action == "calculator":
            return str(action_input.get("expression", "")).strip()
        if action == "wikipedia_search":
            query = str(action_input.get("query", "")).strip()
            lang = str(action_input.get("lang", "")).strip()
            return f"搜索“{query}”" + (f"（{lang}）" if lang else "")
        if action in {"file_write", "file_read"}:
            return str(action_input.get("filename", "")).strip()
        return ""

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
