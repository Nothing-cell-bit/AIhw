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
      --bg: #f3f5f8;
      --panel: #ffffff;
      --panel-soft: #f8fafc;
      --line: #d8dee8;
      --text: #152033;
      --muted: #667085;
      --accent: #2563eb;
      --accent-dark: #1d4ed8;
      --green: #0f766e;
      --orange: #b45309;
      --tool: #eef8f5;
      --shadow: 0 18px 45px rgba(21, 32, 51, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(180deg, #f9fbff 0%, var(--bg) 42%, #eef2f7 100%);
      color: var(--text);
    }
    .layout {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      border-right: 1px solid var(--line);
      background: rgba(255, 255, 255, .78);
      backdrop-filter: blur(12px);
      padding: 22px;
    }
    aside h1 {
      font-size: 20px;
      margin: 0 0 6px;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
      margin-bottom: 22px;
    }
    aside h2 {
      font-size: 13px;
      margin: 22px 0 10px;
      color: var(--muted);
    }
    .tool {
      padding: 9px 11px;
      margin-bottom: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--tool);
      font-size: 13px;
    }
    .status {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 11px;
      border: 1px solid #c7d2fe;
      border-radius: 8px;
      background: #eef2ff;
      color: #3730a3;
      font-size: 13px;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
    }
    main {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    header {
      padding: 18px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, .86);
      backdrop-filter: blur(12px);
    }
    header h2 {
      margin: 0;
      font-size: 19px;
    }
    header p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    .chat {
      flex: 1;
      overflow-y: auto;
      padding: 26px 28px;
    }
    .turn {
      max-width: 860px;
      margin: 0 auto 16px;
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }
    .turn.user-turn {
      flex-direction: row-reverse;
    }
    .avatar {
      flex: 0 0 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      color: #fff;
      font-weight: 700;
      font-size: 13px;
      background: var(--green);
      box-shadow: var(--shadow);
    }
    .user-turn .avatar {
      background: var(--accent);
    }
    .bubble {
      min-width: 0;
      max-width: min(720px, 100%);
      padding: 13px 15px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      line-height: 1.65;
      white-space: pre-wrap;
      box-shadow: 0 8px 24px rgba(21, 32, 51, .05);
    }
    .user-turn .bubble {
      border-color: #bfdbfe;
      background: #eff6ff;
    }
    .speaker {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .thinking-panel {
      max-width: 860px;
      margin: 0 auto 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: var(--shadow);
    }
    .thinking-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-soft);
      color: var(--text);
      font-weight: 700;
      font-size: 14px;
    }
    .thinking-state {
      color: var(--muted);
      font-weight: 500;
      font-size: 12px;
    }
    .steps {
      padding: 12px 14px 14px;
    }
    .step {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid #edf0f5;
      animation: fadeIn .26s ease-out both;
    }
    .step:last-child {
      border-bottom: 0;
    }
    .step-index {
      width: 26px;
      height: 26px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: #e0f2fe;
      color: #0369a1;
      font-size: 12px;
      font-weight: 700;
    }
    .step-title {
      margin-bottom: 4px;
      font-weight: 700;
      font-size: 13px;
    }
    .step-text {
      color: var(--text);
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .tool-call {
      margin-top: 8px;
      padding: 9px 10px;
      border-left: 3px solid var(--orange);
      border-radius: 6px;
      background: #fff7ed;
      font-size: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    form {
      display: flex;
      gap: 10px;
      padding: 16px 28px 22px;
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, .9);
    }
    input {
      flex: 1;
      min-width: 0;
      padding: 13px 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 15px;
      outline: none;
      background: #fff;
    }
    input:focus {
      border-color: #93c5fd;
      box-shadow: 0 0 0 3px rgba(147, 197, 253, .28);
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
    button:hover {
      background: var(--accent-dark);
    }
    button:disabled {
      opacity: .55;
      cursor: wait;
    }
    .loading {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
    }
    .pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      animation: pulse 1s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { transform: scale(.82); opacity: .45; }
      50% { transform: scale(1.15); opacity: 1; }
    }
    @keyframes fadeIn {
      from { transform: translateY(4px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    @media (max-width: 760px) {
      .layout { grid-template-columns: 1fr; }
      aside { display: none; }
      main { height: 100vh; }
      form { padding: 12px; }
      header { padding: 14px 16px; }
      .chat { padding: 16px 12px; }
      .turn, .thinking-panel { max-width: 100%; }
      .avatar { display: none; }
      .bubble { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <h1>Mini ReAct Agent</h1>
      <div class="subtitle">一个从零实现的 ReAct 工具调用智能体。</div>
      <div class="status"><span class="dot"></span><span>本地 Web 服务运行中</span></div>
      <h2>工具</h2>
      <div class="tool">calculator</div>
      <div class="tool">wikipedia_search</div>
      <div class="tool">file_write</div>
      <div class="tool">file_read</div>
      <h2>示例</h2>
      <div class="tool">查一下爱因斯坦的出生年份和去世年份，然后计算他活了多少岁。</div>
    </aside>
    <main>
      <header>
        <h2>Agent 对话台</h2>
        <p>用户提问后，AI 会按步骤思考、选择工具、观察结果并整理答案。</p>
      </header>
      <section id="chat" class="chat">
        <div class="turn ai-turn">
          <div class="avatar">AI</div>
          <div class="bubble">
            <span class="speaker">AI 回答</span>你好，我是 Mini ReAct Agent。输入任务后，我会自动选择工具并展示调用过程。
          </div>
        </div>
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

    function addMessage(text, role) {
      const el = document.createElement("div");
      const isUser = role === "user";
      el.className = "turn " + (isUser ? "user-turn" : "ai-turn");
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = isUser ? "你" : "AI";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      const speaker = document.createElement("span");
      speaker.className = "speaker";
      speaker.textContent = isUser ? "用户提问" : "AI 回答";
      const content = document.createElement("span");
      content.textContent = text;
      bubble.appendChild(speaker);
      bubble.appendChild(content);
      el.appendChild(avatar);
      el.appendChild(bubble);
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;
      return content;
    }

    function createThinkingPanel() {
      const panel = document.createElement("section");
      panel.className = "thinking-panel";
      const head = document.createElement("div");
      head.className = "thinking-head";
      const title = document.createElement("span");
      title.textContent = "AI 思考过程";
      const state = document.createElement("span");
      state.className = "thinking-state";
      state.textContent = "等待模型返回";
      const steps = document.createElement("div");
      steps.className = "steps";
      head.appendChild(title);
      head.appendChild(state);
      panel.appendChild(head);
      panel.appendChild(steps);
      chat.appendChild(panel);
      chat.scrollTop = chat.scrollHeight;
      return { panel, state, steps };
    }

    function formatActionInput(step) {
      const input = step.action_input || {};
      if (step.action === "calculator") {
        return input.expression ? "计算表达式：" + input.expression : "";
      }
      if (step.action === "wikipedia_search") {
        const lang = input.lang ? "，语言：" + input.lang : "";
        return input.query ? "搜索关键词：" + input.query + lang : "";
      }
      if (step.action === "file_write") {
        return input.filename ? "写入文件：" + input.filename : "";
      }
      if (step.action === "file_read") {
        return input.filename ? "读取文件：" + input.filename : "";
      }
      return "";
    }

    function formatObservation(step) {
      if (!step.observation) return "";
      const text = String(step.observation);
      return text.length > 600 ? text.slice(0, 600) + "..." : text;
    }

    function renderStep(container, step) {
      const item = document.createElement("div");
      item.className = "step";
      const index = document.createElement("div");
      index.className = "step-index";
      index.textContent = step.index;
      const body = document.createElement("div");
      const title = document.createElement("div");
      title.className = "step-title";
      title.textContent = step.final_answer ? "形成最终回答" : (step.action ? "调用工具" : "继续调整");
      const thought = document.createElement("div");
      thought.className = "step-text";
      thought.textContent = step.summary || ("思考：" + (step.thought || "无"));
      body.appendChild(title);
      body.appendChild(thought);

      if (step.action) {
        const tool = document.createElement("div");
        tool.className = "tool-call";
        const inputText = formatActionInput(step);
        const observation = formatObservation(step);
        tool.textContent = [
          "使用工具：" + readableToolName(step.action),
          inputText ? "调用内容：" + inputText : "",
          observation ? "工具结果：" + observation : ""
        ].filter(Boolean).join("\n");
        body.appendChild(tool);
      }
      if (step.final_answer) {
        const finalText = document.createElement("div");
        finalText.className = "tool-call";
        finalText.textContent = "答案：" + step.final_answer;
        body.appendChild(finalText);
      }

      item.appendChild(index);
      item.appendChild(body);
      container.appendChild(item);
      chat.scrollTop = chat.scrollHeight;
    }

    function readableToolName(name) {
      const names = {
        calculator: "计算器",
        wikipedia_search: "维基百科搜索",
        file_write: "本地文件写入",
        file_read: "本地文件读取"
      };
      return names[name] || name || "未知工具";
    }

    function startThinkingStatus(panel) {
      const states = ["整理上下文", "等待模型决策", "解析工具调用", "准备观察结果"];
      let index = 0;
      panel.state.textContent = states[index];
      const timer = setInterval(() => {
        index = (index + 1) % states.length;
        panel.state.textContent = states[index];
      }, 900);
      return () => clearInterval(timer);
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      send.disabled = true;
      addMessage(text, "user");
      const panel = createThinkingPanel();
      const stopStatus = startThinkingStatus(panel);
      const waiting = addMessage("Agent 正在思考和调用工具...", "ai");
      waiting.innerHTML = "";
      const loading = document.createElement("span");
      loading.className = "loading";
      loading.innerHTML = "<span class='pulse'></span><span>Agent 正在思考和调用工具...</span>";
      waiting.appendChild(loading);

      try {
        const response = await fetch("/api/chat_stream", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: text})
        });
        if (!response.ok || !response.body) {
          const data = await response.json();
          stopStatus();
          waiting.textContent = data.error || "请求失败。";
          panel.state.textContent = "请求失败";
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let finalAnswer = "";
        let gotStep = false;
        let streamDone = false;

        while (!streamDone) {
          const chunk = await reader.read();
          streamDone = chunk.done;
          buffer += decoder.decode(chunk.value || new Uint8Array(), {stream: !streamDone});
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);
            if (event.type === "status") {
              panel.state.textContent = event.message;
            } else if (event.type === "step") {
              gotStep = true;
              stopStatus();
              panel.state.textContent = "正在展示真实步骤";
              renderStep(panel.steps, event.step);
            } else if (event.type === "done") {
              stopStatus();
              finalAnswer = event.final_answer || "";
              panel.state.textContent = gotStep ? "完成" : "没有工具调用步骤";
            } else if (event.type === "error") {
              stopStatus();
              waiting.textContent = event.error || "请求失败。";
              panel.state.textContent = "请求失败";
              return;
            }
          }
        }
        stopStatus();
        waiting.textContent = finalAnswer || "没有返回内容。";
      } catch (error) {
        stopStatus();
        waiting.textContent = "请求失败：" + error;
        panel.state.textContent = "请求失败";
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
        if self.path == "/api/chat_stream":
            self._handle_chat_stream()
            return

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

    def _handle_chat_stream(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            message = str(payload.get("message", "")).strip()
            if not message:
                self._send_json(400, {"error": "message 不能为空"})
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            for event in AGENT.run_events(message):
                if event["type"] == "done":
                    result = event["result"]
                    payload = {
                        "type": "done",
                        "final_answer": result.final_answer,
                    }
                else:
                    payload = event
                self._write_stream_event(payload)
        except Exception as exc:
            try:
                self._write_stream_event({"type": "error", "error": str(exc)})
            except Exception:
                pass

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
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        self.wfile.write(line.encode("utf-8"))
        self.wfile.flush()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Mini ReAct Agent Web 已启动：")
    print("http://localhost:8501")
    print("按 Ctrl+C 停止服务。")
    server.serve_forever()


if __name__ == "__main__":
    main()
