# [OPEN] game-state-resume

## 问题

- 症状：网站下完一局棋后，在 Trae 中切换页面，再回到该页面时，界面仍显示棋局进行中。
- 期望：回到页面后应展示真实终局状态，不应继续显示进行中的棋局。

## 当前假设

1. 页面切回时没有触发前端可见性/焦点同步逻辑，因此仍直接显示旧内存状态。
2. 终局后某次异步流程又把旧的 `playing` 状态重新写回了 `gameState` 或 `activeGameStates`。
3. 页面恢复时 `trackedGameId()` 取到了错误的棋局 ID，导致同步接口查询的不是当前面板对应的棋局。
4. 棋局终局后虽然状态已更新，但某个旧 DOM 面板仍保留 `data-active="true"`，恢复时被重新绑定成当前活跃棋局。
5. Trae 页面切换的恢复机制不是 `visibilitychange/focus/pageshow`，导致当前同步钩子根本没有被执行。

## 调试计划

1. 给前端关键路径加最小化运行时埋点：保存缓存、恢复页面、终局写入、切页恢复、状态同步。
2. 复现一次“终局 -> 切页 -> 返回”流程并采集日志。
3. 根据日志排除/确认假设，再做最小修复。
4. 用修复前后日志对比验证问题是否消失。

## 已收集证据

- `pre-fix` 日志显示棋局先正确进入 `finished`，随后调用了 `freezeGamePanel`。
- 页面恢复时，`visibilitychange` 与 `syncCurrentGameState:start` 的确被触发，说明恢复事件监听不是主因。
- 在恢复阶段又出现了一次 `applyGameState(status=playing)`，发生在 `restoreChat` 之前，说明旧状态来自历史恢复流程而不是服务端终局接口。
- 结合代码定位，`restoreConversationFromServer()` 在渲染历史步骤时会调用 `renderStep()`，而 `renderStep()` 会触发 `maybeShowGameFromToolStep()`，把旧的 `game_*` 工具观察重新应用到当前棋局状态。

## 当前结论

- 已排除假设 1、3、5 为主因。
- 已确认假设 2、4 的组合路径成立：不是服务端把棋局改回进行中，而是历史会话恢复时重放了旧工具结果，导致前端缓存和当前面板被回写成旧的 `playing` 状态。

## 已实施修复

1. 历史会话恢复时，不再重放旧 `game_*` 步骤到当前棋局状态。
2. 历史步骤仅提取 `game_id`，供后续 `syncCurrentGameState()` 向服务端同步真实状态。
3. 保留调试埋点，后续用 `post-fix` 日志验证问题是否消失。
