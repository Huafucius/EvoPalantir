# AOS Hook Spec

_Hook 体系。所有扩展点的名称、语义分类、触发时机、注册规则。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-plugin.md](./aos-plugin.md) · [aos-lifecycle.md](./aos-lifecycle.md)_

---

## 1. 总则

### 1.1 三种语义分类

| 维度       | Admission Hook     | Transform Hook                 | Runtime Event            |
| ---------- | ------------------ | ------------------------------ | ------------------------ |
| 执行方式   | 同步，串行         | 同步，串行                     | 异步，fire-and-forget    |
| 可否拒绝   | 可以（抛出异常）   | 不可以                         | 不可以                   |
| 可否改写   | 可改写 input       | 可改写 output                  | 只读                     |
| 阻塞主流程 | 是                 | 是                             | 否                       |
| 错误处理   | 抛出即失败当前操作 | 抛出即降级为原始数据，操作继续 | 错误被隔离，不影响主流程 |

下文简称 Admission Hook 为 `AH`、Transform Hook 为 `TH`、Runtime Event 为 `RE`。

### 1.2 扁平注册

开发者返回一个 hooks 对象。内核根据 hook 名字自动判断语义分类，不需要开发者声明类型。

```python
return {
    "session.dispatch.before": my_guard,      # 内核知道这是 Admission
    "session.messages.transform": my_rewrite, # 内核知道这是 Transform
    "session.dispatch.after": my_logger,      # 内核知道这是 Event
}
```

### 1.3 TH 的两类用途

所有 TH 语义相同（串行执行，改写 output），但按用途分为两类惯例：

- **算法 TH**（`context.assemble`、`context.compact`、`skill.discovery.resolve`、`compute.model.resolve`）：提供核心算法实现，通常由引擎 Skill 注册。后注册的 handler 输出覆盖先前结果。
- **微调 TH**（`session.messages.transform`、`compute.params.transform` 等）：叠加式修改流经数据，由任意 Skill 注册。

二者无语义差异，区别仅在于用途惯例。算法 TH 无 handler 时内核不提供默认行为——必须由 Skill（通常是 `aos-context`）注册 handler。

### 1.4 Owner 可见性与注册权限

| ownerType | 可注册 Admission Hook | 可注册 Transform Hook                                                                             | 可订阅 Runtime Event |
| --------- | --------------------- | ------------------------------------------------------------------------------------------------- | -------------------- |
| `system`  | 全部                  | 全部                                                                                              | 全部                 |
| `agent`   | agent / session 相关  | 全部                                                                                              | agent / session 级   |
| `session` | session 相关          | session / tool / compute / context 相关（context.assemble / context.compact 属 session 粒度操作） | session 级           |

越权注册必须在注册时立即失败。

上表为概要规则。部分 hook 虽名称前缀为 `skill.*`，但在 session 上下文中触发（如 bootstrap 阶段的 `skill.load.before`、`skill.default.resolve.before`），因此允许 session-owned 注册。每个 hook 的准确 owner 范围以 §2–§4 详细表格和 §6 总表为准。

### 1.5 执行顺序

Admission Hook 和 Transform Hook 按 owner 层级串行执行：system → agent → session（forward 方向）。

Runtime Event 并行投递，订阅者之间互相独立。

---

## 2. Admission Hooks (13)

同步准入拦截器。`input` 为只读上下文；`output` 为可改写参数（改写 output 修改操作参数；拒绝时抛异常）。

### Skill 相关 (6)

| hook                           | 可注册 owner             | 时机                                     | input                            | output          |
| ------------------------------ | ------------------------ | ---------------------------------------- | -------------------------------- | --------------- |
| `skill.index.refresh.before`   | system                   | 重新扫描 skill 元数据前                  | skillRoot                        | —               |
| `skill.discovery.before`       | session / agent / system | discover 策略执行前                      | ownerType, ownerId, query        | query（可改写） |
| `skill.default.resolve.before` | session / agent / system | bootstrap/reinject 解析默认 skill 集合前 | ownerType, ownerId, plannedNames | —               |
| `skill.load.before`            | session / agent / system | load skillText 前                        | name, sessionId                  | —               |
| `skill.start.before`           | session / agent / system | start plugin 前                          | skillName, ownerType, ownerId    | —               |
| `skill.stop.before`            | session / agent / system | 停止 plugin 前                           | instanceId                       | —               |

