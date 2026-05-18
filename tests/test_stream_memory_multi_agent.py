import json
import os
import tempfile
import unittest
from unittest.mock import patch

from llm_client import LLMClient
from agent import MiniReActAgent
from memory import ConversationMemory
from memory_store import MemoryExtractor, MemoryStore
from multi_agent import AgentCoordinator


class FakeLLM:
    def chat(self, messages, stream=False):
        system = messages[0]["content"]
        if "规划 Agent" in system:
            return json.dumps(
                {
                    "thought": "需要计算",
                    "goal": "计算表达式",
                    "steps": [
                        {
                            "id": 1,
                            "description": "计算 2+3",
                            "tool": "calculator",
                            "tool_input": {"expression": "2+3"},
                        }
                    ],
                    "success_criteria": ["得到结果"],
                    "risks": [],
                },
                ensure_ascii=False,
            )
        return "结果是 5。"

    def chat_stream(self, messages, max_tokens=1200):
        yield "结果"
        yield "是 5。"


class FakeLegacyStreamingLLM:
    def chat(self, messages, stream=False):
        return json.dumps({"thought": "可以回答", "final_answer": "原始答案"}, ensure_ascii=False)

    def chat_stream(self, messages, max_tokens=1200):
        yield "流式"
        yield "答案"


class StreamParsingTest(unittest.TestCase):
    def test_iter_sse_deltas_extracts_content_until_done(self):
        lines = [
            "data: {\"choices\":[{\"delta\":{\"content\":\"你\"}}]}\n".encode("utf-8"),
            b"\n",
            "data: {\"choices\":[{\"delta\":{\"content\":\"好\"}}]}\n".encode("utf-8"),
            b"data: [DONE]\n",
            b"data: {\"choices\":[{\"delta\":{\"content\":\"ignored\"}}]}\n",
        ]
        self.assertEqual(list(LLMClient._iter_sse_deltas(lines)), ["你", "好"])

    def test_iter_sse_events_splits_reasoning_and_content(self):
        lines = [
            "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"先判断\"}}]}\n".encode("utf-8"),
            "data: {\"choices\":[{\"delta\":{\"content\":\"最终\"}}]}\n".encode("utf-8"),
            "data: [DONE]\n".encode("utf-8"),
        ]
        self.assertEqual(
            list(LLMClient._iter_sse_events(lines)),
            [
                {"kind": "reasoning", "delta": "先判断"},
                {"kind": "content", "delta": "最终"},
            ],
        )


class MemoryStoreTest(unittest.TestCase):
    def test_memory_store_adds_searches_and_filters_sensitive_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "memory.sqlite3"))
            memory_id = store.add(
                "以后默认使用中文回答",
                kind="preference",
                tags=["language"],
                importance=0.8,
            )
            records = store.search("中文回答")
            self.assertEqual(records[0].id, memory_id)
            with self.assertRaises(ValueError):
                store.add("api_key=secret-value")

    def test_memory_extractor_detects_stable_preference(self):
        extractor = MemoryExtractor()
        records = extractor.extract("请记住，以后默认用中文回答")
        self.assertEqual(records[0]["kind"], "preference")
        self.assertIn("中文", records[0]["content"])


