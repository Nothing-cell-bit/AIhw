# Spec: 流式输出、记忆体系与双 Agent 协作

## Why

当前项目已经具备一个单体 Mini ReAct Agent：它能维护会话上下文、按步骤调用工具，并在零依赖 Web 页面里展示思考/工具调用过程。下一步目标是把它升级成更像真实产品的 Agent 框架：

- 用户能看到更及时的流式反馈，而不是等整轮模型调用结束。
- Agent 能区分“本轮对话上下文”和“跨会话可复用记忆”。
- 复杂任务先由规划 Agent 拆解，再由执行 Agent 按计划行动，降低单 Agent 边想边做的失控风险。

## Current State

### 1. 流式输出

结论：部分实现，但还不是真正的模型 token 流。

已实现：
- `agent.py` 的 `MiniReActAgent.run_events()` 会产出 `status`、`step`、`done` 事件。
- `web_app.py` 的 `/api/chat_stream` 使用 `application/x-ndjson` 逐行返回事件，并在前端用 `ReadableStream` 读取。
- Web 页面可以边执行边展示状态和工具步骤。

未实现：
- `llm_client.py` 中 `LLMClient.chat(..., stream=True)` 直接抛出 `NotImplementedError`，底层模型调用仍是一次性返回。
- 最终回答只在 `done` 事件里一次性返回，没有 token-by-token 或 sentence-by-sentence 输出。
- CLI 和 Streamlit 页面仍使用阻塞式 `agent.run()`。

判定：已有“事件级流式 UI”，没有“模型级流式输出”。

### 2. 短期记忆 / 长期记忆

结论：短期记忆已基础实现，长期记忆未实现。

已实现的短期记忆：
- `memory.py` 的 `ConversationMemory` 维护当前 Agent 的 `messages`。
- 支持 `MEMORY_MAX_MESSAGES`、`MEMORY_MAX_CHARS` 裁剪。
- 超限后会把较早消息压缩进 `summary`。
- `web_app.py` 的多对话列表为每个对话创建独立 `MiniReActAgent` 与独立 `ConversationMemory`。

短期记忆的不足：
- 摘要是本地截断/拼接，不是语义级总结。
- 对话和记忆都在进程内，服务重启后丢失。
- 没有按用户、主题、事实、偏好、任务状态区分记忆类型。

未实现的长期记忆：
- 没有持久化存储。
- 没有长期事实抽取、检索、更新、遗忘或删除机制。
- `data/` 目录目前只是工具读写文件，不是 Agent 记忆库。

判定：已有“会话内短期上下文”，没有“跨会话长期记忆”。

### 3. 多 Agent 协作

结论：未实现。

现状：
- `MiniReActAgent` 同时负责理解任务、决定工具调用、执行工具、处理观察结果和生成最终答案。
- 项目中没有 `PlannerAgent`、`ExecutorAgent`、`Coordinator` 或任务交接协议。
- `prompts.py` 只有一个通用 ReAct 系统提示词。

判定：当前是单 Agent ReAct 循环，没有“规划 Agent + 执行 Agent”的协作架构。

## Goals

- 实现真正可用的流式输出能力，至少支持最终回答的增量输出。
- 保留现有 Web 事件流，同时扩展统一事件协议，支持状态、计划、工具调用、工具结果、文本增量、完成和错误事件。
- 明确拆分短期记忆与长期记忆。
- 增加可持久化、可检索、可审计、可关闭的长期记忆。
- 引入双 Agent 协作：PlannerAgent 只负责计划，ExecutorAgent 只负责执行，Coordinator 负责任务流转和事件输出。
- 尽量保持现有 `MiniReActAgent.run()`、`run_events()` 的兼容性，避免一次性重写整个项目。

## Non-goals

- 首版不引入 LangChain / LlamaIndex。
- 首版不做复杂向量数据库；长期记忆先用 SQLite 和关键词/标签检索，后续再加 embedding。
- 首版不做任意数量 Agent 的动态图调度，只实现固定的 Planner + Executor。
- 首版不要求工具并行执行。
- 首版不把所有历史聊天记录无条件写入长期记忆。