### Session 相关 (5)

| hook                          | 可注册 owner             | 时机           | input                                              | output            |
| ----------------------------- | ------------------------ | -------------- | -------------------------------------------------- | ----------------- |
| `session.dispatch.before`     | session / agent / system | dispatch 准入  | agentId, sessionId, userMessage                    | —                 |
| `session.bootstrap.before`    | session / agent / system | 默认注入前     | agentId, sessionId, plannedNames                   | —                 |
| `session.reinject.before`     | session / agent / system | reinject 前    | agentId, sessionId, plannedNames                   | —                 |
| `session.message.beforeWrite` | session / agent / system | 消息写入 SH 前 | agentId, sessionId, message                        | message（可替换） |
| `session.compaction.before`   | session / agent / system | compaction 前  | agentId, sessionId, fromSeq, toSeq（内核建议区间） | —                 |

### Compute / Tool 相关 (2)

| hook             | 可注册 owner             | 时机            | input                       | output             |
| ---------------- | ------------------------ | --------------- | --------------------------- | ------------------ |
| `compute.before` | session / agent / system | 每次 LLM 调用前 | agentId, sessionId, lastSeq | —                  |
| `tool.before`    | session / agent / system | bash 执行前     | toolCallId, args            | args（可改写命令） |

---

## 3. Transform Hooks (9)

同步数据改写器。改写流经数据，不可拒绝操作。`output` 为可改写数据。

### 微调 TH (5)

| hook                         | 可注册 owner             | 时机                      | input                            | output                          |
| ---------------------------- | ------------------------ | ------------------------- | -------------------------------- | ------------------------------- |
| `session.system.transform`   | session / agent / system | RU 调用前构造 system 注入 | agentId, sessionId, userMessage? | system（可覆盖）                |
| `session.messages.transform` | session / agent / system | RU 调用前投影完成后       | agentId, sessionId, messages     | messages（可改写）              |
| `compute.params.transform`   | session / agent / system | LLM 参数构造完成后        | agentId, sessionId, params       | params（可改写）                |
| `tool.env`                   | session / agent / system | bash 执行前               | toolCallId, args                 | env（合并环境变量）             |
| `tool.after`                 | session / agent / system | bash 执行后               | toolCallId, rawResult            | result（可改写 visible result） |

`tool.after` 读取 rawResult，返回的 result 成为 visible result 写入 SH。rawResult 由 AOS 记入 RL。`aos-context` Skill 在此 Hook 中执行大内容判定：检查 `len(result) > autoFoldThreshold`，超阈值时通过 AOSCP `content.put` 存入 ContentStore，返回修改后的 output（contentId 引用）。

Transform Hook 的结果只影响当次调用，不写入 SH，不修改 SC 持久状态。

### 算法 TH (4)

内核不提供算法 TH 的默认实现。这些 Hook 通常由 Skill 注册（`context.assemble` / `context.compact` 由 `aos-context` Skill 提供）。如无 handler，`context.assemble` 返回空消息列表，`context.compact` 不执行——上下文将持续膨胀直至溢出，这是预期行为。

| hook                      | 可注册 owner             | 时机                    | input                                         | output                                   |
| ------------------------- | ------------------------ | ----------------------- | --------------------------------------------- | ---------------------------------------- |
| `context.assemble`        | session / agent / system | 内核需要构建/更新 SC 时 | 详见下文 §3.5.1                               | 详见下文 §3.5.1                          |
| `context.compact`         | session / agent / system | compaction 触发时       | 详见下文 §3.5.2                               | 详见下文 §3.5.2                          |
| `skill.discovery.resolve` | session / agent / system | discover 算法执行时     | query, candidates, ownerType, ownerId, limit? | selectedSkills: SkillManifest[], scores? |
| `compute.model.resolve`   | session / agent / system | 每次 LLM 调用前         | agentId, sessionId, requestType               | provider, model, params?                 |