class MultiAgentTest(unittest.TestCase):
    def test_coordinator_runs_planner_executor_and_streams_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "MODELSCOPE_API_KEY": "test-key",
                "MULTI_AGENT_ENABLED": "1",
                "FINAL_ANSWER_STREAMING": "1",
                "LONG_TERM_MEMORY_ENABLED": "1",
                "LONG_TERM_MEMORY_PATH": os.path.join(tmp, "memory.sqlite3"),
            }
            with patch.dict(os.environ, env, clear=False):
                memory = ConversationMemory()
                store = MemoryStore(os.environ["LONG_TERM_MEMORY_PATH"])
                coordinator = AgentCoordinator(FakeLLM(), memory, memory_store=store)
                events = list(coordinator.run_events("帮我算 2+3"))

        event_types = [event["type"] for event in events]
        self.assertIn("plan", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("answer_delta", event_types)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["result"].final_answer, "结果是 5。")

    def test_coordinator_emits_reasoning_delta_when_llm_supports_reasoning_stream(self):
        class FakeReasoningLLM(FakeLLM):
            def chat_stream_events(self, messages, max_tokens=1200):
                system = messages[0]["content"]
                if "规划 Agent" in system:
                    yield {"kind": "reasoning", "delta": "先判断是否需要计算。"}
                    yield {
                        "kind": "content",
                        "delta": json.dumps(
                            {
                                "thought": "需要计算",
                                "goal": "计算表达式",
                                "steps": [
                                    {
                                        "id": 1,
                                        "description": "计算 2+3",
                                        "tool": "calculator",
                                        "tool_input": {"expression": "2+3"},
                                    }
                                ],
                                "success_criteria": ["得到结果"],
                                "risks": [],
                            },
                            ensure_ascii=False,
                        ),
                    }

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "MODELSCOPE_API_KEY": "test-key",
                "MULTI_AGENT_ENABLED": "1",
                "FINAL_ANSWER_STREAMING": "1",
                "LONG_TERM_MEMORY_ENABLED": "1",
                "LONG_TERM_MEMORY_PATH": os.path.join(tmp, "memory.sqlite3"),
            }
            with patch.dict(os.environ, env, clear=False):
                memory = ConversationMemory()
                store = MemoryStore(os.environ["LONG_TERM_MEMORY_PATH"])
                coordinator = AgentCoordinator(FakeReasoningLLM(), memory, memory_store=store)
                events = list(coordinator.run_events("帮我算 2+3"))

        event_types = [event["type"] for event in events]
        self.assertIn("reasoning_delta", event_types)
        self.assertIn("reasoning_done", event_types)


