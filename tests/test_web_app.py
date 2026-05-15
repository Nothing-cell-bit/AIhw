import json
import time
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib import error, request

import web_app
from agent_types import AgentResult
from game import AI, HUMAN, STATUS_PLAYING, GAMES, new_game, store_game


class WebAppTests(unittest.TestCase):
    def test_game_panel_is_not_in_initial_page_layout(self):
        page_before_script = web_app.HTML.split("<script>", 1)[0]
        self.assertNotIn('id="game-panel"', page_before_script)
        self.assertIn("function gamePanelHtml()", web_app.HTML)

    def test_game_intent_is_handled_without_llm(self):
        self.assertIn("function isGameIntent(text)", web_app.HTML)
        self.assertIn("function isGameKnowledgeQuery(text)", web_app.HTML)
        self.assertIn("await createGame();", web_app.HTML)
        self.assertIn("落子后 AI 会自动下一步", web_app.HTML)
        self.assertNotIn("/下棋|五子棋|来一盘|开一局|对弈|棋局/.test(text)", web_app.HTML)

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
        self.assertIn('bindGamePanel(null, {render: Boolean(gameState && gameState.status === "playing")});', web_app.HTML)
        self.assertIn('if (panel.dataset.frozen !== "true" && panel.dataset.active === "true")', web_app.HTML)

    def test_composer_is_locked_while_game_is_playing(self):
        self.assertIn("function syncComposerState()", web_app.HTML)
        self.assertIn("function isGamePlaying()", web_app.HTML)
        self.assertIn("棋局进行中，结束后可继续对话", web_app.HTML)

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


if __name__ == "__main__":
    unittest.main()
