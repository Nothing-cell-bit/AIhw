import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from agent import MiniReActAgent
from game import GameError
from game_tools import game_ai_move, game_analyze, game_create, game_player_move, game_resign


HOST = "127.0.0.1"
PORT = int(os.getenv("AIHW_PORT", "8501"))


def create_conversation(title="新对话"):
    conversation_id = uuid.uuid4().hex
    return conversation_id, {
        "id": conversation_id,
        "title": title,
        "created_at": time.time(),
        "updated_at": time.time(),
        "agent": None,
        "ui_messages": [],
    }


DEFAULT_CONVERSATION_ID, DEFAULT_CONVERSATION = create_conversation("新对话")
CONVERSATIONS = {DEFAULT_CONVERSATION_ID: DEFAULT_CONVERSATION}


def get_conversation(conversation_id):
    if conversation_id in CONVERSATIONS:
        return CONVERSATIONS[conversation_id]
    return CONVERSATIONS[DEFAULT_CONVERSATION_ID]


def conversation_payload(conversation):
    return {
        "id": conversation["id"],
        "title": conversation["title"],
        "created_at": conversation["created_at"],
        "updated_at": conversation["updated_at"],
        "memory": memory_stats(conversation),
    }


def get_agent(conversation):
    if conversation["agent"] is None:
        conversation["agent"] = MiniReActAgent(conversation_id=conversation["id"])
    return conversation["agent"]


def memory_stats(conversation):
    agent = conversation.get("agent")
    if agent is None:
        return {
            "message_count": 0,
            "max_messages": 0,
            "estimated_chars": 0,
            "max_chars": 0,
            "summary_chars": 0,
        }
    return agent.memory.stats()


def ui_payload(conversation):
    return {
        "conversation": conversation_payload(conversation),
        "messages": conversation["ui_messages"],
    }


def list_conversations():
    conversations = sorted(
        CONVERSATIONS.values(),
        key=lambda item: item["updated_at"],
        reverse=True,
    )
    return [conversation_payload(item) for item in conversations]