#### 3.5.1 context.assemble 详细契约

内核在需要构建或更新 SC 时调用。

**input（只读）：**

| 字段        | 类型    | 含义                                   |
| ----------- | ------- | -------------------------------------- |
| sessionId   | string  | 目标 Session                           |
| agentId     | string  | 所属 Agent                             |
| tokenBudget | integer | token 上限（三层继承解析后）           |
| trigger     | string  | 触发类型                               |
| triggerData | object? | 触发附加数据（fold/unfold 时携带 ref） |

**trigger 类型：**

| trigger       | 时机                                           |
| ------------- | ---------------------------------------------- |
| `rebuild`     | 全量重建（bootstrap、recovery、compaction 后） |
| `dispatch`    | dispatch 接收用户消息后                        |
| `incremental` | ReAct 循环中工具结果追加后                     |
| `fold`        | 用户或 auto-fold 触发折叠                      |
| `unfold`      | 用户触发展开                                   |

**output（可改写）：**

| 字段            | 类型             | 含义                 |
| --------------- | ---------------- | -------------------- |
| messages        | ContextMessage[] | 构建的上下文消息序列 |
| estimatedTokens | number           | 预估 token 数        |

**ContextMessage 格式：**

```json
{
  "wire": { "role": "...", "content": "..." },
  "aos": { "sourceMessageId": "...", "sourcePartId": "...", "kind": "..." }
}
```

kind 枚举：`user-input` · `assistant-output` · `tool-bash-call` · `tool-bash-result` · `tool-bash-folded` · `skill-load` · `compaction-marker` · `compaction-summary` · `interrupt` · `message-folded`

**调用时机：**

| 时机                  | trigger       |
| --------------------- | ------------- |
| Bootstrap 完成        | `rebuild`     |
| Dispatch 接收用户消息 | `dispatch`    |
| 工具结果追加到 SH     | `incremental` |
| Fold 操作             | `fold`        |
| Unfold 操作           | `unfold`      |
| Compaction 完成       | `rebuild`     |
| Recovery              | `rebuild`     |

#### 3.5.2 context.compact 详细契约

内核在压缩触发时调用（阈值超限或手动 `session.compact`）。

**input（只读）：**

| 字段            | 类型                        | 含义                         |
| --------------- | --------------------------- | ---------------------------- |
| sessionId       | string                      | 目标 Session                 |
| agentId         | string                      | 所属 Agent                   |
| reason          | `"threshold"` \| `"manual"` | 触发原因                     |
| proposedFromSeq | integer                     | 内核建议的压缩区间起始（含） |
| proposedToSeq   | integer                     | 内核建议的压缩区间结束（含） |

**output（可改写）：**

| 字段           | 类型                        | 含义                                         |
| -------------- | --------------------------- | -------------------------------------------- |
| mode           | `"instruct"` \| `"managed"` | 执行模式                                     |
| summaryPrompt  | string?                     | instruct 模式：LLM prompt                    |
| summaryText    | string?                     | instruct 模式：直接提供摘要（跳过 LLM）      |
| fromSeq        | integer                     | 最终压缩区间起始（含）；引擎可调整内核建议值 |
| toSeq          | integer                     | 最终压缩区间结束（含）；引擎可调整内核建议值 |
| reinjectSkills | boolean                     | 压缩后是否重新注入 skill                     |

**两种模式：**

| 模式       | 含义                                                                          |
| ---------- | ----------------------------------------------------------------------------- |
| `instruct` | 引擎返回 prompt/摘要，内核负责 LLM 调用和 SH 写入                             |
| `managed`  | 引擎通过 AOSCP 自行完成压缩相关的 SH 写入（Marker/Summary），内核不介入这部分 |

**instruct 模式内核执行步骤：**

1. 若引擎未提供 summaryText：用 summaryPrompt 调用 LLM 生成摘要
2. 追加 CompactionMarkerMessage 到 SH
3. 追加 CompactionSummaryMessage 到 SH（`finish: completed`）
4. 若 `reinjectSkills: true`：执行 reinject 流程
5. 调用 `context.assemble` (trigger=rebuild)