## Recommended Approach

推荐采用“渐进式内核升级”：

1. 保留现有 `MiniReActAgent` 对外 API。
2. 新增统一事件对象和 LLM 流式客户端能力。
3. 新增 `MemoryStore`，让短期记忆继续在 `ConversationMemory` 中工作，长期记忆由 SQLite 持久化。
4. 新增 `PlannerAgent`、`ExecutorAgent` 和 `AgentCoordinator`。
5. 最后让 `MiniReActAgent` 包装 Coordinator，旧调用方不用立刻改名。

不推荐一开始大规模重写 `agent.py`。当前项目文件少、边界清晰，渐进迁移更稳。

## Architecture

### Event Protocol

新增统一事件结构，建议放入 `events.py`：

```python
{
    "type": "status | plan | step | tool_call | tool_result | answer_delta | done | error",
    "conversation_id": "optional string",
    "agent": "planner | executor | coordinator | answer",
    "message": "human readable status",
    "payload": {},
}
```

事件含义：
- `status`：正在做什么。
- `plan`：PlannerAgent 产出的结构化计划。
- `tool_call`：ExecutorAgent 准备调用工具。
- `tool_result`：工具观察结果。
- `step`：兼容现有前端的步骤展示。
- `answer_delta`：最终回答的增量文本。
- `done`：完整最终结果。
- `error`：可展示错误。

### LLM Streaming

在 `llm_client.py` 中新增：

- `chat(messages) -> str`：保留现有阻塞调用。
- `chat_stream(messages) -> Iterator[str]`：请求 OpenAI-compatible SSE 流，解析 `data: ...`。
- `_extract_delta(data) -> str`：从 `choices[].delta.content`、`choices[].text` 等兼容格式提取增量。

关键策略：
- Planner 和 Executor 的结构化 JSON 决策先继续用非流式调用，避免半截 JSON 难以解析。
- 最终面向用户的回答由 Answer/Synthesizer 阶段流式生成，产生 `answer_delta`。
- 流结束后把完整回答写回短期记忆。

这样首版既能获得真实文本流，又不会破坏工具调用的稳定性。

### Memory

短期记忆继续由 `ConversationMemory` 负责：
- 当前会话最近消息。
- 当前会话语义摘要。
- 工具观察结果。

新增长期记忆模块，建议放入 `memory_store.py`：

```python
class MemoryStore:
    def add(record: MemoryRecord) -> str: ...
    def search(query: str, limit: int = 5) -> list[MemoryRecord]: ...
    def update(memory_id: str, **fields) -> None: ...
    def delete(memory_id: str) -> None: ...
    def list_recent(limit: int = 20) -> list[MemoryRecord]: ...
```

长期记忆字段：

```text
id
scope: user | conversation | project
kind: preference | fact | task | tool_result | summary
content
tags
confidence
importance
source_conversation_id
created_at
updated_at
last_accessed_at
expires_at
```

存储：
- 首版使用 `data/memory.sqlite3`。
- 使用 Python 标准库 `sqlite3`，避免新增重依赖。
- 可选使用 SQLite FTS；如果环境不可用，退化为 `LIKE` + 标签 + 最近更新时间排序。

记忆写入流程：
1. 每轮完成后，MemoryExtractor 判断哪些内容值得长期保存。
2. 明显敏感信息、密钥、一次性临时内容默认不保存。
3. 只保存稳定事实、偏好、长期任务状态、项目约定。
4. 相似记忆更新已有记录，不无限追加重复内容。

记忆读取流程：
1. 收到用户输入后，用输入文本检索长期记忆。
2. 取 Top K 相关记录注入 Planner 上下文。
3. 如果长期记忆与用户最新输入冲突，优先相信最新输入。

配置建议：

```env
LONG_TERM_MEMORY_ENABLED=1
LONG_TERM_MEMORY_PATH=data/memory.sqlite3
LONG_TERM_MEMORY_TOP_K=5
MEMORY_EXTRACT_IMPORTANCE_THRESHOLD=0.6
```

### Multi-Agent Collaboration

新增固定三层：

