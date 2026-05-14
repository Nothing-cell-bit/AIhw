from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from agent_types import AgentResult, AgentStep
from config import get_settings
from events import make_event
from llm_client import LLMClient, LLMEmptyResponseError
from memory import ConversationMemory
from memory_store import MemoryExtractor, MemoryStore, format_memories_for_prompt
from prompts import ANSWER_PROMPT, EXECUTOR_PROMPT, PLANNER_PROMPT
from tools import run_tool


@dataclass
class PlanStep:
    id: int
    description: str
    tool: str = "none"
    tool_input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskPlan:
    thought: str
    goal: str
    steps: List[PlanStep]
    success_criteria: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thought": self.thought,
            "goal": self.goal,
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "tool": step.tool,
                    "tool_input": step.tool_input,
                }
                for step in self.steps
            ],
            "success_criteria": self.success_criteria,
            "risks": self.risks,
        }


class PlannerAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def plan(self, user_input: str, context: str = "") -> TaskPlan:
        messages = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": self._build_user_prompt(user_input, context)},
        ]
        raw_output = self.llm.chat(messages)
        parsed = _parse_json(raw_output)
        if not parsed:
            return TaskPlan(
                thought="规划 Agent 没有返回合法 JSON，使用单步兜底计划。",
                goal=user_input,
                steps=[PlanStep(id=1, description=user_input, tool="none")],
                raw_output=raw_output,
            )

        steps = []
        for index, item in enumerate(parsed.get("steps") or [], 1):
            if not isinstance(item, dict):
                continue
            tool_input = item.get("tool_input", {})
            steps.append(
                PlanStep(
                    id=int(item.get("id") or index),
                    description=str(item.get("description") or user_input),
                    tool=str(item.get("tool") or "none"),
                    tool_input=tool_input if isinstance(tool_input, dict) else {},
                )
            )

        if not steps:
            steps = [PlanStep(id=1, description=user_input, tool="none")]

        return TaskPlan(
            thought=str(parsed.get("thought", "")),
            goal=str(parsed.get("goal") or user_input),
            steps=steps,
            success_criteria=[str(item) for item in parsed.get("success_criteria", []) if item],
            risks=[str(item) for item in parsed.get("risks", []) if item],
            raw_output=raw_output,
        )

    @staticmethod
    def _build_user_prompt(user_input: str, context: str) -> str:
        parts = []
        if context:
            parts.append(context)
        parts.append(f"用户任务：{user_input}")
        return "\n\n".join(parts)


class ExecutorAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def execute_events(
        self,
        plan: TaskPlan,
        user_input: str,
        memory: ConversationMemory,
        *,
        max_steps: int,
    ) -> Iterator[Dict[str, Any]]:
        executed = 0
        for plan_step in plan.steps:
            if executed >= max_steps:
                yield make_event(
                    "error",
                    agent="executor",
                    message="执行步骤达到上限，任务提前停止。",
                    payload={"needs_replan": True},
                )
                return
            executed += 1

            yield make_event(
                "status",
                agent="executor",
                message=f"执行计划步骤 {plan_step.id}：{plan_step.description}",
            )

            decision = self._decide_step(plan, plan_step, user_input, memory)
            if decision.get("needs_replan"):
                yield make_event(
                    "status",
                    agent="executor",
                    message="执行 Agent 请求重新规划。",
                    payload={"needs_replan": True, "reason": str(decision.get("reason", ""))},
                )
                return

            action = decision.get("action")
            action_input = decision.get("action_input", {})
            thought = str(decision.get("thought", ""))
            if action and action != "none":
                if not isinstance(action_input, dict):
                    action_input = {}
                yield make_event(
                    "tool_call",
                    agent="executor",
                    message=f"准备调用工具：{action}",
                    payload={"action": action, "action_input": action_input, "plan_step": plan_step.id},
                )
                observation = run_tool(str(action), action_input)
                memory.add_observation(
                    json.dumps(
                        {
                            "plan_step": plan_step.id,
                            "action": action,
                            "action_input": action_input,
                            "result": observation,
                        },
                        ensure_ascii=False,
                    )
                )
                step = AgentStep(
                    index=executed,
                    thought=thought or plan_step.description,
                    action=str(action),
                    action_input=action_input,
                    observation=observation,
                    raw_output=json.dumps(decision, ensure_ascii=False),
                )
                yield make_event(
                    "tool_result",
                    agent="executor",
                    message="工具已返回结果。",
                    payload={"observation": observation, "plan_step": plan_step.id},
                    step=_step_to_dict(step),
                )
            else:
                final_answer = str(decision.get("final_answer") or plan_step.description)
                memory.add_assistant(json.dumps({"thought": thought, "final_answer": final_answer}, ensure_ascii=False))
                step = AgentStep(
                    index=executed,
                    thought=thought or plan_step.description,
                    final_answer=final_answer,
                    raw_output=json.dumps(decision, ensure_ascii=False),
                )
                yield {"type": "step", "step": _step_to_dict(step)}

    def _decide_step(
        self,
        plan: TaskPlan,
        plan_step: PlanStep,
        user_input: str,
        memory: ConversationMemory,
    ) -> Dict[str, Any]:
        if plan_step.tool and plan_step.tool != "none":
            return {
                "thought": f"按计划执行：{plan_step.description}",
                "action": plan_step.tool,
                "action_input": plan_step.tool_input,
            }

        messages = [
            {"role": "system", "content": EXECUTOR_PROMPT},
            {
                "role": "user",
                "content": (
                    f"用户任务：{user_input}\n\n"
                    f"整体计划：{json.dumps(plan.to_dict(), ensure_ascii=False)}\n\n"
                    f"当前步骤：{json.dumps(plan_step.__dict__, ensure_ascii=False)}\n\n"
                    f"当前短期上下文：{json.dumps(memory.get_messages()[-6:], ensure_ascii=False)}"
                ),
            },
        ]
        raw_output = self.llm.chat(messages)
        parsed = _parse_json(raw_output)
        if not parsed:
            return {"thought": "执行 Agent 返回格式不可解析。", "final_answer": plan_step.description}
        return parsed