**managed 模式：**

引擎自行通过 AOSCP 操作（`session.append`、`session.history.list` 等）完成压缩相关的 SH 写入（Marker/Summary）。内核不介入这部分。SH 写入完成后，reinject（若 `reinjectSkills: true`）、`context.assemble` (trigger=rebuild) 和 phase 复位仍由内核执行——这些涉及 Hook 触发、Skill 加载和状态管理，非引擎职责。

**崩溃回退：** 引擎崩溃或超时时，操作失败。Compaction 失败时 phase 回退到之前状态。

---

## 4. Runtime Events (22)

异步只读通知，fire-and-forget，不阻塞主流程。`payload` 为只读数据。

### AOS 级 (2)

| event          | 可见 owner | 时机         | payload                       |
| -------------- | ---------- | ------------ | ----------------------------- |
| `aos.started`  | system     | AOS 启动完成 | cause, timestamp, catalogSize |
| `aos.stopping` | system     | AOS 即将停止 | reason, timestamp             |

### Skill 级 (6)

| event                         | 可见 owner               | 时机                                     | payload                           |
| ----------------------------- | ------------------------ | ---------------------------------------- | --------------------------------- |
| `skill.index.refresh.after`   | system                   | 扫描完成后                               | indexedCount                      |
| `skill.discovery.after`       | session / agent / system | discover 完成后                          | ownerType, ownerId, catalog       |
| `skill.default.resolve.after` | session / agent / system | bootstrap/reinject 默认 skill 解析完成后 | ownerType, ownerId, resolvedNames |
| `skill.load.after`            | session / agent / system | load 完成后                              | name, sessionId, skillText        |
| `skill.start.after`           | session / agent / system | plugin 启动后                            | instanceId, skillName             |
| `skill.stop.after`            | session / agent / system | plugin 停止后                            | instanceId                        |

### Agent 级 (2)

| event            | 可见 owner     | 时机               | payload                   |
| ---------------- | -------------- | ------------------ | ------------------------- |
| `agent.started`  | agent / system | Agent 创建或恢复后 | agentId, cause, timestamp |
| `agent.archived` | agent / system | Agent 归档后       | agentId, timestamp        |

### Session 级 (8)

| event                      | 可见 owner               | 时机           | payload                                       |
| -------------------------- | ------------------------ | -------------- | --------------------------------------------- |
| `session.started`          | session / agent / system | bootstrap 完成 | agentId, sessionId, cause, timestamp          |
| `session.archived`         | session / agent / system | 归档后         | agentId, sessionId, timestamp                 |
| `session.dispatch.after`   | session / agent / system | dispatch 完成  | agentId, sessionId, dispatchId, appendedCount |
| `session.bootstrap.after`  | session / agent / system | 默认注入后     | agentId, sessionId, injectedNames             |
| `session.reinject.after`   | session / agent / system | reinject 后    | agentId, sessionId, injectedNames             |
| `session.compaction.after` | session / agent / system | compaction 后  | agentId, sessionId, compactionSeq             |
| `session.error`            | session / agent / system | 运行失败       | source, recoverable, message                  |
| `session.interrupted`      | session / agent / system | 中断           | agentId, sessionId, reason                    |

### Context 级 (2)

| event               | 可见 owner               | 时机              | payload                                                              |
| ------------------- | ------------------------ | ----------------- | -------------------------------------------------------------------- |
| `context.ingest`    | session / agent / system | SH 消息写入后     | sessionId, agentId, message, seq                                     |
| `context.afterTurn` | session / agent / system | ReAct turn 完成后 | sessionId, agentId, turnIndex, toolCalls, appendedCount, finalAnswer |

### Compute 级 (1)

| event           | 可见 owner               | 时机         | payload                                  |
| --------------- | ------------------------ | ------------ | ---------------------------------------- |
| `compute.after` | session / agent / system | LLM 调用结束 | agentId, sessionId, appendedMessageCount |

### Plugin 级 (1)