class LegacyStreamingTest(unittest.TestCase):
    def test_legacy_agent_compacts_game_observation_for_answer_context(self):
        observation = json.dumps(
            {
                "game_id": "game-1",
                "size": 15,
                "board_label": "15x15",
                "status": "playing",
                "message": "15x15 五子棋已开始，玩家执黑先手。",
                "board": [[0] * 15 for _ in range(15)],
            },
            ensure_ascii=False,
        )
        compact = MiniReActAgent._compact_game_observation("game_create", observation)
        self.assertIn('"game_id": "game-1"', compact)
        self.assertIn('"board_label": "15x15"', compact)
        self.assertNotIn('"board"', compact)

    def test_legacy_agent_emits_reasoning_delta_when_stream_supported(self):
        class ReasoningLegacyLLM:
            def chat(self, messages, stream=False):
                return json.dumps({"thought": "可以回答", "final_answer": "后备答案"}, ensure_ascii=False)

            def chat_stream_events(self, messages, max_tokens=1200):
                yield {"kind": "reasoning", "delta": "先确认是否需要工具。"}
                yield {
                    "kind": "content",
                    "delta": json.dumps({"thought": "可以直接回答", "final_answer": "原始答案"}, ensure_ascii=False),
                }

            def chat_stream(self, messages, max_tokens=1200):
                yield "原始"
                yield "答案"

        with patch.dict(
            os.environ,
            {
                "MODELSCOPE_API_KEY": "test-key",
                "MULTI_AGENT_ENABLED": "0",
                "FINAL_ANSWER_STREAMING": "1",
            },
            clear=False,
        ):
            agent = MiniReActAgent(llm=ReasoningLegacyLLM(), memory=ConversationMemory())
            events = list(agent.run_events("直接回答"))

        event_types = [event["type"] for event in events]
        self.assertIn("reasoning_delta", event_types)
        self.assertIn("reasoning_done", event_types)
        self.assertEqual(events[-1]["result"].final_answer, "原始答案")

    def test_legacy_agent_streams_clean_draft_answer_without_second_model_pass(self):
        with patch.dict(
            os.environ,
            {
                "MODELSCOPE_API_KEY": "test-key",
                "MULTI_AGENT_ENABLED": "0",
                "FINAL_ANSWER_STREAMING": "1",
            },
            clear=False,
        ):
            agent = MiniReActAgent(llm=FakeLegacyStreamingLLM(), memory=ConversationMemory())
            events = list(agent.run_events("直接回答"))

        deltas = [event.get("delta") for event in events if event["type"] == "answer_delta"]
        self.assertEqual("".join(deltas), "原始答案")
        self.assertGreater(len(deltas), 1)
        self.assertEqual(events[-1]["result"].final_answer, "原始答案")

    def test_legacy_agent_deduplicates_repeated_draft_answer(self):
        class RepeatingLLM:
            def chat(self, messages, stream=False):
                return json.dumps(
                    {
                        "thought": "可以回答",
                        "final_answer": "你好！有什么我可以帮你的吗？你好！有什么我可以帮你的吗？",
                    },
                    ensure_ascii=False,
                )

        with patch.dict(os.environ, {"MODELSCOPE_API_KEY": "test-key", "FINAL_ANSWER_STREAMING": "1"}, clear=False):
            agent = MiniReActAgent(llm=RepeatingLLM(), memory=ConversationMemory())
            events = list(agent.run_events("你好"))

        self.assertEqual(events[-1]["result"].final_answer, "你好！有什么我可以帮你的吗？")

    def test_legacy_agent_strips_meta_reasoning_from_final_answer_field(self):
        class MetaAnswerLLM:
            def chat(self, messages, stream=False):
                return json.dumps(
                    {
                        "thought": "可以回答",
                        "final_answer": (
                            "我们被问到用户任务：\"你好\"。Agent草稿答案已经给出："
                            "\"你好！有什么我可以帮你的吗？\"。执行步骤显示不需要调用工具，直接回复问候。"
                            "最终答案就是\"你好！有什么我可以帮你的吗？\"。按照要求，直接给出结果，"
                            "不要输出JSON，说明关键依据。所以回复用户即可。你好！有什么我可以帮你的吗？"
                        ),
                    },
                    ensure_ascii=False,
                )

        with patch.dict(os.environ, {"MODELSCOPE_API_KEY": "test-key", "FINAL_ANSWER_STREAMING": "1"}, clear=False):
            agent = MiniReActAgent(llm=MetaAnswerLLM(), memory=ConversationMemory())
            events = list(agent.run_events("你好"))

        self.assertEqual(events[-1]["result"].final_answer, "你好！有什么我可以帮你的吗？")

    def test_legacy_agent_strips_draft_answer_wording_without_colon(self):
        class MetaAnswerLLM:
            def chat(self, messages, stream=False):
                return json.dumps(
                    {
                        "thought": "可以回答",
                        "final_answer": (
                            "我们被问到用户任务：hello。Agent草稿答案已经给出了"
                            "\"Hello! How can I assist you today?\"。执行步骤显示模型已经整理出最终回答。"
                            "所以直接输出这个回答即可。Hello! How can I assist you today?"
                        ),
                    },
                    ensure_ascii=False,
                )

        with patch.dict(os.environ, {"MODELSCOPE_API_KEY": "test-key", "FINAL_ANSWER_STREAMING": "1"}, clear=False):
            agent = MiniReActAgent(llm=MetaAnswerLLM(), memory=ConversationMemory())
            events = list(agent.run_events("hello"))

        deltas = [event.get("delta") for event in events if event["type"] == "answer_delta"]
        self.assertGreater(len(deltas), 3)
        self.assertEqual("".join(deltas), "Hello! How can I assist you today?")
        self.assertEqual(events[-1]["result"].final_answer, "Hello! How can I assist you today?")


if __name__ == "__main__":
    unittest.main()
