# 思考过程流式输出专项规划

## 1. 背景

当前项目已经支持最终回答的流式输出，但 `AI 思考过程` 面板仍然主要依赖整块事件：

- 单 Agent 在得到完整 JSON 后才产出 `step`
- Multi-Agent 在得到完整计划或完整执行决策后才产出 `plan` / `tool_result`
- 前端只对 `answer_delta` 做逐段追加展示

这导致用户能够看到最终回答逐步出现，却无法同步看到规划、决策和工具调用前的思考增量，交互体验不一致。

## 2. 目标

本专项的目标是打通 `LLM -> Agent -> Web 前端` 的思考增量链路，让用户在不暴露完整内部推理细节的前提下，实时看到可公开的思考摘要流。

目标要求：

- 最终回答继续保留现有流式能力
- 思考过程支持增量事件推送，不再只能整块显示
- 优先覆盖 Multi-Agent 模式，再兼容 Legacy 单 Agent
- 前端将思考增量渲染到 `AI 思考过程` 面板，不污染最终回答气泡
- 平台不支持 reasoning 流时自动回退到当前整块模式

## 3. 现状分析

### 3.1 后端现状

- [llm_client.py](file:///d:/AIhw/llm_client.py)
  - 已支持 `chat_stream()`
  - 但当前 `_extract_delta()` 会把 `content` 和 `reasoning_content` 混在一起提取，无法区分“正文增量”和“思考增量”
- [multi_agent.py](file:///d:/AIhw/multi_agent.py)
  - `PlannerAgent.plan()` 和 `ExecutorAgent._decide_step()` 都使用 `llm.chat()` 阻塞拿完整结果
  - 因此无法在规划和执行决策阶段产生增量事件
- [agent.py](file:///d:/AIhw/agent.py)
  - Legacy 单 Agent 的思考和工具决策同样依赖一次性 `chat()`
  - 仅最终回答阶段使用了流式接口
- [events.py](file:///d:/AIhw/events.py)
  - 现有事件模型已支持扩展新的事件类型，适合承载 reasoning 增量

### 3.2 前端现状

- [web_app.py](file:///d:/AIhw/web_app.py)
  - 已通过 NDJSON 流式接收事件
  - 已实现 `answer_delta` 的逐段渲染
  - `thinking panel` 目前只渲染 `status / plan / tool_result / step`
  - 不支持 `reasoning_delta / planner_delta / executor_delta`

## 4. 设计原则

- 不直接暴露原始完整 Chain-of-Thought
- 只展示可公开的思考摘要流或 reasoning 增量
- 保持事件协议统一，复用现有 NDJSON 管道
- 保证向后兼容，旧模型或无 reasoning 流的场景仍可正常运行
- 优先保证稳定性，再优化“像打字一样”的细节体验

## 5. 总体方案

### 5.1 事件协议扩展

新增以下事件类型：

- `reasoning_delta`
  - 通用思考增量事件
- `reasoning_done`
  - 当前思考片段已结束

字段约定：

- `type`
- `agent`
  - `planner` / `executor` / `legacy`
- `message`
- `payload.delta`
- `payload.stage`

示例：

```json
{
  "type": "reasoning_delta",
  "agent": "planner",
  "message": "规划 Agent 正在思考",
  "payload": {
    "stage": "planning",
    "delta": "正在判断任务是否需要工具"
  }
}
```

### 5.2 LLM 流式拆分

在 [llm_client.py](file:///d:/AIhw/llm_client.py) 中新增结构化流式接口：

- `chat_stream_events(messages, max_tokens=1200)`

返回事件：

- `{"kind": "reasoning", "delta": "..."}`
- `{"kind": "content", "delta": "..."}`

实现要求：

- 能识别 `delta.reasoning_content`
- 能识别 `delta.content`
- 保留现有 `chat_stream()`，但仅返回 `content` 轨

### 5.3 Multi-Agent 先行改造

优先改造 [multi_agent.py](file:///d:/AIhw/multi_agent.py)：

- `PlannerAgent.plan_events()`
  - 流式发出 `reasoning_delta`
  - 累积 `content` 并在结束后解析 JSON
- `ExecutorAgent.decide_step_events()`
  - 与 `plan_events()` 同理
- `AgentCoordinator.run_events()`
  - 转发 reasoning 增量事件到前端

### 5.4 前端增量渲染

在 [web_app.py](file:///d:/AIhw/web_app.py) 中增加：

- `renderReasoningDelta(panel, event)`
- `flushReasoningBlock(panel, agent)`

表现要求：

- planner 和 executor 的 reasoning 流独立展示
- reasoning 结束后保留为一条思考记录
- 如果后续收到了 `plan` 或 `tool_result`，对应 reasoning 区块不应丢失

## 6. 分阶段实施

### 阶段 1：基础链路打通

范围：

- 新增 spec
- `llm_client.py` 增加结构化流式事件接口
- `multi_agent.py` 增加 planner/executor 思考增量事件
- `web_app.py` 增加 reasoning 面板渲染

产出：

- Multi-Agent 模式下，用户可实时看到规划/执行阶段的思考增量

### 阶段 2：Legacy Agent 接入

范围：

- 改造 [agent.py](file:///d:/AIhw/agent.py) 的 `_legacy_run_events()`
- 在单 Agent 模式中对每轮决策支持 reasoning 流

产出：

- 单 Agent 与 Multi-Agent 都具备思考过程流式能力

### 阶段 3：体验优化

范围：

- 节流与合并过碎 token
- 对 reasoning 增量做摘要清洗和重复去除
- 前端增加“展开 / 收起思考片段”

产出：

- 思考流更稳定、可读性更高

## 7. 风险与回退

风险点：

- 模型不稳定返回 `reasoning_content`
- 流式返回时正文 JSON 不完整
- reasoning 文本过碎或过长，导致前端抖动
- 原始 reasoning 可能包含不适合直接展示的内部细节

回退策略：

- 若 `chat_stream_events()` 无 reasoning 轨，则退回当前整块模式
- 若正文 JSON 解析失败，则退回 `chat()` 一次性调用
- 前端若未收到 `reasoning_delta`，仍按现有 `plan / step / tool_result` 渲染

## 8. 测试计划

### 8.1 单元测试

- `llm_client.py`
  - reasoning/content 轨分流正确
- `multi_agent.py`
  - 事件顺序包含 `reasoning_delta -> plan/tool_result -> answer_delta -> done`

### 8.2 Web 流测试

- `web_app.py`
  - 能转发 reasoning 增量事件
  - 前端 HTML 包含 reasoning 渲染逻辑

### 8.3 回退测试

- 无 reasoning 轨时仍能正常得到 `plan`
- JSON 流式解析失败时可回退到阻塞模式

## 9. 本次执行范围

本次开始执行的范围是 **阶段 1**：

- 编写本 spec
- 实现 `LLMClient.chat_stream_events()`
- 在 Multi-Agent 中接入 `planner/executor` reasoning 增量事件
- 在前端 thinking panel 中渲染 reasoning 增量
- 补充对应测试
