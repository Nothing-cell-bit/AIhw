# 项目结构重构专项规划

## 1. 背景

当前项目已经能稳定运行，但目录和文件职责开始明显失衡：

- `web_app.py` 同时承担会话存储、HTTP 路由、页面模板、前端脚本和样式资源
- `game_ai.py` 同时承担搜索配置、评估、威胁检测、VCF 搜索和主搜索流程
- `agent.py` 与 `multi_agent.py` 存在重复的清洗、序列化和回退逻辑
- 多个模块已经超过数百行，阅读、测试和后续修改成本持续增加

本专项的目标是通过分阶段重构，把“大而全”文件拆成职责单一的小模块，同时保持现有行为兼容。

## 2. 重构目标

- 按领域职责重组目录结构，而不是单纯按文件大小拆分
- 优先移动现有代码，不先改变业务行为
- 保持现有导入尽量兼容，降低一次性改动风险
- 每个阶段都用现有测试验证，确保模块间调用稳定

## 3. 设计原则

- 拆分优先：高耦合、高体积、高频变更文件
- 兼容优先：旧入口文件保留薄封装或转发层
- 渐进优先：每次只做一个聚合点，不做大爆炸式迁移
- 测试优先：每完成一轮拆分就跑相关测试

## 4. 目标结构

推荐逐步演进到以下目录：

- `agent/`
  - `legacy_agent.py`
  - `coordinator.py`
  - `planner.py`
  - `executor.py`
  - `answer_cleaner.py`
  - `step_formatters.py`
- `llm/`
  - `client.py`
  - `stream_parser.py`
  - `retry_policy.py`
- `game/`
  - `core.py`
  - `state.py`
  - `tools.py`
  - `analysis.py`
  - `ai/profile.py`
  - `ai/evaluate.py`
  - `ai/candidates.py`
  - `ai/threats.py`
  - `ai/vcf.py`
  - `ai/search.py`
- `web/`
  - `conversation_store.py`
  - `frontend.py`
  - `server.py`
  - `routes.py`
- `long_memory/`
  - `store.py`
  - `extractor.py`
  - `formatters.py`
  - `models.py`
  - `utils.py`

## 5. 分阶段计划

### 阶段 1：拆分 Web 聚合点

范围：

- 从 `web_app.py` 中拆出会话存储逻辑
- 从 `web_app.py` 中拆出超大前端模板资源
- 保留 `web_app.py` 作为兼容入口，继续提供 `Handler`、`main()` 和现有公开符号

目标：

- 明显缩小 `web_app.py`
- 降低“Python 服务逻辑”和“前端资源字符串”耦合
- 不改变当前网站行为和测试结果

### 阶段 2：拆分五子棋 AI 引擎

范围：

- 从 `game_ai.py` 拆出搜索配置、评估函数、候选点、威胁分析、VCF 搜索和主搜索

目标：

- 把 AI 算法从单文件聚合改为组合式结构
- 为后续继续增强棋力留出更清晰的插入点

### 阶段 3：统一 Agent 共享逻辑

范围：

- 抽离 `agent.py` 与 `multi_agent.py` 中重复的最终回答清洗、步骤序列化、游戏观察压缩逻辑
- 尽量保持旧入口兼容，避免影响现有调用与测试

目标：

- 减少重复实现
- 让 Legacy 与 Multi-Agent 共用一套横切逻辑

### 阶段 4：整理 LLM 与 Memory 层

范围：

- 拆分 `llm_client.py`
- 拆分 `memory_store.py`

目标：

- 让模型调用、流式解析、重试和记忆存取边界更清晰

## 6. 本次执行范围

本次根据 spec 已执行：

- 新增 `web/` 子模块
- 抽出会话存储逻辑到 `web/conversation_store.py`
- 抽出超大 HTML 页面资源到 `web/frontend.py`
- 保留 `web_app.py` 兼容当前测试与启动方式
- 新增 `gomoku_ai/` 子模块
- 将 `game_ai.py` 拆分为 `models.py`、`evaluation.py`、`tactics.py`、`search.py`
- 保留 `game_ai.py` 兼容导出入口，确保现有导入不受影响
- 新增 `agent_shared.py`
- 抽出 Legacy / Multi-Agent 共用的回答清洗、棋局观察压缩、步骤序列化、JSON 解析与答案分块逻辑
- 保留 `MiniReActAgent` 的兼容静态方法入口，降低已有测试和调用改动范围
- 新增 `llm/` 子模块，拆出 `client.py`、`errors.py`、`stream_parser.py`、`retry_policy.py`
- 保留 `llm_client.py` 兼容导出入口，确保现有导入不受影响
- 新增 `long_memory/` 子模块，拆出 `store.py`、`extractor.py`、`formatters.py`、`models.py`、`utils.py`
- 保留 `memory_store.py` 兼容导出入口，确保现有导入不受影响

## 7. 风险与回退

主要风险：

- `web_app.py` 中的前端脚本是超大字符串，迁移时容易遗漏引号或插值结构
- 现有测试和运行入口依赖 `web_app.py` 公开符号，拆分时需要保留兼容导出

回退策略：

- 若拆分后测试失败，保留新模块但先恢复 `web_app.py` 的旧引用路径
- 阶段 1 不修改业务协议，只做代码搬迁，便于快速回退

## 8. 验证计划

- 运行 `tests.test_web_app`
- 运行 `tests.test_stream_memory_multi_agent`
- 运行 `tests.test_game`
- 用诊断检查新增模块和 `web_app.py`
- 重启本地网站并确认页面正常打开

## 9. 执行状态

- 阶段 1（Web 聚合点拆分）：已完成
- 阶段 2（五子棋 AI 引擎拆分）：已完成
- 阶段 3（统一 Agent 共享逻辑）：已完成
- 阶段 4（整理 LLM 与 Memory 层）：已完成
