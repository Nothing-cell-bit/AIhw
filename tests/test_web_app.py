import json
import time
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib import error, request

import web_app
from config import get_settings
from agent_types import AgentResult
from game import AI, EMPTY, HUMAN, STATUS_DRAW, STATUS_PLAYING, GAMES, new_game, store_game


class WebAppTests(unittest.TestCase):
    def test_agent_mode_selector_and_api_are_present(self):
        self.assertIn('id="agent-mode-select"', web_app.HTML)
        self.assertIn("当前会话模式", web_app.HTML)
        self.assertIn("/api/agent_mode", web_app.HTML)
        self.assertIn("function updateAgentMode()", web_app.HTML)
        self.assertIn("agentModeSelect.addEventListener(\"change\"", web_app.HTML)
        self.assertIn("conversation-mode-badge", web_app.HTML)
        self.assertIn("单Agent", web_app.HTML)
        self.assertIn("多Agent", web_app.HTML)

    def test_settings_increase_max_steps_for_large_tasks(self):
        settings = get_settings()
        self.assertGreaterEqual(settings.max_steps, 12)
        self.assertGreaterEqual(settings.planner_max_steps, 12)
        self.assertGreaterEqual(settings.executor_max_steps, 12)
        self.assertGreaterEqual(settings.replan_max_attempts, 2)

    def test_conversation_delete_ui_is_present(self):
        self.assertIn("conversation-delete", web_app.HTML)
        self.assertIn('method: "DELETE"', web_app.HTML)
        self.assertIn("确认删除当前会话吗？", web_app.HTML)
        self.assertIn("function deleteConversation(conversationId)", web_app.HTML)

    def test_game_panel_is_not_in_initial_page_layout(self):
        page_before_script = web_app.HTML.split("<script>", 1)[0]
        self.assertNotIn('id="game-panel"', page_before_script)
        self.assertIn("function gamePanelHtml()", web_app.HTML)

    def test_game_intent_is_handled_without_llm(self):
        self.assertIn("function isGameIntent(text)", web_app.HTML)
        self.assertIn("function isGameKnowledgeQuery(text)", web_app.HTML)
        self.assertIn("function extractRequestedGameSize(text)", web_app.HTML)
        self.assertIn("await createGame(extractRequestedGameSize(text));", web_app.HTML)
        self.assertIn("落子后 AI 会自动下一步", web_app.HTML)
        self.assertNotIn("/下棋|五子棋|来一盘|开一局|对弈|棋局/.test(text)", web_app.HTML)
        self.assertIn('id="game-size-select"', web_app.HTML)
        self.assertIn("13x13 标准", web_app.HTML)
        self.assertIn("15x15", web_app.HTML)

    def test_game_panel_has_no_new_game_button(self):
        self.assertNotIn("game-new", web_app.HTML)
        self.assertNotIn("新棋局</button>", web_app.HTML)

    def test_dialog_created_games_append_independent_panels(self):
        self.assertIn('data-active="true"', web_app.HTML)
        self.assertIn("function appendGamePanel()", web_app.HTML)
        self.assertIn("function freezeCurrentGamePanel()", web_app.HTML)
        self.assertIn("freezeCurrentGamePanel();", web_app.HTML)
        self.assertIn("appendGamePanel();", web_app.HTML)
        self.assertIn('step.action === "game_create"', web_app.HTML)
        self.assertNotIn("chat.querySelector(\".game-panel\")", web_app.HTML)
        self.assertNotIn("data.game_id !== gameState.game_id) {\n        return false;", web_app.HTML)

    def test_restore_chat_only_rerenders_active_playing_game(self):
        self.assertIn("const activeGameStates = {}", web_app.HTML)
        self.assertIn("const historicalGameIds = {};", web_app.HTML)
        self.assertIn('bindGamePanel(null, {render: Boolean(gameState && gameState.status === "playing")});', web_app.HTML)
        self.assertIn('if (panel.dataset.frozen !== "true" && panel.dataset.active === "true")', web_app.HTML)
        self.assertIn('await syncCurrentGameState();', web_app.HTML)
        self.assertIn('/api/game/state?game_id=', web_app.HTML)
        self.assertIn('document.addEventListener("visibilitychange"', web_app.HTML)
        self.assertIn('window.addEventListener("pageshow"', web_app.HTML)
        self.assertIn("freezeGamePanel(gamePanel);", web_app.HTML)
        self.assertIn('renderStep(panel.steps, step, {suppressGameReplay: true});', web_app.HTML)
        self.assertIn("if (options.suppressGameReplay) return;", web_app.HTML)
        self.assertIn("historicalGameIds[conversationId] = historicalGameId;", web_app.HTML)
        self.assertIn("if (currentConversationId && historicalGameIds[currentConversationId]) return historicalGameIds[currentConversationId];", web_app.HTML)

    def test_composer_is_locked_while_game_is_playing(self):
        self.assertIn("function syncComposerState()", web_app.HTML)
        self.assertIn("function isGamePlaying()", web_app.HTML)
        self.assertIn("function conversationActionsLocked()", web_app.HTML)
        self.assertIn('conversationList.querySelectorAll(".conversation-item, .conversation-delete")', web_app.HTML)
        self.assertIn("棋局进行中，结束后可继续对话", web_app.HTML)

    def test_game_panel_supports_dynamic_board_size_and_ai_profile(self):
        self.assertIn("function getSelectedGameSize()", web_app.HTML)
        self.assertIn("if (gameSizeSelect) gameSizeSelect.value = String(matched.size);", web_app.HTML)
        self.assertIn("function getAiProfile(state)", web_app.HTML)
        self.assertIn("game-size-badge", web_app.HTML)
        self.assertIn("async function createGame(sizeOverride)", web_app.HTML)
        self.assertIn('const data = await callGameApi("/api/game/create", {game: "gomoku", size});', web_app.HTML)
        self.assertIn("const cellSize = board.length >= 19 ? 24 : board.length >= 15 ? 28 : board.length >= 13 ? 32 : 36;", web_app.HTML)
        self.assertIn("chatPayload.current_game_id = gameState.game_id;", web_app.HTML)
        self.assertIn('if (step.action === "game_moves") {', web_app.HTML)
        self.assertIn("function renderReasoningDelta(panel, event)", web_app.HTML)
        self.assertIn("function finalizeReasoning(panel, event)", web_app.HTML)
        self.assertIn('} else if (event.type === "reasoning_delta") {', web_app.HTML)
        self.assertIn("let pendingGameState = null;", web_app.HTML)
        self.assertIn("if (step.action === \"game_create\" && options.deferCreate)", web_app.HTML)
        self.assertNotIn("function preparePendingGamePanel(data)", web_app.HTML)
        self.assertNotIn("形成最终回答", web_app.HTML)

    def test_game_ai_move_api_returns_draw_for_full_board(self):
        GAMES.clear()
        state = store_game(new_game())
        state.board = [
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [AI, AI, HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI],
            [HUMAN, HUMAN, AI, AI, HUMAN, HUMAN, AI, AI, HUMAN],
        ]
        state.turn = state.ai
        state.status = STATUS_PLAYING
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"game_id": state.game_id}).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/game/ai_move",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["status"], "draw")
            self.assertEqual(payload["winner"], 0)
            self.assertNotIn("move", payload)
        finally:
            server.shutdown()
            server.server_close()

    def test_game_state_api_returns_latest_terminal_status(self):
        GAMES.clear()
        state = store_game(new_game(size=13))
        state.status = STATUS_DRAW
        state.winner = EMPTY
        state.turn = EMPTY
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/game/state?game_id={state.game_id}",
                method="GET",
            )
            with request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["game_id"], state.game_id)
            self.assertEqual(payload["status"], STATUS_DRAW)
            self.assertEqual(payload["board_label"], "13x13")
            self.assertIn("平局", payload["message"])
        finally:
            server.shutdown()
            server.server_close()

    def test_chat_stream_pre_header_error_returns_valid_http_json(self):
        original_agent_factory = web_app.get_agent

        def failing_agent_factory(conversation):
            raise RuntimeError("agent init failed")

        web_app.get_agent = failing_agent_factory
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"message": "hello"}).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/chat_stream",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(error.HTTPError) as caught:
                request.urlopen(req, timeout=10)

            self.assertEqual(caught.exception.code, 500)
            payload = json.loads(caught.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"], "agent init failed")
        finally:
            server.shutdown()
            server.server_close()
            web_app.get_agent = original_agent_factory

    def test_chat_stream_forwards_answer_delta_events(self):
        original_agent_factory = web_app.get_agent

        class StreamingAgent:
            memory = type(
                "Memory",
                (),
                {
                    "stats": staticmethod(
                        lambda: {
                            "message_count": 1,
                            "max_messages": 16,
                            "estimated_chars": 0,
                            "max_chars": 12000,
                            "summary_chars": 0,
                        }
                    )
                },
            )()

            def run_events(self, message):
                yield {"type": "answer_delta", "delta": "你", "payload": {"delta": "你"}}
                yield {"type": "answer_delta", "delta": "好", "payload": {"delta": "好"}}
                yield {"type": "done", "result": AgentResult(final_answer="你好", steps=[])}

        web_app.get_agent = lambda conversation: StreamingAgent()
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"message": "hello"}).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/chat_stream",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as response:
                lines = [json.loads(line) for line in response.read().decode("utf-8").splitlines() if line]

            self.assertEqual([item["type"] for item in lines[:2]], ["answer_delta", "answer_delta"])
            self.assertEqual(lines[-1]["final_answer"], "你好")
        finally:
            server.shutdown()
            server.server_close()
            web_app.get_agent = original_agent_factory

    def test_chat_stream_flushes_delta_before_done(self):
        original_agent_factory = web_app.get_agent

        class SlowStreamingAgent:
            memory = type(
                "Memory",
                (),
                {
                    "stats": staticmethod(
                        lambda: {
                            "message_count": 1,
                            "max_messages": 16,
                            "estimated_chars": 0,
                            "max_chars": 12000,
                            "summary_chars": 0,
                        }
                    )
                },
            )()

            def run_events(self, message):
                yield {"type": "answer_delta", "delta": "先", "payload": {"delta": "先"}}
                time.sleep(0.35)
                yield {"type": "done", "result": AgentResult(final_answer="先", steps=[])}

        web_app.get_agent = lambda conversation: SlowStreamingAgent()
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"message": "hello"}).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/chat_stream",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            start = time.time()
            with request.urlopen(req, timeout=10) as response:
                first_line = response.readline().decode("utf-8")
                elapsed = time.time() - start

            self.assertLess(elapsed, 0.3)
            self.assertEqual(json.loads(first_line)["type"], "answer_delta")
        finally:
            server.shutdown()
            server.server_close()
            web_app.get_agent = original_agent_factory

    def test_chat_stream_passes_current_game_context_to_agent(self):
        original_agent_factory = web_app.get_agent
        captured = {}

        class ContextAwareAgent:
            memory = type(
                "Memory",
                (),
                {
                    "stats": staticmethod(
                        lambda: {
                            "message_count": 1,
                            "max_messages": 16,
                            "estimated_chars": 0,
                            "max_chars": 12000,
                            "summary_chars": 0,
                        }
                    )
                },
            )()

            def run_events(self, message):
                captured["message"] = message
                yield {"type": "done", "result": AgentResult(final_answer="ok", steps=[])}

        web_app.get_agent = lambda conversation: ContextAwareAgent()
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps(
                {
                    "message": "列出本局的序列",
                    "conversation_id": web_app.DEFAULT_CONVERSATION_ID,
                    "current_game_id": "game-123",
                    "current_game_size": 15,
                    "current_game_status": "draw",
                }
            ).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/chat_stream",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as response:
                response.read()

            self.assertIn("[当前棋局上下文]", captured["message"])
            self.assertIn("game_id=game-123", captured["message"])
            self.assertIn("size=15", captured["message"])
            self.assertIn("status=draw", captured["message"])
        finally:
            server.shutdown()
            server.server_close()
            web_app.get_agent = original_agent_factory

    def test_chat_stream_forwards_reasoning_delta_events(self):
        original_agent_factory = web_app.get_agent

        class StreamingReasoningAgent:
            memory = type(
                "Memory",
                (),
                {
                    "stats": staticmethod(
                        lambda: {
                            "message_count": 1,
                            "max_messages": 16,
                            "estimated_chars": 0,
                            "max_chars": 12000,
                            "summary_chars": 0,
                        }
                    )
                },
            )()

            def run_events(self, message):
                yield {
                    "type": "reasoning_delta",
                    "agent": "planner",
                    "delta": "先判断用户问题。",
                    "payload": {"stage": "planning", "delta": "先判断用户问题。"},
                }
                yield {
                    "type": "reasoning_done",
                    "agent": "planner",
                    "payload": {"stage": "planning"},
                }
                yield {"type": "done", "result": AgentResult(final_answer="ok", steps=[])}

        web_app.get_agent = lambda conversation: StreamingReasoningAgent()
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"message": "hello"}).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/chat_stream",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=10) as response:
                lines = [json.loads(line) for line in response.read().decode("utf-8").splitlines() if line]

            self.assertEqual(lines[0]["type"], "reasoning_delta")
            self.assertEqual(lines[1]["type"], "reasoning_done")
            self.assertEqual(lines[-1]["final_answer"], "ok")
        finally:
            server.shutdown()
            server.server_close()
            web_app.get_agent = original_agent_factory

    def test_delete_conversation_api_removes_target_and_returns_fallback(self):
        original_conversations = web_app.CONVERSATIONS
        first_id, first = web_app.create_conversation("会话一")
        second_id, second = web_app.create_conversation("会话二")
        first["updated_at"] = time.time()
        second["updated_at"] = time.time() + 1
        web_app.CONVERSATIONS = {first_id: first, second_id: second}
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/conversations?conversation_id={second_id}",
                method="DELETE",
            )
            with request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["deleted_id"], second_id)
            self.assertEqual(payload["conversation"]["id"], first_id)
            self.assertEqual(len(payload["conversations"]), 1)
            self.assertNotIn(second_id, web_app.CONVERSATIONS)
        finally:
            server.shutdown()
            server.server_close()
            web_app.CONVERSATIONS = original_conversations

    def test_agent_mode_api_updates_conversation_mode(self):
        original_conversations = web_app.CONVERSATIONS
        conversation_id, conversation = web_app.create_conversation("模式切换测试", agent_mode="single")
        web_app.CONVERSATIONS = {conversation_id: conversation}
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req_get_before = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/agent_mode?conversation_id={conversation_id}",
                method="GET",
            )
            with request.urlopen(req_get_before, timeout=10) as response:
                before_payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(before_payload["agent_mode"], "single")

            body = json.dumps({"conversation_id": conversation_id, "agent_mode": "multi"}).encode("utf-8")
            req_post = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/agent_mode",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req_post, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["agent_mode"], "multi")
            self.assertEqual(payload["conversation"]["agent_mode"], "multi")

            req_get_after = request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/agent_mode?conversation_id={conversation_id}",
                method="GET",
            )
            with request.urlopen(req_get_after, timeout=10) as response:
                after_payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(after_payload["agent_mode"], "multi")
        finally:
            server.shutdown()
            server.server_close()
            web_app.CONVERSATIONS = original_conversations


if __name__ == "__main__":
    unittest.main()
