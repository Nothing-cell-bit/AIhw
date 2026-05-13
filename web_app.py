import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent import MiniReActAgent


HOST = "127.0.0.1"
PORT = 8501
AGENT = MiniReActAgent()


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mini ReAct Agent</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #dfe3ea;
      --text: #1f2937;
      --muted: #667085;
      --accent: #2563eb;
      --accent-dark: #1d4ed8;
      --tool: #eef6f2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .layout {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      border-right: 1px solid var(--line);
      background: #fbfcfe;
      padding: 20px;
    }
    aside h1 {
      font-size: 18px;
      margin: 0 0 18px;
    }
    aside h2 {
      font-size: 13px;
      margin: 24px 0 10px;
      color: var(--muted);
    }
    .tool {
      padding: 8px 10px;
      margin-bottom: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--tool);
      font-size: 13px;
    }
    main {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    .chat {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
    }
    .message {
      max-width: 860px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      margin: 0 auto 14px;
      line-height: 1.65;
      white-space: pre-wrap;
    }
    .user {
      border-color: #bfdbfe;
      background: #eff6ff;
    }
    details {
      max-width: 860px;
      margin: 0 auto 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px 14px;
    }
    summary {
      cursor: pointer;
      color: var(--muted);
      font-size: 14px;
    }
    pre {
      overflow-x: auto;
      background: #111827;
      color: #f9fafb;
      padding: 12px;
      border-radius: 6px;
      font-size: 13px;
    }
    form {
      display: flex;
      gap: 10px;
      padding: 16px 24px 22px;
      border-top: 1px solid var(--line);
      background: #fff;
    }
    input {
      flex: 1;
      min-width: 0;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 15px;
    }
    button {
      width: 96px;
      border: 0;
      border-radius: 6px;
      color: #fff;
      background: var(--accent);
      font-size: 15px;
      cursor: pointer;
    }
    button:disabled {
      opacity: .55;
      cursor: wait;
    }
    @media (max-width: 760px) {
      .layout { grid-template-columns: 1fr; }
      aside { display: none; }
      main { height: 100vh; }
      form { padding: 12px; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h1>Mini ReAct Agent</h1>
      <h2>工具</h2>
      <div class="tool">calculator</div>
      <div class="tool">wikipedia_search</div>
      <div class="tool">file_write</div>
      <div class="tool">file_read</div>
      <h2>示例</h2>
      <div class="tool">查一下爱因斯坦的出生年份和去世年份，然后计算他活了多少岁。</div>
    </aside>
    <main>
      <section id="chat" class="chat">
        <div class="message">你好，我是 Mini ReAct Agent。输入任务后，我会自动选择工具并展示调用过程。</div>
      </section>
      <form id="form">
        <input id="input" autocomplete="off" placeholder="输入你的任务">
        <button id="send" type="submit">发送</button>
      </form>
    </main>
  </div>
  <script>
    const chat = document.querySelector("#chat");
    const form = document.querySelector("#form");
    const input = document.querySelector("#input");
    const send = document.querySelector("#send");

    function addMessage(text, cls) {
      const el = document.createElement("div");
      el.className = "message " + (cls || "");
      el.textContent = text;
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;
      return el;
    }

    function addSteps(steps) {
      const details = document.createElement("details");
      details.open = true;
      const summary = document.createElement("summary");
      summary.textContent = "查看思考与工具调用";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(steps, null, 2);
      details.appendChild(summary);
      details.appendChild(pre);
      chat.appendChild(details);
      chat.scrollTop = chat.scrollHeight;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      send.disabled = true;
      addMessage(text, "user");
      const waiting = addMessage("Agent 正在思考和调用工具...");

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: text})
        });
        const data = await response.json();
        waiting.textContent = data.final_answer || data.error || "没有返回内容。";
        if (data.steps) addSteps(data.steps);
      } catch (error) {
        waiting.textContent = "请求失败：" + error;
      } finally {
        send.disabled = false;
        input.focus();
      }
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in {"/", "/index.html"}:
            self._send_text(200, HTML, "text/html; charset=utf-8")
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            message = str(payload.get("message", "")).strip()
            if not message:
                self._send_json(400, {"error": "message 不能为空"})
                return

            result = AGENT.run(message)
            self._send_json(
                200,
                {
                    "final_answer": result.final_answer,
                    "steps": [
                        {
                            "index": step.index,
                            "thought": step.thought,
                            "action": step.action,
                            "action_input": step.action_input,
                            "observation": step.observation,
                            "final_answer": step.final_answer,
                        }
                        for step in result.steps
                    ],
                },
            )
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

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


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Mini ReAct Agent Web 已启动：")
    print("http://localhost:8501")
    print("按 Ctrl+C 停止服务。")
    server.serve_forever()


if __name__ == "__main__":
    main()
