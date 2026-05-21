import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from agent import MiniReActAgent
from game import GameError
from game_tools import game_ai_move, game_analyze, game_create, game_player_move, game_resign, game_state
from web import conversation_store
from web.conversation_store import (
    CONVERSATIONS,
    DEFAULT_CONVERSATION,
    DEFAULT_CONVERSATION_ID,
    conversation_payload,
    create_conversation,
    delete_conversation,
    get_agent,
    get_conversation,
    list_conversations,
    memory_stats,
    title_from_message,
    update_conversation_mode,
    ui_payload,
)
from web.frontend import HTML


HOST = os.getenv("AIHW_HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("AIHW_PORT", "8501"))


def _conversation_map():
    return globals()["CONVERSATIONS"]


def _sync_conversation_store():
    conversation_store.CONVERSATIONS = _conversation_map()


def build_agent_message(message, payload):
    current_game_id = str(payload.get("current_game_id", "")).strip()
    if not current_game_id:
        return message

    parts = [message, "", "[当前棋局上下文]"]
    parts.append(f"game_id={current_game_id}")

    current_game_size = payload.get("current_game_size")
    if current_game_size:
        parts.append(f"size={current_game_size}")

    current_game_status = str(payload.get("current_game_status", "")).strip()
    if current_game_status:
        parts.append(f"status={current_game_status}")

    return "\n".join(parts)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_text(200, HTML, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/conversations":
            _sync_conversation_store()
            self._send_json(200, {"conversations": list_conversations()})
            return
        if parsed.path == "/api/conversation":
            _sync_conversation_store()
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [DEFAULT_CONVERSATION_ID])[0]
            conversation = get_conversation(conversation_id)
            self._send_json(200, ui_payload(conversation))
            return
        if parsed.path == "/api/memory":
            _sync_conversation_store()
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [DEFAULT_CONVERSATION_ID])[0]
            conversation = get_conversation(conversation_id)
            self._send_json(200, memory_stats(conversation))
            return
        if parsed.path == "/api/game/state":
            params = parse_qs(parsed.query)
            game_id = params.get("game_id", [""])[0]
            self._send_json(200, json.loads(game_state(game_id or None)))
            return
        if parsed.path == "/api/agent_mode":
            _sync_conversation_store()
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [DEFAULT_CONVERSATION_ID])[0]
            conversation = get_conversation(conversation_id)
            payload = conversation_payload(conversation)
            self._send_json(200, {"conversation_id": payload["id"], "agent_mode": payload["agent_mode"]})
            return
        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/conversations":
            self._send_json(404, {"error": "Not found"})
            return
        try:
            _sync_conversation_store()
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [""])[0]
            conversation = delete_conversation(conversation_id)
            globals()["CONVERSATIONS"] = conversation_store.CONVERSATIONS
            self._send_json(
                200,
                {
                    "deleted_id": conversation_id,
                    "conversation": conversation_payload(conversation),
                    "conversations": list_conversations(),
                },
            )
        except KeyError as exc:
            self._send_json(404, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})

    def do_POST(self):
        if self.path == "/api/conversations":
            _sync_conversation_store()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            conversation_id, conversation = create_conversation(
                "新对话",
                agent_mode=payload.get("agent_mode"),
            )
            CONVERSATIONS[conversation_id] = conversation
            globals()["CONVERSATIONS"] = conversation_store.CONVERSATIONS
            self._send_json(200, {"conversation": conversation_payload(conversation)})
            return

        if self.path == "/api/agent_mode":
            try:
                _sync_conversation_store()
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body or "{}")
                conversation_id = str(payload.get("conversation_id", DEFAULT_CONVERSATION_ID)).strip()
                conversation = get_conversation(conversation_id)
                update_conversation_mode(conversation, payload.get("agent_mode"))
                globals()["CONVERSATIONS"] = conversation_store.CONVERSATIONS
                updated = conversation_payload(conversation)
                self._send_json(
                    200,
                    {
                        "conversation": updated,
                        "agent_mode": updated["agent_mode"],
                    },
                )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if self.path.startswith("/api/game/"):
            self._handle_game_api(self.path)
            return

        if self.path == "/api/chat_stream":
            self._handle_chat_stream()
            return

        if self.path != "/api/chat":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            _sync_conversation_store()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            message = str(payload.get("message", "")).strip()
            conversation_id = str(payload.get("conversation_id", DEFAULT_CONVERSATION_ID)).strip()
            conversation = get_conversation(conversation_id)
            if not message:
                self._send_json(400, {"error": "message 不能为空"})
                return

            if conversation["title"] == "新对话":
                conversation["title"] = title_from_message(message)
            conversation["updated_at"] = time.time()
            agent = get_agent(conversation)
            result = agent.run(build_agent_message(message, payload))
            step_payloads = [
                {
                    "index": step.index,
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": step.observation,
                    "final_answer": step.final_answer,
                    "summary": MiniReActAgent._natural_step_summary(step),
                }
                for step in result.steps
            ]
            conversation["ui_messages"].append({"role": "user", "content": message})
            conversation["ui_messages"].append(
                {"role": "assistant", "content": result.final_answer, "steps": step_payloads}
            )
            self._send_json(
                200,
                {
                    "final_answer": result.final_answer,
                    "steps": step_payloads,
                    "conversation": conversation_payload(conversation),
                },
            )
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _handle_game_api(self, path):
        handlers = {
            "/api/game/create": game_create,
            "/api/game/player_move": game_player_move,
            "/api/game/ai_move": game_ai_move,
            "/api/game/analyze": game_analyze,
            "/api/game/resign": game_resign,
            "/api/game/state": game_state,
        }
        handler = handlers.get(path)
        if handler is None:
            self._send_json(404, {"error": "Not found"})
            return

        try:
            _sync_conversation_store()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            result = handler(**payload)
            self._send_json(200, json.loads(result))
        except (GameError, TypeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _handle_chat_stream(self):
        headers_sent = False
        self._use_chunked_stream = False
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            message = str(payload.get("message", "")).strip()
            conversation_id = str(payload.get("conversation_id", DEFAULT_CONVERSATION_ID)).strip()
            conversation = get_conversation(conversation_id)
            if not message:
                self._send_json(400, {"error": "message 不能为空"})
                return
            agent = get_agent(conversation)
            if conversation["title"] == "新对话":
                conversation["title"] = title_from_message(message)
            conversation["updated_at"] = time.time()
            conversation["ui_messages"].append({"role": "user", "content": message})
            streamed_steps = []

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            headers_sent = True
            self._use_chunked_stream = True

            for event in agent.run_events(build_agent_message(message, payload)):
                if event["type"] == "done":
                    result = event["result"]
                    conversation["updated_at"] = time.time()
                    conversation["ui_messages"].append(
                        {"role": "assistant", "content": result.final_answer, "steps": streamed_steps}
                    )
                    payload = {
                        "type": "done",
                        "final_answer": result.final_answer,
                        "conversation": conversation_payload(conversation),
                        "memory": memory_stats(conversation),
                    }
                else:
                    payload = event
                    if event["type"] == "step":
                        streamed_steps.append(event["step"])
                    elif event["type"] == "tool_result" and event.get("step"):
                        streamed_steps.append(event["step"])
                self._write_stream_event(payload)
            self._finish_stream()
        except Exception as exc:
            if headers_sent:
                try:
                    self._write_stream_event({"type": "error", "error": str(exc)})
                    self._finish_stream()
                except Exception:
                    pass
            else:
                self._send_json(500, {"error": str(exc)})
        finally:
            self._use_chunked_stream = False

    def log_message(self, format, *args):
        return

    def _send_text(self, status, text, content_type):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status, payload):
        text = json.dumps(payload, ensure_ascii=False)
        self._send_text(status, text, "application/json; charset=utf-8")

    def _write_stream_event(self, payload):
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        if getattr(self, "_use_chunked_stream", False):
            self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
            self.wfile.write(data)
            self.wfile.write(b"\r\n")
        else:
            self.wfile.write(data)
        self.wfile.flush()

    def _finish_stream(self):
        if getattr(self, "_use_chunked_stream", False):
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Mini ReAct Agent Web 已启动：")
    print(f"http://localhost:{PORT}")
    if HOST == "0.0.0.0":
        print(f"局域网访问地址：http://<你的本机IP>:{PORT}")
    else:
        print(f"当前监听地址：http://{HOST}:{PORT}")
    print("按 Ctrl+C 停止服务。")
    server.serve_forever()


if __name__ == "__main__":
    main()