1. `AgentCoordinator`
   - 接收用户输入。
   - 读取短期记忆和长期记忆。
   - 调用 PlannerAgent。
   - 把计划交给 ExecutorAgent。
   - 必要时触发一次 replan。
   - 负责最终回答流式输出。
   - 负责记忆写入。

2. `PlannerAgent`
   - 只规划，不调用工具。
   - 输出严格 JSON。
   - 计划包括目标、约束、步骤、工具需求、成功标准、失败处理。

3. `ExecutorAgent`
   - 接收 Planner 的计划。
   - 使用现有 `run_tool()` 执行工具。
   - 每一步输出结构化事件。
   - 遇到计划不可执行时返回 `needs_replan`，不自己大改目标。

建议新增 `multi_agent.py`：

```python
class PlannerAgent:
    def plan(self, task, context) -> TaskPlan: ...

class ExecutorAgent:
    def execute_events(self, plan, context) -> Iterator[AgentEvent]: ...

class AgentCoordinator:
    def run_events(self, user_input) -> Iterator[AgentEvent]: ...
```

`MiniReActAgent` 保持为兼容门面：

```python
class MiniReActAgent:
    def run_events(self, user_input):
        if settings.multi_agent_enabled:
            yield from self.coordinator.run_events(user_input)
        else:
            yield from self._legacy_run_events(user_input)
```

配置建议：

```env
MULTI_AGENT_ENABLED=1
PLANNER_MAX_STEPS=8
EXECUTOR_MAX_STEPS=8
REPLAN_MAX_ATTEMPTS=1
FINAL_ANSWER_STREAMING=1
```

## Scenarios

### Scenario: 流式最终回答

GIVEN 用户在 Web 页面提交一个不需要工具的普通问题  
WHEN 模型开始生成最终回答  
THEN 前端持续收到 `answer_delta` 并逐步显示文本  
AND 结束时收到 `done`，其中包含完整最终回答。

### Scenario: 工具任务的事件流

GIVEN 用户要求“查资料并计算”  
WHEN Agent 执行任务  
THEN 前端依次看到计划、工具调用、工具结果和最终回答增量  
AND 工具调用仍使用完整 JSON 决策，不依赖半截流式 JSON。

### Scenario: 短期记忆

GIVEN 用户在当前对话中告诉 Agent 一个临时上下文  
WHEN 后续几轮继续追问  
THEN Agent 能从 `ConversationMemory` 中读取该上下文  
AND 服务重启后该短期上下文不要求保留。

### Scenario: 长期记忆

GIVEN 用户明确表达一个稳定偏好，例如“以后默认用中文回答”  
WHEN 新建对话后再次提问  
THEN Agent 能检索长期记忆并按该偏好回答  
AND 记忆状态可在调试接口或页面中查看。

### Scenario: 规划 Agent + 执行 Agent

GIVEN 用户提出一个多步骤任务  
WHEN Coordinator 开始处理  
THEN PlannerAgent 先输出结构化计划  
AND ExecutorAgent 按计划执行工具  
AND 最终回答说明结果、关键步骤和未完成风险。

## Impact

- Frontend:
  - 更新 `/api/chat_stream` 消费逻辑，支持 `plan`、`tool_call`、`tool_result`、`answer_delta`。
  - 当前步骤面板可以复用，但最终回答气泡需要支持增量追加。

- Backend:
  - `llm_client.py` 增加 SSE 流解析。
  - `agent.py` 保留兼容 API，但可委托给 Coordinator。
  - 新增 `events.py`、`memory_store.py`、`multi_agent.py`。

- Database:
  - 新增 `data/memory.sqlite3`。
  - 不迁移现有 `data/*.txt`。

- AI / prompts:
  - `prompts.py` 拆出 `PLANNER_PROMPT`、`EXECUTOR_PROMPT`、`MEMORY_EXTRACTOR_PROMPT`、`ANSWER_PROMPT`。
  - Planner/Executor 必须输出结构化 JSON。
  - Answer 阶段可以输出自然语言并流式返回。

- Deployment:
  - 新增环境变量。
  - 默认可保留 legacy 模式，避免旧流程突然变化。

## Tasks

