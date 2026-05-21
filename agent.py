import json
import time
from typing import Any, Dict, Iterator, List, Optional

from agent_shared import (
    answer_step_dict,
    chunk_text,
    clean_final_answer,
    compact_game_observation,
    dedupe_repeated_answer,
    extract_game_id,
    extract_quoted_final_answer,
    is_gomoku_board_line,
    is_gomoku_key_segment,
    is_gomoku_noise_segment,
    looks_like_interactive_gomoku_answer,
    parse_json,
    sanitize_interactive_gomoku_answer,
    step_to_dict,
    strip_meta_answer,
)
from agent_types import AgentResult, AgentStep
from config import get_settings
from llm_client import LLMClient, LLMEmptyResponseError
from memory import ConversationMemory
from memory_store import MemoryStore
from multi_agent import AgentCoordinator
from prompts import ANSWER_PROMPT
from tools import run_tool


class MiniReActAgent:
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        memory: Optional[ConversationMemory] = None,
        conversation_id: str = "",
        multi_agent_enabled: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        self.max_steps = settings.max_steps
        self.llm = llm or LLMClient()
        self.memory = memory or ConversationMemory(
            max_messages=settings.memory_max_messages,
            max_chars=settings.memory_max_chars,
        )
        self.settings = settings
        self.multi_agent_enabled = settings.multi_agent_enabled if multi_agent_enabled is None else bool(multi_agent_enabled)
        self.conversation_id = conversation_id
        self.memory_store = MemoryStore(settings.long_term_memory_path) if settings.long_term_memory_enabled else None
        self.coordinator = AgentCoordinator(
            self.llm,
            self.memory,
            conversation_id=conversation_id,
            memory_store=self.memory_store,
        )

    def run(self, user_input: str) -> AgentResult:
        final_result = None
        for event in self.run_events(user_input):
            if event["type"] == "done":
                final_result = event["result"]
        if final_result is None:
            return AgentResult(final_answer="任务没有返回结果。")
        return final_result

    def run_events(self, user_input: str) -> Iterator[Dict[str, Any]]:
        if self.multi_agent_enabled:
            yield from self.coordinator.run_events(user_input)
            return

        yield from self._legacy_run_events(user_input)

    def _legacy_run_events(self, user_input: str) -> Iterator[Dict[str, Any]]:
        self.memory.add_user(user_input)
        steps: List[AgentStep] = []

        for step_index in range(1, self.max_steps + 1):
            yield {
                "type": "status",
                "message": f"第 {step_index} 轮：正在让模型判断下一步该怎么做。",
            }
            try:
                raw_output = yield from self._stream_legacy_decision(step_index)
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
                draft_answer = self._clean_final_answer(str(parsed["final_answer"]))
                step = AgentStep(
                    index=step_index,
                    thought=thought,
                    final_answer=draft_answer,
                    raw_output=raw_output,
                )
                steps.append(step)
                yield {"type": "step", "step": self._step_to_dict(step)}
                final_answer = yield from self._stream_legacy_final_answer(user_input, steps, draft_answer)
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

    def _stream_legacy_decision(self, step_index: int) -> Iterator[Dict[str, Any]]:
        messages = self.memory.get_messages()
        content_chunks: List[str] = []
        emitted_reasoning = False

        if hasattr(self.llm, "chat_stream_events"):
            try:
                for event in self.llm.chat_stream_events(messages):
                    kind = str(event.get("kind", "")).strip()
                    delta = str(event.get("delta", ""))
                    if not delta:
                        continue
                    if kind == "reasoning":
                        emitted_reasoning = True
                        yield {
                            "type": "reasoning_delta",
                            "agent": "legacy",
                            "message": f"第 {step_index} 轮：模型正在思考。",
                            "payload": {"stage": "legacy_decision", "delta": delta, "step_index": step_index},
                            "delta": delta,
                        }
                    elif kind == "content":
                        content_chunks.append(delta)
            except Exception:
                content_chunks = []
                emitted_reasoning = False

        if emitted_reasoning:
            yield {
                "type": "reasoning_done",
                "agent": "legacy",
                "message": f"第 {step_index} 轮：模型已形成当前决策。",
                "payload": {"stage": "legacy_decision", "step_index": step_index},
            }

        content = "".join(content_chunks).strip()
        if content:
            return content
        return self.llm.chat(messages)

    def _stream_legacy_final_answer(
        self,
        user_input: str,
        steps: List[AgentStep],
        draft_answer: str,
    ) -> Iterator[Dict[str, Any]]:
        if not self.settings.final_answer_streaming:
            return draft_answer

        if draft_answer:
            for delta in self._chunk_text(draft_answer):
                yield {
                    "type": "answer_delta",
                    "agent": "answer",
                    "message": "最终回答生成中。",
                    "payload": {"delta": delta},
                    "delta": delta,
                }
                time.sleep(0.025)
            return draft_answer

        messages = [
            {"role": "system", "content": ANSWER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"用户任务：{user_input}\n\n"
                    f"Agent 草稿答案：{draft_answer}\n\n"
                    f"执行步骤：{json.dumps([self._answer_step_dict(step) for step in steps], ensure_ascii=False)}"
                ),
            },
        ]
        chunks: List[str] = []
        try:
            for delta in self.llm.chat_stream(messages):
                chunks.append(delta)
                yield {
                    "type": "answer_delta",
                    "agent": "answer",
                    "message": "最终回答生成中。",
                    "payload": {"delta": delta},
                    "delta": delta,
                }
        except Exception:
            return draft_answer

        final_answer = "".join(chunks).strip()
        return self._clean_final_answer(final_answer) or draft_answer

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

        if action.startswith("game_"):
            return f"棋局工具已返回结果：\n{MiniReActAgent._compact_game_observation(action, observation)}"

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
    def _compact_game_observation(action: str, observation: str) -> str:
        return compact_game_observation(action, observation)

    @staticmethod
    def _step_to_dict(step: AgentStep) -> Dict[str, Any]:
        return step_to_dict(step, MiniReActAgent._natural_step_summary)

    @staticmethod
    def _answer_step_dict(step: AgentStep) -> Dict[str, Any]:
        return answer_step_dict(step, MiniReActAgent._natural_step_summary)

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
            "game_create": "创建五子棋",
            "game_player_move": "玩家落子",
            "game_ai_move": "AI 下棋",
            "game_analyze": "棋局复盘",
            "game_moves": "棋谱序列",
            "game_resign": "提前退出棋局",
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
        if action == "game_create":
            size = action_input.get("size", 9)
            return f"创建 {size}x{size} 五子棋"
        if action == "game_player_move":
            row = action_input.get("row")
            col = action_input.get("col")
            return f"玩家落子 row={row}, col={col}"
        if action == "game_ai_move":
            game_id = str(action_input.get("game_id", "")).strip()
            return f"为棋局 {game_id or '当前棋局'} 搜索下一步"
        if action == "game_analyze":
            return "分析当前棋局"
        if action == "game_moves":
            return "列出当前棋局的落子序列"
        if action == "game_resign":
            return "结束当前棋局"
        return ""

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        return parse_json(text)

    @staticmethod
    def _chunk_text(text: str) -> Iterator[str]:
        yield from chunk_text(text)

    @classmethod
    def _clean_final_answer(cls, text: str) -> str:
        return clean_final_answer(text)

    @staticmethod
    def _sanitize_interactive_gomoku_answer(text: str) -> str:
        return sanitize_interactive_gomoku_answer(text)

    @staticmethod
    def _looks_like_interactive_gomoku_answer(text: str) -> bool:
        return looks_like_interactive_gomoku_answer(text)

    @staticmethod
    def _extract_game_id(text: str) -> str:
        return extract_game_id(text)

    @staticmethod
    def _is_gomoku_board_line(line: str) -> bool:
        return is_gomoku_board_line(line)

    @staticmethod
    def _is_gomoku_noise_segment(text: str) -> bool:
        return is_gomoku_noise_segment(text)

    @staticmethod
    def _is_gomoku_key_segment(text: str) -> bool:
        return is_gomoku_key_segment(text)

    @staticmethod
    def _extract_quoted_final_answer(text: str) -> str:
        return extract_quoted_final_answer(text)

    @staticmethod
    def _strip_meta_answer(text: str) -> str:
        return strip_meta_answer(text)

    @staticmethod
    def _dedupe_repeated_answer(text: str) -> str:
        return dedupe_repeated_answer(text)