| event          | 可见 owner | 时机              | payload                                  |
| -------------- | ---------- | ----------------- | ---------------------------------------- |
| `plugin.error` | owner 向上 | plugin 子进程崩溃 | instanceId, skillName, exitCode, message |

「owner 向上」：session-owned 可被 session/agent/system 接收；agent-owned 可被 agent/system 接收；system-owned 仅 system 接收。

---

## 5. Hook 签名（stdio JSON-RPC）

### 5.1 Admission Hook 调用

daemon → plugin：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "hook",
  "params": {
    "name": "tool.before",
    "input": { "toolCallId": "...", "args": { "command": "rm -rf /" } },
    "output": { "args": { "command": "rm -rf /" } }
  }
}
```

plugin → daemon（允许）：

```json
{ "jsonrpc": "2.0", "id": 1, "result": { "action": "allow" } }
```

plugin → daemon（拒绝）：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { "action": "reject", "reason": "dangerous command" }
}
```

plugin → daemon（改写 output）：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "action": "allow",
    "output": { "args": { "command": "echo safe" } }
  }
}
```

### 5.2 Transform Hook 调用

daemon → plugin：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "hook",
  "params": {
    "name": "tool.after",
    "input": { "toolCallId": "...", "rawResult": "..." },
    "output": { "result": "..." }
  }
}
```

plugin → daemon：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": { "output": { "result": "<modified visible result>" } }
}
```

### 5.3 Runtime Event 通知

daemon → plugin（不期望响应）：

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "name": "session.dispatch.after",
    "payload": { "agentId": "...", "sessionId": "...", "dispatchId": "..." }
  }
}
```

---

## 6. 扩展点总表

| 名称                         | 分类 | 允许的 owner             |
| ---------------------------- | ---- | ------------------------ |
| skill.index.refresh.before   | AH   | system                   |
| skill.discovery.before       | AH   | system / agent / session |
| skill.default.resolve.before | AH   | system / agent / session |
| skill.load.before            | AH   | system / agent / session |
| skill.start.before           | AH   | system / agent / session |
| skill.stop.before            | AH   | system / agent / session |
| session.dispatch.before      | AH   | system / agent / session |
| session.bootstrap.before     | AH   | system / agent / session |
| session.reinject.before      | AH   | system / agent / session |
| session.message.beforeWrite  | AH   | system / agent / session |
| session.compaction.before    | AH   | system / agent / session |
| compute.before               | AH   | system / agent / session |
| tool.before                  | AH   | system / agent / session |
| context.assemble             | TH   | system / agent / session |
| context.compact              | TH   | system / agent / session |
| skill.discovery.resolve      | TH   | system / agent / session |
| compute.model.resolve        | TH   | system / agent / session |
| session.system.transform     | TH   | system / agent / session |
| session.messages.transform   | TH   | system / agent / session |
| compute.params.transform     | TH   | system / agent / session |
| tool.env                     | TH   | system / agent / session |
| tool.after                   | TH   | system / agent / session |
| aos.started                  | RE   | system                   |
| aos.stopping                 | RE   | system                   |
| skill.index.refresh.after    | RE   | system                   |
| skill.discovery.after        | RE   | system / agent / session |
| skill.default.resolve.after  | RE   | system / agent / session |
| skill.load.after             | RE   | system / agent / session |
| skill.start.after            | RE   | system / agent / session |
| skill.stop.after             | RE   | system / agent / session |
| agent.started                | RE   | system / agent           |
| agent.archived               | RE   | system / agent           |
| session.started              | RE   | system / agent / session |
| session.archived             | RE   | system / agent / session |
| session.dispatch.after       | RE   | system / agent / session |
| session.bootstrap.after      | RE   | system / agent / session |
| session.reinject.after       | RE   | system / agent / session |
| session.compaction.after     | RE   | system / agent / session |
| session.error                | RE   | system / agent / session |
| session.interrupted          | RE   | system / agent / session |
| context.ingest               | RE   | system / agent / session |
| context.afterTurn            | RE   | system / agent / session |
| compute.after                | RE   | system / agent / session |
| plugin.error                 | RE   | owner 向上               |

合计：13 AH + 9 TH + 22 RE = **44 个扩展点**。