- [ ] 定义统一事件协议 `events.py`，并让旧 `step/status/done` 映射到新协议。
- [ ] 为 `LLMClient` 增加 `chat_stream()`，支持 OpenAI-compatible SSE。
- [ ] 增加流式解析测试，覆盖 `data: {...}`、空行、`[DONE]`、异常 JSON。
- [ ] 改造 Web `/api/chat_stream`，支持转发 `answer_delta`。
- [ ] 改造前端最终回答气泡，收到 `answer_delta` 时追加文本，收到 `done` 时校准完整答案。
- [ ] 新增 `MemoryStore` 和 SQLite schema 初始化。
- [ ] 新增长期记忆检索、写入、更新、删除接口。
- [ ] 新增 MemoryExtractor，完成后只提取稳定、非敏感、高价值记忆。
- [ ] 在 Agent 上下文构建时注入相关长期记忆。
- [ ] 新增 `PlannerAgent`，输出结构化 `TaskPlan`。
- [ ] 新增 `ExecutorAgent`，基于计划执行现有工具。
- [ ] 新增 `AgentCoordinator`，串联记忆检索、规划、执行、最终回答流、记忆写入。
- [ ] 让 `MiniReActAgent` 保持旧 API，并通过配置切换 legacy / multi-agent。
- [ ] 更新 README，说明三种能力的状态、配置和运行方式。
- [ ] 增加测试：流式输出、短期记忆裁剪、长期记忆检索、多 Agent 计划执行。

## Acceptance

- [ ] `LLMClient.chat_stream()` 能从模拟 SSE 响应中逐段产出文本。
- [ ] Web 页面提交问题后，最终回答区域能逐字或逐段增长，而不是只在结束时出现。
- [ ] legacy 模式下，原有 `MiniReActAgent.run()` 行为不破坏。
- [ ] 当前对话仍能使用短期记忆，并在超限后保留摘要。
- [ ] 开启长期记忆后，新对话能检索到上一对话保存的稳定偏好或事实。
- [ ] 长期记忆不会保存 `.env`、API key、明显密钥或工具写入的大段原文。
- [ ] PlannerAgent 对多步骤任务产出计划，且 ExecutorAgent 的工具执行能对应计划步骤。
- [ ] ExecutorAgent 遇到不可执行计划时能返回 `needs_replan`，Coordinator 最多重规划一次。
- [ ] 单元测试不依赖真实模型 API，使用 fake LLM / fake stream。
- [ ] 手动运行 `python web_app.py` 后，`/api/chat_stream` 能持续 flush NDJSON 事件。

## Risks

- 流式 JSON 决策容易解析不稳定。
  - 缓解：首版只流式最终自然语言回答，内部工具决策继续非流式 JSON。

- 长期记忆可能保存不该保存的信息。
  - 缓解：默认过滤密钥、路径、长文本和低重要性内容；提供关闭配置和删除接口。

- Planner 计划过度复杂，Executor 执行变慢。
  - 缓解：限制计划步骤数，默认最多一次 replan。

- 多 Agent 增加模型调用次数。
  - 缓解：简单任务允许 Planner 输出单步计划；后续可加“快速路径”跳过 Planner。

- SQLite 关键词检索相关性有限。
  - 缓解：首版用标签、recency、importance 综合排序；embedding 检索放入后续扩展。

## Suggested Implementation Order

1. 先做事件协议和 `LLMClient.chat_stream()`，因为这是后续 Web 增量输出的基础。
2. 再做最终回答流式输出，不改工具决策机制。
3. 接着做 `MemoryStore`，把长期记忆作为可选能力接入上下文。
4. 然后做 Planner/Executor/Coordinator，先在测试里跑通，再接入 Web。
5. 最后更新 README 和页面记忆状态展示。

## Future Extensions

- 使用 embedding 向量检索长期记忆。
- 增加 Memory 管理页面：查看、编辑、删除、禁用某条记忆。
- 支持更多 Agent 角色，例如 ReviewerAgent、ResearchAgent。
- 根据任务复杂度自动选择 single-agent 或 multi-agent。
- 为工具执行增加超时、取消、并行和权限提示。
