HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mini ReAct Agent</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #060914;
      --bg-deep: #030611;
      --panel: rgba(10, 18, 36, 0.84);
      --panel-strong: rgba(11, 21, 44, 0.94);
      --panel-soft: rgba(18, 30, 58, 0.82);
      --line: rgba(90, 219, 255, 0.18);
      --line-strong: rgba(136, 96, 255, 0.34);
      --text: #edf6ff;
      --muted: #94a9d7;
      --accent: #46d7ff;
      --accent-dark: #1dbbff;
      --accent-soft: rgba(70, 215, 255, 0.14);
      --violet: #8b5cff;
      --green: #27f0b4;
      --orange: #ff9a3d;
      --tool: rgba(17, 28, 55, 0.75);
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.38);
      --shadow-soft: 0 12px 28px rgba(0, 0, 0, 0.28);
      --glow: 0 0 0 1px rgba(70, 215, 255, 0.12), 0 0 22px rgba(70, 215, 255, 0.18);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(70, 215, 255, 0.16), transparent 26%),
        radial-gradient(circle at top right, rgba(139, 92, 255, 0.18), transparent 24%),
        radial-gradient(circle at 50% 120%, rgba(39, 240, 180, 0.12), transparent 28%),
        linear-gradient(180deg, #0b1120 0%, #060914 45%, #030611 100%);
      color: var(--text);
      position: relative;
      overflow: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.02)) 0 0 / 100% 3px,
        linear-gradient(90deg, rgba(70, 215, 255, 0.03) 1px, transparent 1px) 0 0 / 32px 32px,
        linear-gradient(rgba(139, 92, 255, 0.02) 1px, transparent 1px) 0 0 / 32px 32px;
      mix-blend-mode: screen;
    }
    .layout {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      display: flex;
      flex-direction: column;
      gap: 18px;
      border-right: 1px solid var(--line);
      background: rgba(6, 11, 25, 0.74);
      backdrop-filter: blur(24px);
      padding: 24px 18px;
    }
    .rail-top {
      display: grid;
      gap: 12px;
    }
    .brand-card, .rail-card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      backdrop-filter: blur(20px);
      box-shadow: var(--shadow-soft), var(--glow);
    }
    .rail-card {
      padding: 16px;
      min-height: 0;
    }
    .brand-card {
      padding: 18px 18px 16px;
    }
    aside h1 {
      font-size: 19px;
      margin: 0 0 8px;
      letter-spacing: -.02em;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      margin: 0;
    }
    .section-label {
      font-size: 11px;
      color: var(--muted);
      letter-spacing: .08em;
      text-transform: uppercase;
      margin: 0 0 10px;
    }
    aside h2 {
      font-size: 11px;
      margin: 0 0 10px;
      color: var(--muted);
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .tool {
      padding: 9px 11px;
      margin-bottom: 8px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--tool);
      font-size: 13px;
    }
    .size-picker {
      display: grid;
      gap: 6px;
    }
    .size-picker label {
      font-size: 12px;
      color: var(--muted);
    }
    .size-picker select {
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(8, 16, 33, 0.92);
      color: var(--text);
      padding: 0 12px;
      font-size: 13px;
    }
    .new-chat {
      width: 100%;
      height: 44px;
      margin: 0;
      border-radius: 999px;
      background: linear-gradient(135deg, #1cc8ff, #5d7bff 54%, #8b5cff);
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 26px rgba(70, 215, 255, 0.28);
    }
    .conversation-list {
      display: grid;
      gap: 7px;
      max-height: 100%;
      overflow-y: auto;
      padding-right: 2px;
    }
    .conversation-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 36px;
      gap: 8px;
      align-items: stretch;
    }
    .conversation-item {
      width: 100%;
      min-height: 42px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(12, 19, 39, 0.86);
      color: var(--text);
      text-align: left;
      font-size: 13px;
      line-height: 1.35;
      cursor: pointer;
    }
    .conversation-item-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .conversation-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      display: inline-block;
    }
    .conversation-mode-badge {
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      line-height: 1.2;
      border: 1px solid var(--line);
      background: rgba(14, 24, 48, 0.9);
      color: var(--muted);
    }
    .conversation-mode-badge.multi {
      border-color: rgba(70, 215, 255, 0.42);
      color: #9be9ff;
      background: rgba(26, 102, 132, 0.3);
    }
    .conversation-mode-badge.single {
      border-color: rgba(139, 92, 255, 0.42);
      color: #d6c4ff;
      background: rgba(62, 44, 108, 0.32);
    }
    .conversation-item:hover {
      border-color: rgba(70, 215, 255, 0.34);
      background: rgba(70, 215, 255, 0.12);
    }
    .conversation-item.active {
      border-color: rgba(139, 92, 255, 0.42);
      background: linear-gradient(135deg, rgba(70, 215, 255, 0.14), rgba(139, 92, 255, 0.16));
      color: #dff5ff;
      font-weight: 700;
    }
    .conversation-delete {
      min-width: 36px;
      min-height: 42px;
      padding: 0;
      border: 1px solid rgba(255, 96, 122, 0.2);
      border-radius: 12px;
      background: rgba(44, 15, 24, 0.9);
      color: #ff9db0;
      font-size: 18px;
      line-height: 1;
      box-shadow: none;
    }
    .conversation-delete:hover {
      background: rgba(255, 96, 122, 0.16);
      color: #ffd2da;
      box-shadow: none;
    }
    .status, .memory-box {
      display: none;
    }
    .memory-box {
      gap: 8px;
      padding: 0;
      border: 0;
      background: transparent;
      font-size: 13px;
      color: var(--muted);
    }
    .memory-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }
    .memory-row strong {
      color: var(--text);
      font-weight: 700;
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
      min-width: 0;
    }
    header {
      display: flex;
      justify-content: center;
      padding: 14px 28px 6px;
      background: transparent;
    }
    .hero {
      width: min(980px, 100%);
      padding: 0 4px;
    }
    header h2 {
      margin: 0;
      font-size: 34px;
      line-height: 1.08;
      letter-spacing: -.04em;
      font-weight: 700;
      text-shadow: 0 0 18px rgba(70, 215, 255, 0.22);
    }
    header p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      max-width: 720px;
    }
    .chat {
      flex: 1;
      overflow-y: auto;
      padding: 6px 28px 14px;
    }
    .turn {
      max-width: 920px;
      margin: 0 auto 12px;
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }
    .turn.user-turn {
      flex-direction: row-reverse;
    }
    .avatar {
      flex: 0 0 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      color: #fff;
      font-weight: 700;
      font-size: 12px;
      background: linear-gradient(135deg, #19d7ff, #27f0b4);
      box-shadow: 0 0 18px rgba(39, 240, 180, 0.25);
    }
    .user-turn .avatar {
      background: linear-gradient(135deg, #5d7bff, #8b5cff);
    }
    .bubble {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
      min-width: 0;
      max-width: min(760px, 100%);
      padding: 8px 14px 10px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background:
        linear-gradient(135deg, rgba(70, 215, 255, 0.06), rgba(139, 92, 255, 0.06)),
        var(--panel);
      box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.04);
      backdrop-filter: blur(20px);
    }
    .user-turn .bubble {
      border-color: rgba(139, 92, 255, 0.26);
      background:
        linear-gradient(135deg, rgba(93, 123, 255, 0.16), rgba(139, 92, 255, 0.14)),
        rgba(18, 26, 52, 0.9);
    }
    .speaker {
      display: block;
      margin: 0;
      color: #7cecff;
      font-size: 14px;
      line-height: 1.45;
      font-weight: 700;
    }
    .message-text {
      display: block;
      width: 100%;
      margin: 0;
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
    }
    .thinking-panel {
      max-width: 920px;
      margin: 0 auto 14px;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: var(--shadow-soft), var(--glow);
      backdrop-filter: blur(20px);
    }
    .thinking-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(70, 215, 255, 0.12), rgba(139, 92, 255, 0.1));
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
      padding: 12px 16px 14px;
    }
    .step {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid rgba(123, 155, 219, 0.12);
      animation: fadeIn .26s ease-out both;
    }
    .step-live {
      background: linear-gradient(90deg, rgba(70, 215, 255, 0.12), rgba(255, 255, 255, 0));
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
      background: linear-gradient(135deg, rgba(70, 215, 255, 0.18), rgba(139, 92, 255, 0.16));
      color: #8fe8ff;
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
      padding: 10px 12px;
      border-left: 3px solid var(--orange);
      border-radius: 14px;
      background: rgba(39, 20, 3, 0.66);
      font-size: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .game-panel {
      width: 100%;
      margin: 0;
      padding: 0;
      background: transparent;
    }
    .game-turn .bubble {
      max-width: min(920px, 100%);
      padding: 6px 10px 10px;
    }
    .game-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 8px;
    }
    .game-title {
      font-weight: 800;
      font-size: 16px;
      letter-spacing: .04em;
      color: #8fe8ff;
    }
    .game-meta {
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .game-size-badge {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(70, 215, 255, 0.12);
      color: #8fe8ff;
      border: 1px solid rgba(70, 215, 255, 0.28);
      font-size: 12px;
      font-weight: 700;
    }
    .game-status {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .game-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .game-actions button {
      width: auto;
      min-width: 96px;
      min-height: 38px;
      padding: 0 14px;
      font-size: 13px;
    }
    .game-actions button:disabled {
      cursor: wait;
    }
    .game-panel[data-frozen="true"] .game-actions {
      display: none;
    }
    .game-actions .secondary {
      border: 1px solid var(--line);
      background: rgba(15, 23, 42, 0.82);
      color: var(--text);
    }
    .game-actions .secondary:hover {
      border-color: rgba(70, 215, 255, 0.4);
      background: rgba(70, 215, 255, 0.12);
      color: #8fe8ff;
    }
    .game-body {
      display: grid;
      grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(9, 1fr);
      width: min(100%, 360px);
      aspect-ratio: 1 / 1;
      border: 2px solid #8b5a2b;
      border-radius: 10px;
      background: #d9a85f;
      box-shadow: 0 10px 28px rgba(21, 32, 51, 0.18);
      overflow: hidden;
    }
    .cell {
      position: relative;
      display: grid;
      place-items: center;
      width: 100%;
      aspect-ratio: 1 / 1;
      min-height: 24px;
      border: 1px solid rgba(93, 58, 20, 0.38);
      background: transparent;
      min-width: 0;
      padding: 0;
      color: var(--text);
      cursor: pointer;
      border-radius: 0;
    }
    .cell:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.18);
      box-shadow: none;
    }
    .cell:disabled {
      cursor: default;
      opacity: 1;
    }
    .stone {
      width: 72%;
      height: 72%;
      border-radius: 50%;
      box-shadow: inset 0 2px 5px rgba(255, 255, 255, .32), 0 4px 9px rgba(21, 32, 51, .22);
    }
    .stone.black {
      background: radial-gradient(circle at 34% 28%, #6b7280, #111827 58%, #020617);
    }
    .stone.white {
      background: radial-gradient(circle at 34% 28%, #ffffff, #e5e7eb 62%, #b8c0cc);
      border: 1px solid rgba(21, 32, 51, 0.14);
    }
    .game-info {
      display: grid;
      gap: 10px;
      font-size: 13px;
    }
    .game-message, .analysis-box, .search-box {
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(10, 18, 36, 0.82);
      line-height: 1.55;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }
    .analysis-box {
      white-space: pre-wrap;
    }
    form {
      display: flex;
      align-items: center;
      gap: 12px;
      width: min(920px, calc(100% - 40px));
      margin: 0 auto 18px;
      padding: 10px 12px 10px 16px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background:
        linear-gradient(135deg, rgba(70, 215, 255, 0.08), rgba(139, 92, 255, 0.08)),
        rgba(9, 16, 34, 0.92);
      box-shadow: var(--shadow), var(--glow);
      backdrop-filter: blur(20px);
    }
    input {
      flex: 1;
      min-width: 0;
      min-height: 46px;
      padding: 10px 0;
      border: 0;
      border-radius: 0;
      font-size: 15px;
      outline: none;
      background: transparent;
      color: var(--text);
    }
    input::placeholder {
      color: #7d93c6;
    }
    input:focus {
      border-color: transparent;
      box-shadow: none;
    }
    button {
      width: auto;
      min-width: 118px;
      min-height: 46px;
      padding: 0 18px;
      border: 0;
      border-radius: 999px;
      color: #fff;
      background: linear-gradient(135deg, #19d7ff, #5d7bff 55%, #8b5cff);
      font-size: 15px;
      font-weight: 700;
      letter-spacing: .02em;
      cursor: pointer;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 24px rgba(70, 215, 255, 0.24);
      transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
    }
    button:hover:not(.cell) {
      background: linear-gradient(135deg, #32ddff, #6f8cff 55%, #9b70ff);
      transform: translateY(-1px);
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1), 0 0 30px rgba(70, 215, 255, 0.34);
    }
    button:disabled:not(.cell) {
      opacity: .55;
      cursor: wait;
    }
    .cell:hover,
    .cell:disabled:hover {
      background: rgba(255, 255, 255, 0.18);
      transform: none;
      box-shadow: none;
      filter: none;
    }
    .cell:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.18);
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
      form { width: calc(100% - 24px); margin: 0 auto 14px; padding: 8px 10px 8px 14px; }
      header { padding: 12px 16px 4px; }
      header h2 { font-size: 28px; }
      header p { font-size: 14px; }
      .chat { padding: 6px 12px 12px; }
      .turn, .thinking-panel { max-width: 100%; }
      .avatar { display: none; }
      .bubble { max-width: 100%; }
      .game-panel { width: 100%; padding: 0; }
      .game-head { align-items: flex-start; flex-direction: column; }
      .game-actions { justify-content: flex-start; }
      .game-body { grid-template-columns: 1fr; }
      .board { width: 100%; max-width: 360px; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <div class="rail-top">
        <div class="brand-card">
          <h1>Mini ReAct Agent</h1>
          <div class="subtitle">更轻量的多工具智能体界面，聚焦对话、思考过程与棋局交互。</div>
        </div>
        <button id="new-chat" class="new-chat" type="button">发起新对话</button>
      </div>
      <div class="rail-card">
        <div class="section-label">会话</div>
        <div id="conversation-list" class="conversation-list"></div>
      </div>
      <div class="rail-card" style="padding: 16px;">
        <div class="section-label">Agent 模式</div>
        <div class="size-picker">
          <label for="agent-mode-select">当前会话模式</label>
          <select id="agent-mode-select">
            <option value="multi">多 Agent</option>
            <option value="single">单 Agent</option>
          </select>
        </div>
      </div>
      <div class="rail-card" style="padding: 16px;">
        <div class="section-label">棋盘规格</div>
        <div class="size-picker">
          <label for="game-size-select">默认创建规格</label>
          <select id="game-size-select">
            <option value="9">9x9 快速</option>
            <option value="13" selected>13x13 标准</option>
            <option value="15">15x15 专业</option>
            <option value="19">19x19 实验</option>
          </select>
        </div>
      </div>
      <div class="memory-box" aria-hidden="true">
        <div class="memory-row"><span>消息数</span><strong id="memory-count">-</strong></div>
        <div class="memory-row"><span>上下文字符</span><strong id="memory-chars">-</strong></div>
        <div class="memory-row"><span>摘要字符</span><strong id="memory-summary">-</strong></div>
      </div>
      <div style="display:none;">
        <div class="tool">calculator</div>
        <div class="tool">wikipedia_search</div>
        <div class="tool">file_write</div>
        <div class="tool">file_read</div>
        <div class="tool">game_create</div>
        <div class="tool">game_ai_move</div>
        <div class="tool">game_analyze</div>
      </div>
    </aside>
    <main>
      <header>
        <div class="hero">
          <h2>今天想让 AI 帮你完成什么？</h2>
          <p>输入任务后，系统会在需要时调用工具，并把关键思考过程与最终结果分开展示，页面重点只保留真正有用的信息。</p>
        </div>
      </header>
      <section id="chat" class="chat">
        <div class="turn ai-turn">
          <div class="avatar">AI</div>
          <div class="bubble"><span class="speaker">AI 回答</span><span class="message-text">你好，我是 Mini ReAct Agent。你可以让我查资料、读写文件、做计算，或者直接开始一局五子棋。</span></div>
        </div>
      </section>
      <form id="form">
        <input id="input" autocomplete="off" placeholder="输入任务，例如“总结这个项目结构”或“来一盘 15x15 五子棋”">
        <button id="send" type="submit">发送</button>
      </form>
    </main>
  </div>
  <script>
    const chat = document.querySelector("#chat");
    const form = document.querySelector("#form");
    const input = document.querySelector("#input");
    const send = document.querySelector("#send");
    const newChat = document.querySelector("#new-chat");
    const conversationList = document.querySelector("#conversation-list");
    const memoryCount = document.querySelector("#memory-count");
    const memoryChars = document.querySelector("#memory-chars");
    const memorySummary = document.querySelector("#memory-summary");
    const agentModeSelect = document.querySelector("#agent-mode-select");
    const gameSizeSelect = document.querySelector("#game-size-select");
    let gamePanel = null;
    let gameBoard = null;
    let gameStatus = null;
    let gameSizeBadge = null;
    let gameMessage = null;
    let gameSearch = null;
    let gameAnalysis = null;
    let gameAi = null;
    let gameResign = null;
    let currentConversationId = null;
    let isBusy = false;
    let gameState = null;
    let isGameBusy = false;
    let gameRequestToken = 0;
    let currentAgentMode = agentModeSelect ? agentModeSelect.value : "multi";
    const chatViews = {};
    const activeGameStates = {};
    const historicalGameIds = {};
    let pendingGameState = null;

    // #region debug-point A:report-helper
    function debugReport(hypothesisId, msg, data = {}) {
      fetch("http://127.0.0.1:7777/event", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          sessionId: "game-state-resume",
          runId: "post-fix",
          hypothesisId,
          location: "web/frontend.py",
          msg: "[DEBUG] " + msg,
          data,
          ts: Date.now()
        })
      }).catch(() => {});
    }
    // #endregion

    function normalizeAgentMode(mode) {
      const value = String(mode || "").trim().toLowerCase();
      if (value === "single") return "single";
      return "multi";
    }

    function agentModeLabel(mode) {
      return normalizeAgentMode(mode) === "single" ? "单Agent" : "多Agent";
    }

    function setAgentMode(mode) {
      currentAgentMode = normalizeAgentMode(mode);
      if (agentModeSelect) {
        agentModeSelect.value = currentAgentMode;
      }
    }

    function isGameTerminal(state) {
      return Boolean(state && ["finished", "draw", "resigned"].includes(state.status));
    }

    function setMemoryStats(stats) {
      if (!stats) {
        memoryCount.textContent = "-";
        memoryChars.textContent = "-";
        memorySummary.textContent = "-";
        return;
      }
      memoryCount.textContent = stats.message_count + "/" + stats.max_messages;
      memoryChars.textContent = stats.estimated_chars + "/" + stats.max_chars;
      memorySummary.textContent = stats.summary_chars;
    }

    async function loadMemoryStats(conversationId) {
      try {
        const response = await fetch("/api/memory?conversation_id=" + encodeURIComponent(conversationId));
        const data = await response.json();
        setMemoryStats(data);
      } catch (error) {
        setMemoryStats(null);
      }
    }

    function welcomeHtml() {
      return `
        <div class="turn ai-turn">
          <div class="avatar">AI</div>
          <div class="bubble"><span class="speaker">AI 回答</span><span class="message-text">你好，我是 Mini ReAct Agent。你可以让我查资料、读写文件、做计算，或者直接开始一局五子棋。</span></div>
        </div>
      `;
    }

    function saveCurrentChat() {
      if (currentConversationId) {
        chatViews[currentConversationId] = chat.innerHTML;
        activeGameStates[currentConversationId] = gameState;
        // #region debug-point B:save-current-chat
        debugReport("B", "saveCurrentChat", {
          conversationId: currentConversationId,
          gameId: gameState?.game_id || "",
          status: gameState?.status || "",
          turn: gameState?.turn ?? null
        });
        // #endregion
      }
    }

    function restoreChat(conversationId) {
      chat.innerHTML = chatViews[conversationId] || welcomeHtml();
      gameState = activeGameStates[conversationId] || null;
      // #region debug-point C:restore-chat
      debugReport("C", "restoreChat", {
        conversationId,
        cachedGameId: gameState?.game_id || "",
        cachedStatus: gameState?.status || "",
        cachedTurn: gameState?.turn ?? null,
        activePanelGameId: findActiveGamePanel()?.dataset?.gameId || ""
      });
      // #endregion
      bindGamePanel(null, {render: Boolean(gameState && gameState.status === "playing")});
      syncComposerState();
      chat.scrollTop = chat.scrollHeight;
    }

    async function restoreConversationFromServer(conversationId) {
      gameState = activeGameStates[conversationId] || null;
      resetGameRefs();
      const response = await fetch("/api/conversation?conversation_id=" + encodeURIComponent(conversationId));
      const data = await response.json();
      setAgentMode(data.conversation && data.conversation.agent_mode);
      let historicalGameId = "";
      if (!data.messages || !data.messages.length) {
        chatViews[conversationId] = welcomeHtml();
      } else {
        chat.innerHTML = "";
        for (const message of data.messages) {
          if (message.role === "user") {
            addMessage(message.content, "user");
          } else {
            const panel = createThinkingPanel();
            panel.state.textContent = "历史步骤";
            for (const step of message.steps || []) {
              historicalGameId = historicalGameId || extractGameIdFromStep(step);
              renderStep(panel.steps, step, {suppressGameReplay: true});
            }
            addMessage(message.content, "ai");
          }
        }
        chatViews[conversationId] = chat.innerHTML;
      }
      historicalGameIds[conversationId] = historicalGameId;
      restoreChat(conversationId);
      await syncCurrentGameState();
    }

    async function loadConversations(selectId) {
      const response = await fetch("/api/conversations");
      const data = await response.json();
      const conversations = data.conversations || [];
      if (!conversations.length) return;
      const selectedId = selectId || currentConversationId || conversations[0].id;
      const activeConversation = conversations.find((item) => item.id === selectedId);
      if (activeConversation) {
        setAgentMode(activeConversation.agent_mode);
      }
      renderConversationList(conversations, selectedId);
      if (!currentConversationId) {
        switchConversation(selectedId, false);
      }
    }

    function renderConversationList(conversations, activeId) {
      conversationList.innerHTML = "";
      for (const conversation of conversations) {
        const row = document.createElement("div");
        row.className = "conversation-row";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "conversation-item" + (conversation.id === activeId ? " active" : "");
        const head = document.createElement("div");
        head.className = "conversation-item-head";
        const title = document.createElement("span");
        title.className = "conversation-title";
        title.textContent = conversation.title;
        const badge = document.createElement("span");
        const mode = normalizeAgentMode(conversation.agent_mode);
        badge.className = "conversation-mode-badge " + mode;
        badge.textContent = agentModeLabel(mode);
        head.appendChild(title);
        head.appendChild(badge);
        button.appendChild(head);
        button.disabled = conversationActionsLocked();
        button.addEventListener("click", () => switchConversation(conversation.id, true));
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "conversation-delete";
        remove.textContent = "×";
        remove.title = "删除会话";
        remove.setAttribute("aria-label", "删除会话 " + conversation.title);
        remove.disabled = conversationActionsLocked();
        remove.addEventListener("click", async (event) => {
          event.stopPropagation();
          await deleteConversation(conversation.id);
        });
        row.appendChild(button);
        row.appendChild(remove);
        conversationList.appendChild(row);
      }
    }

    async function deleteConversation(conversationId) {
      if (conversationActionsLocked()) return;
      const targetId = String(conversationId || "").trim();
      if (!targetId) return;
      const isCurrent = targetId === currentConversationId;
      const confirmed = window.confirm(isCurrent ? "确认删除当前会话吗？" : "确认删除这条历史会话吗？");
      if (!confirmed) return;
      try {
        if (currentConversationId && targetId !== currentConversationId) {
          saveCurrentChat();
        }
        const response = await fetch("/api/conversations?conversation_id=" + encodeURIComponent(targetId), {method: "DELETE"});
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "删除会话失败");
        }
        delete chatViews[targetId];
        delete activeGameStates[targetId];
        if (isCurrent) {
          currentConversationId = data.conversation?.id || null;
          gameState = null;
          isGameBusy = false;
          gameRequestToken += 1;
          resetGameRefs();
          if (currentConversationId) {
            if (chatViews[currentConversationId]) {
              restoreChat(currentConversationId);
            } else {
              await restoreConversationFromServer(currentConversationId);
            }
            syncComposerState();
            await loadMemoryStats(currentConversationId);
          } else {
            chat.innerHTML = welcomeHtml();
            setMemoryStats(null);
          }
        }
        await loadConversations(currentConversationId || data.conversation?.id);
        if (!input.disabled) input.focus();
      } catch (error) {
        window.alert("删除会话失败：" + String(error.message || error));
      }
    }

    async function switchConversation(conversationId, shouldSave) {
      if (conversationActionsLocked()) return;
      if (shouldSave) saveCurrentChat();
      currentConversationId = conversationId;
      if (chatViews[conversationId]) {
        restoreChat(conversationId);
      } else {
        await restoreConversationFromServer(conversationId);
      }
      await loadMemoryStats(conversationId);
      await loadConversations(conversationId);
    }

    async function createNewConversation() {
      if (conversationActionsLocked()) return;
      saveCurrentChat();
      const response = await fetch("/api/conversations", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({agent_mode: normalizeAgentMode(agentModeSelect && agentModeSelect.value)})
      });
      const data = await response.json();
      currentConversationId = data.conversation.id;
      setAgentMode(data.conversation.agent_mode);
      gameState = null;
      isGameBusy = false;
      gameRequestToken += 1;
      resetGameRefs();
      chatViews[currentConversationId] = welcomeHtml();
      restoreChat(currentConversationId);
      syncComposerState();
      await loadMemoryStats(currentConversationId);
      await loadConversations(currentConversationId);
      input.focus();
    }

    async function updateAgentMode() {
      if (!currentConversationId || conversationActionsLocked()) {
        setAgentMode(agentModeSelect && agentModeSelect.value);
        return;
      }
      const nextMode = normalizeAgentMode(agentModeSelect && agentModeSelect.value);
      if (nextMode === currentAgentMode) return;
      const response = await fetch("/api/agent_mode", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          conversation_id: currentConversationId,
          agent_mode: nextMode
        })
      });
      const data = await response.json();
      if (!response.ok) {
        setAgentMode(currentAgentMode);
        throw new Error(data.error || "切换 Agent 模式失败");
      }
      setAgentMode(data.agent_mode || (data.conversation && data.conversation.agent_mode));
      await loadConversations(currentConversationId);
    }

    function gamePanelHtml() {
      return `
        <section class="game-panel" data-active="true">
          <div class="game-head">
            <div>
              <div class="game-title">五子棋对弈</div>
              <div class="game-meta">
                <span class="game-size-badge">未创建</span>
                <div class="game-status">创建棋局后开始。</div>
              </div>
            </div>
            <div class="game-actions">
              <button type="button" class="game-ai">AI 下棋</button>
              <button type="button" class="game-resign secondary">提前退出</button>
            </div>
          </div>
          <div class="game-body">
            <div class="board" aria-label="五子棋棋盘"></div>
            <div class="game-info">
              <div class="game-message">玩家执黑先手，点击棋盘空位落子。</div>
              <div class="search-box">AI 搜索信息会显示在这里。</div>
              <div class="analysis-box">终局或退出后会显示复盘。</div>
            </div>
          </div>
        </section>
      `;
    }

    function resetGameRefs() {
      gamePanel = null;
      gameBoard = null;
      gameStatus = null;
      gameSizeBadge = null;
      gameMessage = null;
      gameSearch = null;
      gameAnalysis = null;
      gameAi = null;
      gameResign = null;
    }

    function findGamePanelById(gameId) {
      if (!gameId) return null;
      return Array.from(chat.querySelectorAll(".game-panel")).find((panel) => panel.dataset.gameId === gameId) || null;
    }

    function findActiveGamePanel() {
      const panels = Array.from(chat.querySelectorAll(".game-panel"));
      for (let index = panels.length - 1; index >= 0; index -= 1) {
        const panel = panels[index];
        if (panel.dataset.frozen !== "true" && panel.dataset.active === "true") {
          return panel;
        }
      }
      return null;
    }

    function freezeGamePanel(panel) {
      if (!panel) return;
      // #region debug-point D:freeze-game-panel
      debugReport("D", "freezeGamePanel", {
        panelGameId: panel.dataset.gameId || "",
        statusText: panel.querySelector(".game-status")?.textContent || ""
      });
      // #endregion
      panel.dataset.frozen = "true";
      panel.dataset.active = "false";
      const status = panel.querySelector(".game-status");
      if (status && status.textContent === "玩家回合") {
        status.textContent = "历史棋局";
      }
      panel.querySelectorAll("button").forEach((button) => {
        button.disabled = true;
      });
    }

    function freezeCurrentGamePanel() {
      if (gamePanel && document.body.contains(gamePanel)) {
        freezeGamePanel(gamePanel);
      }
      resetGameRefs();
    }

    function appendGamePanel() {
      const el = document.createElement("div");
      el.className = "turn ai-turn game-turn";
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = "AI";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      const speaker = document.createElement("span");
      speaker.className = "speaker";
      speaker.textContent = "棋局";
      bubble.appendChild(speaker);
      const holder = document.createElement("div");
      holder.innerHTML = gamePanelHtml();
      bubble.appendChild(holder.firstElementChild);
      el.appendChild(avatar);
      el.appendChild(bubble);
      chat.appendChild(el);
      bindGamePanel(el.querySelector(".game-panel"));
      chat.scrollTop = chat.scrollHeight;
      return gamePanel;
    }

    function ensureGamePanel() {
      if (gamePanel && document.body.contains(gamePanel) && gamePanel.dataset.frozen !== "true") {
        return gamePanel;
      }
      const activePanel = findActiveGamePanel();
      if (activePanel) {
        bindGamePanel(activePanel, {render: false});
        return gamePanel;
      }
      return appendGamePanel();
    }

    function bindGamePanel(panel = null, options = {}) {
      const shouldRender = options.render !== false;
      gamePanel = panel || findActiveGamePanel();
      if (!gamePanel) {
        resetGameRefs();
        return;
      }
      gameBoard = gamePanel.querySelector(".board");
      gameStatus = gamePanel.querySelector(".game-status");
      gameSizeBadge = gamePanel.querySelector(".game-size-badge");
      gameMessage = gamePanel.querySelector(".game-message");
      gameSearch = gamePanel.querySelector(".search-box");
      gameAnalysis = gamePanel.querySelector(".analysis-box");
      gameAi = gamePanel.querySelector(".game-ai");
      gameResign = gamePanel.querySelector(".game-resign");
      if (gameAi) gameAi.onclick = aiMove;
      if (gameResign) gameResign.onclick = resignGame;
      if (shouldRender && gameState) {
        renderBoard();
        updateGameInfo(gameState);
      }
    }

    function maybeShowGameFromToolStep(step, options = {}) {
      if (!step || !step.action || !step.observation) return;
      if (options.suppressGameReplay) return;
      if (!["game_create", "game_player_move", "game_ai_move", "game_resign"].includes(step.action)) return;
      try {
        const data = JSON.parse(step.observation);
        if (data.board && data.game_id) {
          if (step.action === "game_create" && options.deferCreate) {
            if (gameState?.game_id && data.game_id !== gameState.game_id) {
              freezeCurrentGamePanel();
            }
            pendingGameState = data;
            return;
          }
          if (step.action === "game_create" && gameState?.game_id && data.game_id !== gameState.game_id) {
            freezeCurrentGamePanel();
          }
          applyGameState(data);
        }
      } catch (error) {
        // Tool observations are plain text on failure; there is nothing to render.
      }
    }

    function applyGameState(data) {
      // #region debug-point E:apply-game-state
      debugReport("E", "applyGameState", {
        conversationId: currentConversationId,
        gameId: data?.game_id || "",
        status: data?.status || "",
        turn: data?.turn ?? null,
        winner: data?.winner ?? null
      });
      // #endregion
      gameState = data;
      if (currentConversationId) {
        activeGameStates[currentConversationId] = gameState;
      }
      const targetPanel = findGamePanelById(data.game_id) || ensureGamePanel();
      bindGamePanel(targetPanel, {render: false});
      gamePanel.dataset.gameId = data.game_id;
      gamePanel.dataset.active = "true";
      gamePanel.dataset.frozen = "false";
      renderBoard();
      updateGameInfo(data);
      if (isGameTerminal(data)) {
        freezeGamePanel(gamePanel);
      }
      syncComposerState();
      return true;
    }

    function renderBoard() {
      if (!gameBoard) return;
      gameBoard.innerHTML = "";
      const size = gameState?.size || getSelectedGameSize();
      const board = gameState?.board || Array.from({length: size}, () => Array(size).fill(0));
      const canPlay = gameState && gameState.status === "playing" && gameState.turn === gameState.human && !isGameBusy;
      const cellSize = board.length >= 19 ? 24 : board.length >= 15 ? 28 : board.length >= 13 ? 32 : 36;
      gameBoard.style.gridTemplateColumns = `repeat(${board.length}, 1fr)`;
      gameBoard.style.width = `min(100%, ${board.length * cellSize}px)`;
      gameBoard.style.maxWidth = `${board.length * cellSize}px`;
      gameBoard.dataset.size = String(board.length);
      for (let row = 0; row < board.length; row += 1) {
        for (let col = 0; col < board[row].length; col += 1) {
          const cell = document.createElement("button");
          cell.type = "button";
          cell.className = "cell";
          cell.setAttribute("aria-label", `${row + 1} 行 ${col + 1} 列`);
          cell.disabled = !canPlay || board[row][col] !== 0;
          if (board[row][col]) {
            const stone = document.createElement("span");
            stone.className = "stone " + (board[row][col] === 1 ? "black" : "white");
            cell.appendChild(stone);
          }
          cell.addEventListener("click", () => playerMove(row, col));
          gameBoard.appendChild(cell);
        }
      }
      syncGameButtons();
    }

    function updateGameInfo(data) {
      if (!gameStatus || !gameMessage || !gameSearch) return;
      if (gameSizeBadge) {
        gameSizeBadge.textContent = data.board_label || `${data.size}x${data.size}`;
      }
      gameStatus.textContent = statusText(data);
      gameMessage.textContent = data.message || "玩家执黑先手，点击棋盘空位落子。";
      if (data.move) {
        gameSearch.textContent = `AI 搜索到 ${data.depth_reached || 0} 层，检查 ${data.nodes || 0} 个节点，耗时 ${data.elapsed_ms || 0} 毫秒，评分 ${data.score || 0}。`;
      } else if (data.ai_profile) {
        gameSearch.textContent = `${data.board_label || `${data.size}x${data.size}`} 建议参数：最大深度 ${data.ai_profile.max_depth}，时间预算 ${data.ai_profile.time_limit_ms} 毫秒。`;
      }
      if (["finished", "draw", "resigned"].includes(data.status)) {
        analyzeGame(data.game_id, gamePanel);
      }
    }

    function statusText(data) {
      if (!data) return "创建棋局后开始。";
      if (data.status === "draw") return "平局";
      if (data.status === "resigned") return "玩家退出，AI 胜";
      if (data.status === "finished") return data.winner === data.human ? "玩家胜" : "AI 胜";
      return data.turn === data.human ? "玩家回合" : "AI 回合";
    }

    function syncGameButtons() {
      if (!gameAi || !gameResign) return;
      const playing = gameState && gameState.status === "playing";
      gameAi.disabled = true;
      gameAi.textContent = playing && gameState.turn === gameState.ai ? "AI 思考中" : "AI 自动下";
      if (gamePanel?.dataset.frozen === "true") {
        gameResign.disabled = true;
      } else {
        gameResign.disabled = isGameBusy || !playing;
      }
      syncComposerState();
    }

    function isGamePlaying() {
      return Boolean(gameState && gameState.status === "playing");
    }

    function conversationActionsLocked() {
      return isBusy || isGamePlaying();
    }

    function syncComposerState() {
      const locked = isGamePlaying();
      if (!isBusy) {
        input.disabled = locked;
        send.disabled = locked;
      }
      newChat.disabled = conversationActionsLocked();
      if (agentModeSelect) {
        agentModeSelect.disabled = conversationActionsLocked();
      }
      for (const button of conversationList.querySelectorAll(".conversation-item, .conversation-delete")) {
        button.disabled = conversationActionsLocked();
      }
      input.placeholder = locked ? "棋局进行中，结束后可继续对话" : "输入你的任务";
    }

    function shouldAutoAiMove(state) {
      return state && state.status === "playing" && state.turn === state.ai;
    }

    async function callGameApi(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload || {})
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "棋局请求失败");
      }
      return data;
    }

    async function createGame(sizeOverride) {
      const requestToken = ++gameRequestToken;
      const size = [9, 13, 15, 19].includes(Number(sizeOverride)) ? Number(sizeOverride) : getSelectedGameSize();
      isGameBusy = true;
      freezeCurrentGamePanel();
      gameState = null;
      if (currentConversationId) {
        activeGameStates[currentConversationId] = null;
      }
      appendGamePanel();
      gameMessage.textContent = `正在创建 ${size}x${size} 棋局...`;
      syncGameButtons();
      try {
        const data = await callGameApi("/api/game/create", {game: "gomoku", size});
        if (requestToken !== gameRequestToken) return;
        gameState = null;
        gameSearch.textContent = "AI 搜索信息会显示在这里。";
        gameAnalysis.textContent = "终局或退出后会显示复盘。";
        applyGameState(data);
      } catch (error) {
        gameMessage.textContent = String(error.message || error);
      } finally {
        if (requestToken === gameRequestToken) {
          isGameBusy = false;
          if (gameState) {
            syncComposerState();
          }
          renderBoard();
        }
      }
    }

    async function playerMove(row, col) {
      if (!gameState || isGameBusy) return;
      const requestToken = gameRequestToken;
      const gameId = gameState.game_id;
      isGameBusy = true;
      gameMessage.textContent = "正在记录玩家落子...";
      renderBoard();
      try {
        const data = await callGameApi("/api/game/player_move", {game_id: gameId, row, col});
        if (requestToken !== gameRequestToken || data.game_id !== gameId) return;
        const applied = applyGameState(data);
        if (applied && shouldAutoAiMove(data)) {
          await aiMove({auto: true, keepBusy: true, requestToken, gameId});
        }
      } catch (error) {
        gameMessage.textContent = String(error.message || error);
      } finally {
        if (requestToken === gameRequestToken && (!gameState || gameState.game_id === gameId)) {
          isGameBusy = false;
          renderBoard();
        }
      }
    }

    async function aiMove(options = {}) {
      const auto = Boolean(options.auto);
      const keepBusy = Boolean(options.keepBusy);
      if (!gameState) return;
      if (!keepBusy && isGameBusy) return;
      if (gameState.status !== "playing" || gameState.turn !== gameState.ai) return;
      const requestToken = options.requestToken ?? gameRequestToken;
      const gameId = options.gameId || gameState.game_id;
      const aiProfile = getAiProfile(gameState);
      if (!keepBusy) {
        isGameBusy = true;
      }
      gameMessage.textContent = "AI 正在搜索下一步...";
      gameSearch.textContent = `${gameState.board_label || `${gameState.size}x${gameState.size}`} 棋盘下，AI 正在按推荐策略搜索下一步...`;
      renderBoard();
      try {
        const data = await callGameApi("/api/game/ai_move", {game_id: gameId, time_limit_ms: aiProfile.time_limit_ms, max_depth: aiProfile.max_depth});
        if (requestToken !== gameRequestToken || data.game_id !== gameId) return;
        applyGameState(data);
      } catch (error) {
        const message = String(error.message || error);
        if (message.includes("已经结束") || message.includes("棋盘已满") || message.includes("无棋")) {
          gameMessage.textContent = "棋局已结束，正在整理结果。";
          analyzeGame(gameId, gamePanel);
        } else {
          gameMessage.textContent = (auto ? "AI 自动落子失败：" : "") + message;
        }
      } finally {
        if (requestToken === gameRequestToken && (!gameState || gameState.game_id === gameId)) {
          isGameBusy = false;
          renderBoard();
        }
      }
    }

    async function resignGame() {
      if (!gameState || isGameBusy) return;
      const requestToken = ++gameRequestToken;
      const gameId = gameState.game_id;
      isGameBusy = true;
      gameMessage.textContent = "正在结束棋局...";
      syncGameButtons();
      try {
        const data = await callGameApi("/api/game/resign", {game_id: gameId});
        if (requestToken !== gameRequestToken || data.game_id !== gameId) return;
        applyGameState(data);
      } catch (error) {
        gameMessage.textContent = String(error.message || error);
      } finally {
        if (requestToken === gameRequestToken) {
          isGameBusy = false;
          renderBoard();
        }
      }
    }

    async function analyzeGame(gameId = null, panel = null) {
      const targetGameId = gameId || gameState?.game_id;
      if (!targetGameId) return;
      const targetPanel = panel || findGamePanelById(targetGameId) || gamePanel;
      const targetAnalysis = targetPanel?.querySelector(".analysis-box");
      try {
        const data = await callGameApi("/api/game/analyze", {game_id: targetGameId});
        const keyMoves = (data.key_moves || []).map((item) => `第 ${item.move_no} 手：${item.comment}`).join("\n");
        if (targetAnalysis) {
          targetAnalysis.textContent = [data.result, data.summary, keyMoves].filter(Boolean).join("\n");
        }
      } catch (error) {
        if (targetAnalysis) {
          targetAnalysis.textContent = String(error.message || error);
        }
      }
    }

    function trackedGameId() {
      if (gameState?.game_id) return gameState.game_id;
      if (gamePanel?.dataset?.gameId) return gamePanel.dataset.gameId;
      const activePanel = findActiveGamePanel();
      if (activePanel?.dataset?.gameId) return activePanel.dataset.gameId;
      if (currentConversationId && historicalGameIds[currentConversationId]) return historicalGameIds[currentConversationId];
      const anyPanel = Array.from(chat.querySelectorAll(".game-panel[data-game-id]")).pop();
      return anyPanel?.dataset?.gameId || "";
    }

    function extractGameIdFromStep(step) {
      if (!step?.action || !String(step.action).startsWith("game_") || !step.observation) return "";
      try {
        const data = JSON.parse(step.observation);
        return data?.game_id || "";
      } catch (error) {
        return "";
      }
    }

    async function syncCurrentGameState() {
      const gameId = trackedGameId();
      // #region debug-point A:sync-request
      debugReport("A", "syncCurrentGameState:start", {
        conversationId: currentConversationId,
        trackedGameId: gameId,
        cachedGameId: gameState?.game_id || "",
        cachedStatus: gameState?.status || ""
      });
      // #endregion
      if (!gameId) return;
      try {
        const response = await fetch("/api/game/state?game_id=" + encodeURIComponent(gameId));
        const data = await response.json();
        // #region debug-point A:sync-response
        debugReport("A", "syncCurrentGameState:response", {
          ok: response.ok,
          trackedGameId: gameId,
          returnedGameId: data?.game_id || "",
          returnedStatus: data?.status || "",
          returnedTurn: data?.turn ?? null
        });
        // #endregion
        if (!response.ok) return;
        applyGameState(data);
      } catch (error) {
        // #region debug-point A:sync-error
        debugReport("A", "syncCurrentGameState:error", {
          trackedGameId: gameId,
          error: String(error.message || error)
        });
        // #endregion
        // Ignore background sync failures and keep current UI state.
      }
    }

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
      content.className = "message-text";
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
      return { panel, state, steps, liveReasoning: {} };
    }

    function reasoningKey(event) {
      const agent = event?.agent || "agent";
      const stage = event?.payload?.stage || "thinking";
      return `${agent}:${stage}`;
    }

    function reasoningLabel(event) {
      const stage = event?.payload?.stage || "thinking";
      if (event?.agent === "planner") return stage === "planning" ? "规划推理" : "规划思考";
      if (event?.agent === "executor") return stage === "execution" ? "执行推理" : "执行思考";
      return "思考增量";
    }

    function renderReasoningDelta(panel, event) {
      const delta = event?.delta || event?.payload?.delta || "";
      if (!delta) return;
      const key = reasoningKey(event);
      let block = panel.liveReasoning[key];
      if (!block) {
        const item = document.createElement("div");
        item.className = "step step-live";
        item.dataset.reasoningKey = key;
        const index = document.createElement("div");
        index.className = "step-index";
        index.textContent = event.agent === "planner" ? "P*" : event.agent === "executor" ? "E*" : "...";
        const body = document.createElement("div");
        const title = document.createElement("div");
        title.className = "step-title";
        title.textContent = reasoningLabel(event);
        const text = document.createElement("div");
        text.className = "step-text";
        text.textContent = "";
        body.appendChild(title);
        body.appendChild(text);
        item.appendChild(index);
        item.appendChild(body);
        panel.steps.appendChild(item);
        block = { item, title, text };
        panel.liveReasoning[key] = block;
      }
      block.text.textContent += delta;
      chat.scrollTop = chat.scrollHeight;
    }

    function finalizeReasoning(panel, event) {
      const key = reasoningKey(event);
      const block = panel.liveReasoning[key];
      if (!block) return;
      block.title.textContent = reasoningLabel(event) + "（完成）";
      block.item.classList.remove("step-live");
      delete panel.liveReasoning[key];
      chat.scrollTop = chat.scrollHeight;
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
      if (step.action === "game_create") {
        const size = Number(input.size) || 9;
        return `创建 ${size}x${size} 五子棋`;
      }
      if (step.action === "game_player_move") {
        return `玩家落子：${Number(input.row) + 1} 行 ${Number(input.col) + 1} 列`;
      }
      if (step.action === "game_ai_move") {
        return "AI 搜索下一步";
      }
      if (step.action === "game_analyze") {
        return "复盘当前棋局";
      }
      if (step.action === "game_moves") {
        return "列出当前棋局手顺";
      }
      if (step.action === "game_resign") {
        return "提前结束棋局";
      }
      return "";
    }

    function compactGameObservation(step, payload) {
      const label = payload.board_label || (payload.size ? `${payload.size}x${payload.size}` : "棋局");
      const base = [`game_id=${payload.game_id || "unknown"}`, label];
      if (payload.move?.coord) base.push(`落子=${payload.move.coord}`);
      if (payload.status) base.push(`状态=${payload.status}`);
      if (payload.message) base.push(`提示=${payload.message}`);
      return base.join("，");
    }

    function formatObservation(step) {
      if (!step.observation) return "";
      const text = String(step.observation);
      if ((step.action || "").startsWith("game_")) {
        try {
          const payload = JSON.parse(text);
          if (payload && typeof payload === "object") {
            return compactGameObservation(step, payload);
          }
        } catch (error) {
          // Fall back to plain text.
        }
      }
      return text.length > 600 ? text.slice(0, 600) + "..." : text;
    }

    function renderStep(container, step, options = {}) {
      if (step.final_answer) {
        return;
      }
      const item = document.createElement("div");
      item.className = "step";
      const index = document.createElement("div");
      index.className = "step-index";
      index.textContent = step.index;
      const body = document.createElement("div");
      const title = document.createElement("div");
      title.className = "step-title";
      title.textContent = step.action ? "调用工具" : "继续调整";
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
      item.appendChild(index);
      item.appendChild(body);
      container.appendChild(item);
      chat.scrollTop = chat.scrollHeight;
      maybeShowGameFromToolStep(step, options);
    }

    function renderPlan(container, plan) {
      const steps = plan.steps || [];
      renderStep(container, {
        index: "P",
        summary: "规划 Agent 已生成计划：" + (plan.goal || "继续处理任务"),
        observation: steps.map((item) => `${item.id}. ${item.description}`).join("\n")
      });
    }

    function appendAnswerDelta(target, delta) {
      if (!delta) return;
      if (target.dataset.streaming !== "1") {
        target.textContent = "";
        target.dataset.streaming = "1";
      }
      target.textContent += delta;
      chat.scrollTop = chat.scrollHeight;
    }

    function readableToolName(name) {
      const names = {
        calculator: "计算器",
        wikipedia_search: "维基百科搜索",
        file_write: "本地文件写入",
        file_read: "本地文件读取",
        game_create: "创建棋局",
        game_player_move: "玩家落子",
        game_ai_move: "AI 下棋",
        game_analyze: "棋局复盘",
        game_moves: "棋谱序列",
        game_resign: "提前退出"
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

    function isGameKnowledgeQuery(text) {
      return /什么是五子棋|五子棋是什么|五子棋.*(规则|玩法|介绍|起源|历史|怎么下|怎么玩)|介绍一下五子棋/.test(text);
    }

    function isGameIntent(text) {
      if (isGameKnowledgeQuery(text)) return false;
      return /想下棋|想玩五子棋|来一盘|开一局|开始下棋|开始五子棋|和AI下棋|和 AI 下棋|和AI对弈|和 AI 对弈|对弈一局|创建棋局/.test(text);
    }

    function extractRequestedGameSize(text) {
      const source = String(text || "").toLowerCase();
      const patterns = [
        {size: 19, regex: /(?:^|[^0-9])19\s*[x*＊乘]\s*19(?:[^0-9]|$)|十九\s*[x*＊乘]\s*十九/},
        {size: 15, regex: /(?:^|[^0-9])15\s*[x*＊乘]\s*15(?:[^0-9]|$)|十五\s*[x*＊乘]\s*十五/},
        {size: 13, regex: /(?:^|[^0-9])13\s*[x*＊乘]\s*13(?:[^0-9]|$)|十三\s*[x*＊乘]\s*十三/},
        {size: 9, regex: /(?:^|[^0-9])9\s*[x*＊乘]\s*9(?:[^0-9]|$)|九\s*[x*＊乘]\s*九/}
      ];
      const matched = patterns.find((item) => item.regex.test(source));
      if (!matched) return null;
      if (gameSizeSelect) gameSizeSelect.value = String(matched.size);
      return matched.size;
    }

    function getSelectedGameSize() {
      const value = Number(gameSizeSelect?.value || 13);
      return [9, 13, 15, 19].includes(value) ? value : 13;
    }

    function getAiProfile(state) {
      if (state?.ai_profile) return state.ai_profile;
      const size = Number(state?.size || getSelectedGameSize());
      if (size === 19) return {time_limit_ms: 3000, max_depth: 3};
      if (size === 15) return {time_limit_ms: 2500, max_depth: 4};
      if (size === 13) return {time_limit_ms: 1800, max_depth: 4};
      return {time_limit_ms: 1200, max_depth: 5};
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      if (!currentConversationId) {
        await createNewConversation();
      }
      if (isGamePlaying()) {
        syncComposerState();
        return;
      }
      input.value = "";
      input.disabled = true;
      send.disabled = true;
      newChat.disabled = true;
      isBusy = true;
      await loadConversations(currentConversationId);
      addMessage(text, "user");

      if (isGameIntent(text)) {
        try {
          addMessage("五子棋棋局已创建。你执黑先手，落子后 AI 会自动下一步。", "ai");
          await createGame(extractRequestedGameSize(text));
        } catch (error) {
          addMessage("创建棋局失败：" + String(error.message || error), "ai");
        } finally {
          saveCurrentChat();
          isBusy = false;
          syncComposerState();
          newChat.disabled = false;
          syncGameButtons();
          await loadConversations(currentConversationId);
          if (!input.disabled) input.focus();
        }
        return;
      }

      const panel = createThinkingPanel();
      const stopStatus = startThinkingStatus(panel);
      const waiting = addMessage("Agent 正在思考和调用工具...", "ai");
      waiting.innerHTML = "";
      const loading = document.createElement("span");
      loading.className = "loading";
      loading.innerHTML = "<span class='pulse'></span><span>Agent 正在思考和调用工具...</span>";
      waiting.appendChild(loading);

      try {
        const chatPayload = {message: text, conversation_id: currentConversationId};
        if (gameState?.game_id) {
          chatPayload.current_game_id = gameState.game_id;
          chatPayload.current_game_size = gameState.size;
          chatPayload.current_game_status = gameState.status;
        }
        const response = await fetch("/api/chat_stream", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(chatPayload)
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
        pendingGameState = null;

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
            } else if (event.type === "reasoning_delta") {
              gotStep = true;
              stopStatus();
              panel.state.textContent = event.message || "正在输出思考过程";
              renderReasoningDelta(panel, event);
            } else if (event.type === "reasoning_done") {
              stopStatus();
              panel.state.textContent = event.message || "当前思考片段已完成";
              finalizeReasoning(panel, event);
            } else if (event.type === "plan") {
              gotStep = true;
              stopStatus();
              panel.state.textContent = event.message || "规划已生成";
              renderPlan(panel.steps, event.payload || {});
            } else if (event.type === "tool_call") {
              panel.state.textContent = event.message || "准备调用工具";
            } else if (event.type === "tool_result") {
              gotStep = true;
              stopStatus();
              panel.state.textContent = event.message || "工具已返回结果";
              if (event.step) {
                renderStep(panel.steps, event.step, {deferCreate: true});
              }
            } else if (event.type === "answer_delta") {
              stopStatus();
              panel.state.textContent = "正在生成最终回答";
              const delta = event.delta || event.payload?.delta || "";
              finalAnswer += delta;
              appendAnswerDelta(waiting, delta);
            } else if (event.type === "step") {
              gotStep = true;
              stopStatus();
              panel.state.textContent = "正在展示真实步骤";
              renderStep(panel.steps, event.step, {deferCreate: true});
            } else if (event.type === "done") {
              stopStatus();
              finalAnswer = event.final_answer || finalAnswer || "";
              panel.state.textContent = gotStep ? "完成" : "没有工具调用步骤";
              if (pendingGameState) {
                applyGameState(pendingGameState);
                pendingGameState = null;
              }
              if (event.memory) {
                setMemoryStats(event.memory);
              }
              if (event.conversation) {
                await loadConversations(event.conversation.id);
              }
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
        pendingGameState = null;
        waiting.textContent = "请求失败：" + error;
        panel.state.textContent = "请求失败";
      } finally {
        saveCurrentChat();
        isBusy = false;
        syncComposerState();
        newChat.disabled = false;
        syncGameButtons();
        await loadConversations(currentConversationId);
        if (!input.disabled) input.focus();
      }
    });
    newChat.addEventListener("click", createNewConversation);
    loadConversations();
    agentModeSelect.addEventListener("change", async () => {
      try {
        await updateAgentMode();
      } catch (error) {
        window.alert("切换 Agent 模式失败：" + String(error.message || error));
      }
    document.addEventListener("visibilitychange", () => {
      // #region debug-point F:visibilitychange
      debugReport("F", "visibilitychange", {state: document.visibilityState});
      // #endregion
      if (document.visibilityState === "visible") {
        syncCurrentGameState();
      }
    });
    window.addEventListener("focus", () => {
      // #region debug-point F:focus
      debugReport("F", "focus", {});
      // #endregion
      syncCurrentGameState();
    });
    window.addEventListener("pageshow", () => {
      // #region debug-point F:pageshow
      debugReport("F", "pageshow", {});
      // #endregion
      syncCurrentGameState();
    });
    });
  </script>
</body>
</body>
</html>
"""