class AgentCoordinator:
    def __init__(
        self,
        llm: LLMClient,
        memory: ConversationMemory,
        *,
        conversation_id: str = "",
        memory_store: Optional[MemoryStore] = None,
    ) -> None:
        self.settings = get_settings()
        self.llm = llm
        self.memory = memory
        self.conversation_id = conversation_id
        self.memory_store = memory_store
        self.memory_extractor = MemoryExtractor(self.settings.memory_extract_importance_threshold)
        self.planner = PlannerAgent(llm)
        self.executor = ExecutorAgent(llm)

    def run_events(self, user_input: str) -> Iterator[Dict[str, Any]]:
        self.memory.add_user(user_input)
        long_term_context = self._long_term_context(user_input)

        yield make_event("status", agent="coordinator", message="正在检索记忆并规划任务。")
        plan = self.planner.plan(user_input, long_term_context)
        yield make_event("plan", agent="planner", message="规划已生成。", payload=plan.to_dict())

        streamed_steps: List[AgentStep] = []
        for event in self.executor.execute_events(
            plan,
            user_input,
            self.memory,
            max_steps=self.settings.executor_max_steps,
        ):
            if event.get("type") in {"step", "tool_result"} and event.get("step"):
                step_payload = event.get("step") or {}
                streamed_steps.append(_dict_to_step(step_payload))
            yield event

        final_answer = yield from self._stream_final_answer(user_input, plan, streamed_steps)
        self.memory.add_assistant(final_answer)
        self._save_long_term_memories(user_input, final_answer)
        yield {"type": "done", "result": AgentResult(final_answer=final_answer, steps=streamed_steps)}

    def _long_term_context(self, user_input: str) -> str:
        if not self.memory_store:
            return ""
        records = self.memory_store.search(user_input, limit=self.settings.long_term_memory_top_k)
        return format_memories_for_prompt(records)

    def _stream_final_answer(
        self,
        user_input: str,
        plan: TaskPlan,
        steps: List[AgentStep],
    ) -> Iterator[Dict[str, Any]]:
        draft_answer = _clean_final_answer(_fallback_final_answer(steps))
        if draft_answer and not any(step.observation and not step.final_answer for step in steps):
            for delta in _chunk_text(draft_answer):
                yield make_event(
                    "answer_delta",
                    agent="answer",
                    message="最终回答生成中。",
                    payload={"delta": delta},
                    delta=delta,
                )
                time.sleep(0.025)
            return draft_answer

        messages = [
            {"role": "system", "content": ANSWER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"用户任务：{user_input}\n\n"
                    f"计划：{json.dumps(plan.to_dict(), ensure_ascii=False)}\n\n"
                    f"执行步骤：{json.dumps([_step_to_dict(step) for step in steps], ensure_ascii=False)}"
                ),
            },
        ]

        chunks: List[str] = []
        if self.settings.final_answer_streaming:
            try:
                for delta in self.llm.chat_stream(messages):
                    chunks.append(delta)
                    yield make_event(
                        "answer_delta",
                        agent="answer",
                        message="最终回答生成中。",
                        payload={"delta": delta},
                        delta=delta,
                    )
            except Exception:
                chunks = []

        if not chunks:
            try:
                chunks.append(self.llm.chat(messages))
            except LLMEmptyResponseError:
                chunks.append(_fallback_final_answer(steps))

        return _clean_final_answer("".join(chunks).strip()) or draft_answer

    def _save_long_term_memories(self, user_input: str, final_answer: str) -> None:
        if not self.memory_store:
            return
        for record in self.memory_extractor.extract(user_input, final_answer, self.conversation_id):
            try:
                self.memory_store.add(**record)
            except ValueError:
                continue