def title_from_message(message):
    message = " ".join(message.split())
    if not message:
        return "新对话"
    return message[:18] + ("..." if len(message) > 18 else "")


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
    .size-picker {
      display: grid;
      gap: 6px;
      margin-top: 10px;
      margin-bottom: 14px;
    }
    .size-picker label {
      font-size: 12px;
      color: var(--muted);
    }
    .size-picker select {
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--text);
      padding: 0 10px;
      font-size: 13px;
    }
    .new-chat {
      width: 100%;
      height: 38px;
      margin: 14px 0 8px;
      border-radius: 7px;
      background: var(--accent);
    }
    .conversation-list {
      display: grid;
      gap: 7px;
      max-height: 260px;
      overflow-y: auto;
      padding-right: 2px;
    }
    .conversation-item {
      width: 100%;
      min-height: 38px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--text);
      text-align: left;
      font-size: 13px;
      line-height: 1.35;
      cursor: pointer;
    }
    .conversation-item:hover {
      border-color: #bfdbfe;
      background: #f8fbff;
    }
    .conversation-item.active {
      border-color: #93c5fd;
      background: #eff6ff;
      color: #1d4ed8;
      font-weight: 700;
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
    .memory-box {
      display: grid;
      gap: 8px;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
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
    .game-panel {
      width: 100%;
      margin: 0;
      padding: 0;
      background: transparent;
    }
    .game-turn .bubble {
      max-width: min(860px, 100%);
    }
    .game-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 12px;
    }
    .game-title {
      font-weight: 800;
      font-size: 15px;
    }
    .game-meta {
      margin-top: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .game-size-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      border: 1px solid #bfdbfe;
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
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .game-actions button {
      width: auto;
      min-width: 82px;
      height: 34px;
      padding: 0 12px;
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
      background: #fff;
      color: var(--text);
    }
    .game-actions .secondary:hover {
      border-color: #bfdbfe;
      background: #eff6ff;
      color: var(--accent-dark);
    }
    .game-body {
      display: grid;
      grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .board {
      display: grid;
      grid-template-columns: repeat(9, 1fr);
      width: min(100%, 360px);
      aspect-ratio: 1 / 1;
      border: 2px solid #8b5a2b;
      background: #d9a85f;
      box-shadow: 0 10px 28px rgba(21, 32, 51, .10);
    }
    .cell {
      position: relative;
      display: grid;
      place-items: center;
      width: 100%;
      aspect-ratio: 1 / 1;
      border: 1px solid rgba(93, 58, 20, .38);
      background: transparent;
      min-width: 0;
      padding: 0;
      color: var(--text);
      cursor: pointer;
    }
    .cell:hover:not(:disabled) {
      background: rgba(255, 255, 255, .18);
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
      border: 1px solid rgba(21, 32, 51, .14);
    }
    .game-info {
      display: grid;
      gap: 10px;
      font-size: 13px;
    }
    .game-message, .analysis-box, .search-box {
      padding: 10px 11px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      line-height: 1.55;
    }
    .analysis-box {
      white-space: pre-wrap;
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
      <h1>Mini ReAct Agent</h1>
      <div class="subtitle">一个从零实现的 ReAct 工具调用智能体。</div>
      <div class="status"><span class="dot"></span><span>本地 Web 服务运行中</span></div>
      <button id="new-chat" class="new-chat" type="button">新建对话</button>
      <h2>对话</h2>
      <div id="conversation-list" class="conversation-list"></div>
      <h2>工具</h2>
      <div class="tool">calculator</div>
      <div class="tool">wikipedia_search</div>
      <div class="tool">file_write</div>
      <div class="tool">file_read</div>
      <div class="tool">game_create</div>
      <div class="tool">game_ai_move</div>
      <div class="tool">game_analyze</div>
      <div class="size-picker">
        <label for="game-size-select">默认棋盘规格</label>
        <select id="game-size-select">
          <option value="9">9x9 快速</option>
          <option value="13" selected>13x13 标准</option>
          <option value="15">15x15 专业</option>
          <option value="19">19x19 实验</option>
        </select>
      </div>
      <h2>记忆状态</h2>
      <div class="memory-box">
        <div class="memory-row"><span>消息数</span><strong id="memory-count">-</strong></div>
        <div class="memory-row"><span>上下文字符</span><strong id="memory-chars">-</strong></div>
        <div class="memory-row"><span>摘要字符</span><strong id="memory-summary">-</strong></div>
      </div>
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
    const newChat = document.querySelector("#new-chat");
    const conversationList = document.querySelector("#conversation-list");
    const memoryCount = document.querySelector("#memory-count");
    const memoryChars = document.querySelector("#memory-chars");
    const memorySummary = document.querySelector("#memory-summary");
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
    const chatViews = {};
    const activeGameStates = {};

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
          <div class="bubble">
            <span class="speaker">AI 回答</span>你好，我是 Mini ReAct Agent。输入任务后，我会自动选择工具并展示调用过程。
          </div>
        </div>
      `;
    }

    function saveCurrentChat() {
      if (currentConversationId) {
        chatViews[currentConversationId] = chat.innerHTML;
        activeGameStates[currentConversationId] = gameState;
      }
    }

    function restoreChat(conversationId) {
      chat.innerHTML = chatViews[conversationId] || welcomeHtml();
      gameState = activeGameStates[conversationId] || null;
      bindGamePanel(null, {render: Boolean(gameState && gameState.status === "playing")});
      syncComposerState();
      chat.scrollTop = chat.scrollHeight;
    }

    async function restoreConversationFromServer(conversationId) {
      gameState = activeGameStates[conversationId] || null;
      resetGameRefs();
      const response = await fetch("/api/conversation?conversation_id=" + encodeURIComponent(conversationId));
      const data = await response.json();
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
              renderStep(panel.steps, step);
            }
            addMessage(message.content, "ai");
          }
        }
        chatViews[conversationId] = chat.innerHTML;
      }
      restoreChat(conversationId);
    }

    async function loadConversations(selectId) {
      const response = await fetch("/api/conversations");
      const data = await response.json();
      const conversations = data.conversations || [];
      if (!conversations.length) return;
      renderConversationList(conversations, selectId || currentConversationId || conversations[0].id);
      if (!currentConversationId) {
        switchConversation(selectId || conversations[0].id, false);
      }
    }

    function renderConversationList(conversations, activeId) {
      conversationList.innerHTML = "";
      for (const conversation of conversations) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "conversation-item" + (conversation.id === activeId ? " active" : "");
        button.textContent = conversation.title;
        button.disabled = isBusy;
        button.addEventListener("click", () => switchConversation(conversation.id, true));
        conversationList.appendChild(button);
      }
    }

    async function switchConversation(conversationId, shouldSave) {
      if (isBusy) return;
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
      if (isBusy) return;
      saveCurrentChat();
      const response = await fetch("/api/conversations", {method: "POST"});
      const data = await response.json();
      currentConversationId = data.conversation.id;
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

    function maybeShowGameFromToolStep(step) {
      if (!step || !step.action || !step.observation) return;
      if (!["game_create", "game_player_move", "game_ai_move", "game_resign"].includes(step.action)) return;
      try {
        const data = JSON.parse(step.observation);
        if (data.board && data.game_id) {
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

    function syncComposerState() {
      const locked = isGamePlaying();
      if (!isBusy) {
        input.disabled = locked;
        send.disabled = locked;
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

    async function createGame() {
      const requestToken = ++gameRequestToken;
      const size = getSelectedGameSize();
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
      if (step.action === "game_resign") {
        return "提前结束棋局";
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
      maybeShowGameFromToolStep(step);
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
          await createGame();
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
        const response = await fetch("/api/chat_stream", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: text, conversation_id: currentConversationId})
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
                renderStep(panel.steps, event.step);
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
              renderStep(panel.steps, event.step);
            } else if (event.type === "done") {
              stopStatus();
              finalAnswer = event.final_answer || finalAnswer || "";
              panel.state.textContent = gotStep ? "完成" : "没有工具调用步骤";
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
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_text(200, HTML, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/conversations":
            self._send_json(200, {"conversations": list_conversations()})
            return
        if parsed.path == "/api/conversation":
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [DEFAULT_CONVERSATION_ID])[0]
            conversation = get_conversation(conversation_id)
            self._send_json(200, ui_payload(conversation))
            return
        if parsed.path == "/api/memory":
            params = parse_qs(parsed.query)
            conversation_id = params.get("conversation_id", [DEFAULT_CONVERSATION_ID])[0]
            conversation = get_conversation(conversation_id)
            self._send_json(200, memory_stats(conversation))
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/api/conversations":
            conversation_id, conversation = create_conversation("新对话")
            CONVERSATIONS[conversation_id] = conversation
            self._send_json(200, {"conversation": conversation_payload(conversation)})
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
            result = agent.run(message)
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
        }
        handler = handlers.get(path)
        if handler is None:
            self._send_json(404, {"error": "Not found"})
            return

        try:
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

            for event in agent.run_events(message):
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
    print("http://localhost:8501")
    print("按 Ctrl+C 停止服务。")
    server.serve_forever()


if __name__ == "__main__":
    main()