def _fallback_final_answer(steps: List[AgentStep]) -> str:
    for step in reversed(steps):
        if step.final_answer:
            return step.final_answer
        if step.observation:
            return f"已完成工具调用，结果如下：\n{step.observation}"
    return "任务已处理，但没有生成可展示的最终内容。"


def _chunk_text(text: str) -> Iterator[str]:
    for match in re.finditer(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?|[\u4e00-\u9fff]|[^\S\r\n]+|[^\w\s]", text):
        yield match.group(0)


def _clean_final_answer(text: str) -> str:
    cleaned = _extract_quoted_final_answer(text) or _strip_meta_answer(text)
    return _dedupe_repeated_answer(cleaned)


def _extract_quoted_final_answer(text: str) -> str:
    patterns = [
        r"最终答案(?:就是|是|为)?[：:\s]*[\"“](.+?)[\"”]",
        r"预期的回答[：:\s]*[\"“](.+?)[\"”]",
        r"Agent\s*草稿答案(?:已经)?给出(?:了)?[：:\s]*[\"“](.+?)[\"”]",
        r"草稿答案(?:已经)?给出(?:了)?[：:\s]*[\"“](.+?)[\"”]",
        r"Agent\s*草稿答案[：:\s]*[\"“](.+?)[\"”]",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.S)
        if matches:
            return matches[-1].strip()
    return ""


def _strip_meta_answer(text: str) -> str:
    markers = ["所以回复用户即可。", "所以回复用户即可：", "所以回答：", "回答：", "最终答案：", "预期的回答："]
    cleaned = text.strip()
    for marker in markers:
        index = cleaned.rfind(marker)
        if index != -1:
            return cleaned[index + len(marker) :].strip()
    return cleaned


def _dedupe_repeated_answer(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    normalized = cleaned.replace(" ", "")
    if len(normalized) % 2 == 0:
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            return cleaned[: len(cleaned) // 2].strip()

    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", cleaned)
    if len(sentences) >= 2 and len(sentences) % 2 == 0:
        half = len(sentences) // 2
        left = "".join(sentences[:half]).strip()
        right = "".join(sentences[half:]).strip()
        if left and left == right:
            return left

    return cleaned


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def _step_to_dict(step: AgentStep) -> Dict[str, Any]:
    return {
        "index": step.index,
        "thought": step.thought,
        "action": step.action,
        "action_input": step.action_input,
        "observation": step.observation,
        "final_answer": step.final_answer,
        "summary": _natural_step_summary(step),
    }


def _dict_to_step(payload: Dict[str, Any]) -> AgentStep:
    return AgentStep(
        index=int(payload.get("index") or 0),
        thought=str(payload.get("thought") or ""),
        action=payload.get("action"),
        action_input=payload.get("action_input"),
        observation=payload.get("observation"),
        final_answer=payload.get("final_answer"),
    )


def _natural_step_summary(step: AgentStep) -> str:
    if step.final_answer:
        return "执行 Agent 得到了阶段性结论。"
    if step.action:
        return f"执行 Agent 调用了工具 {step.action}，并拿到了观察结果。"
    if step.observation:
        return f"执行过程返回观察结果：{step.observation}"
    return "执行 Agent 完成了一个计划步骤。"
