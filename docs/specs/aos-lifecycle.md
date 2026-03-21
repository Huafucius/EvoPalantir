# AOS Lifecycle Spec

_生命周期时序。启动、bootstrap、dispatch、恢复、归档。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-hooks.md](./aos-hooks.md) · [aos-data-model.md](./aos-data-model.md)_

---

## 1. Daemon 生命周期

### 1.1 启动

| 步骤 | 动作                                                | Hook                                                                                       |
| ---- | --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| 1    | 读取 AOS_API_TOKEN（未设置则拒绝启动）              | —                                                                                          |
| 2    | 初始化 Store（SQLite 或配置的后端）                 | —                                                                                          |
| 3    | 初始化 AOSCB（见下文）                              | —                                                                                          |
| 4    | skill.index.refresh（扫描 skillRoot）               | AH: `skill.index.refresh.before` → RE: `skill.index.refresh.after`                         |
| 5    | 注册内建 skill `aos` + `aos-context`                | —                                                                                          |
| 6    | system 级 discover                                  | AH: `skill.discovery.before` → TH: `skill.discovery.resolve` → RE: `skill.discovery.after` |
| 7    | 预热 system 级默认 load skillText 缓存              | —                                                                                          |
| 8    | 启动 system 级默认 start plugin（含 `aos-context`） | AH: `skill.start.before` → RE: `skill.start.after`                                         |
| 9    | 绑定 HTTP 端口                                      | —                                                                                          |
| 10   | 开始接受请求                                        | RE: `aos.started`                                                                          |

**AOSCB 初始化规则：**

- 首次启动（Store 中无 AOSCB）：创建 AOSCB，`name` 取 `AOS_NAME` 环境变量（默认 `"default"`），`skillRoot` 取 `AOS_SKILL_ROOT`（默认 `"./skills"`），其余字段取默认值。
- 后续启动（Store 中已有 AOSCB）：读取已有 AOSCB，用当前环境变量刷新 `name` 和 `skillRoot`。这两个字段反映部署配置而非业务状态，以环境变量为权威。
- `defaultSkills`、`autoFoldThreshold`、`compactionThreshold`、`maxTurns` 等业务配置字段不受环境变量影响，仅通过 `system.update` 修改。

### 1.2 热重载

file watcher 监听 skillRoot 变化：

- SKILL.md 新增/变更：刷新 SkillManifest，失效 skillText 缓存，RE: `skill.index.refresh.after`
- SKILL.md 删除：从索引中移除
- 运行中 Plugin 继续使用启动时的版本，直到 owner 生命周期结束或显式重启

### 1.3 优雅关闭

| 步骤 | 动作                                                     |
| ---- | -------------------------------------------------------- |
| 1    | RE: `aos.stopping`                                       |
| 2    | 停止接受新请求                                           |
| 3    | Drain 所有活跃 dispatch（等待当前 ReAct 循环完成或超时） |
| 4    | 停止所有 Plugin 子进程                                   |
| 5    | 关闭 HTTP server                                         |
| 6    | 关闭 Store 连接                                          |

### 1.4 后台运行

- `aos daemon start` — 前台运行，Ctrl+C 优雅退出
- `aos daemon start --detach` — 后台运行
- `aos daemon stop` — 停止后台 daemon

---

## 2. Agent 生命周期

### 2.1 创建 / 激活

| 步骤 | 动作                                  | Hook                                               |
| ---- | ------------------------------------- | -------------------------------------------------- |
| 1    | 读取/创建 ACB                         | —                                                  |
| 2    | 预热 agent 级默认 load skillText 缓存 | —                                                  |
| 3    | agent 级 start reconcile              | AH: `skill.start.before` → RE: `skill.start.after` |
| 4    | 建立 agent 级 event 订阅              | —                                                  |
| 5    | Agent ready                           | RE: `agent.started`                                |

### 2.2 归档

| 步骤 | 动作                                   | Hook                                             |
| ---- | -------------------------------------- | ------------------------------------------------ |
| 1    | 停止 agent 下所有 Plugin               | AH: `skill.stop.before` → RE: `skill.stop.after` |
| 2    | ACB.status = `archived`, 写 archivedAt | —                                                |
| 3    | ACB/SH 保留                            | RE: `agent.archived`                             |

---

## 3. Session 生命周期

### 3.1 状态机

```
initializing → ready → archived
```

### 3.2 Phase（与状态正交）

```
idle → dispatched → idle
idle → compacting → idle
dispatched → interrupted → idle
```

### 3.3 Bootstrap

| 步骤 | 动作                                    | 写入 | Hook                                                                                       |
| ---- | --------------------------------------- | ---- | ------------------------------------------------------------------------------------------ |
| 1    | 创建/读取 SCB, status=`initializing`    | SCB  | —                                                                                          |
| 2    | 预热 session 级默认 load skillText 缓存 | —    | —                                                                                          |
| 3    | session 级 start reconcile              | —    | AH: `skill.start.before` → RE: `skill.start.after`                                         |
| 4    | phase = `bootstrapping`                 | SCB  | —                                                                                          |
| 5    | 追加 begin marker                       | SH   | AH: `session.message.beforeWrite`                                                          |
| 6    | skill.default.resolve                   | —    | AH: `skill.default.resolve.before` → RE: `skill.default.resolve.after`                     |
| 7    | 开始默认注入                            | —    | AH: `session.bootstrap.before`                                                             |
| 8    | 注入默认 load skill skillText           | SH   | AH: `skill.load.before` → RE: `skill.load.after` (each)                                    |
| 9    | 追加 done marker                        | SH   | AH: `session.message.beforeWrite`                                                          |
| 10   | 结束默认注入                            | —    | RE: `session.bootstrap.after`                                                              |
| 11   | 构建 SC                                 | —    | TH: `context.assemble` (trigger=rebuild)                                                   |
| 12   | session 级 discover                     | —    | AH: `skill.discovery.before` → TH: `skill.discovery.resolve` → RE: `skill.discovery.after` |
| 13   | status=`ready`, phase=`idle`            | SCB  | RE: `session.started`                                                                      |

**默认 load 解析规则：**

1. 取 AOSCB / ACB / SCB 三层 SkillDefaultRule，只看 load 条目
2. system → agent → session 顺序覆盖同名冲突
3. 最终保留 load=enable 的 skill
4. 从 skillText 缓存取正文
5. 强制追加 `aos` skill
6. 按 system → agent → session 排序注入；每个 skill 一条消息

**默认 start reconcile 规则：**

1. 取 AOSCB / ACB / SCB 三层 SkillDefaultRule，只看 start 条目
2. system → agent → session 顺序覆盖同名冲突：后层 disable 压掉前层 enable（aos-context 的替换不走此规则，见下文替换机制）
3. 最终保留 start=enable 且具有 `plugin` 字段声明的 skill
4. 对目标集合与当前已运行 Plugin 集合求差集：新增的执行 `skill.start`，多余的执行 `skill.stop`

start reconcile 在三个层级分别执行：daemon 启动时（system 级）、Agent 激活时（agent 级）、Session bootstrap 时（session 级）。每级只处理属于该 ownerType 的 Plugin。

**上下文引擎替换机制：** `aos-context` 作为 system-owned Plugin 始终运行。自定义引擎以 agent/session-owned Plugin 身份注册同名算法 TH（`context.assemble`、`context.compact`）。TH 按 owner 层级串行执行（system → agent → session），后注册者的输出覆盖前者。因此替换不是 stop 旧进程，而是 TH 覆盖链——自定义引擎的输出自然取代 `aos-context` 的输出。

---

## 4. Dispatch 流程

### 4.1 执行顺序

| 步骤 | 动作                                                     | 写入  | Hook                                      |
| ---- | -------------------------------------------------------- | ----- | ----------------------------------------- |
| 1    | 校验：status=ready, phase=idle                           | —     | —                                         |
| 2    | Admission: session.dispatch.before                       | —     | AH: `session.dispatch.before`             |
| 3    | 追加 userMessage 到 SH                                   | SH    | AH: `session.message.beforeWrite`         |
| 4    | 构建 SC                                                  | —     | TH: `context.assemble` (trigger=dispatch) |
| 5    | 获取 lease，phase = `dispatched`                         | SCB   | —                                         |
| 6    | 创建 dispatchId；**异步分界点**——此后 ReActUnit 独立推进 | —     | —                                         |
| 7    | 创建 ReActUnit                                           | —     | —                                         |
| 8    | ReActUnit 执行 ReAct 循环                                | SH/SC | （见 4.2）                                |
| 9    | 释放 lease，phase = `idle`                               | SCB   | —                                         |
| 10   | 写 RL                                                    | RL    | RE: `session.dispatch.after`              |

步骤 6 是内核内部的异步切分点。AOSCP 层始终返回 `{ sessionId, dispatchId }`。客户端通过传输层决定后续行为：fire-and-forget 立即结束，streaming / blocking 连接 SSE dispatch 流接收中间事件和最终 `done` 事件（携带 finalMessageSeq、usage）。三种模式的客户端契约见 [aos-aoscp.md](./aos-aoscp.md) §5.2。

### 4.2 ReAct 循环

| 步骤 | 动作                                                                                                                        | 写入  | Hook                                                                                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------- | ----- | --------------------------------------------------------------------------------------------- |
| 1    | 取 SC.messages                                                                                                              | —     | —                                                                                             |
| 2    | Transform: system → messages → params                                                                                       | —     | TH: `session.system.transform` → `session.messages.transform` → `compute.params.transform`    |
| 3    | 解析模型                                                                                                                    | —     | TH: `compute.model.resolve`                                                                   |
| 4    | Admission: compute.before                                                                                                   | —     | AH: `compute.before`                                                                          |
| 5    | 调用 LLM（使用 compute.model.resolve 结果）                                                                                 | —     | —                                                                                             |
| 6    | 判断返回类型                                                                                                                | —     | —                                                                                             |
| 6a   | tool_call → TH: tool.env                                                                                                    | —     | TH: `tool.env`                                                                                |
| 6b   | AH: tool.before                                                                                                             | —     | AH: `tool.before`                                                                             |
| 6c   | 执行 bash                                                                                                                   | —     | —                                                                                             |
| 6d   | TH: tool.after → visible result（`aos-context` 在此判定大内容，超阈值时通过 `content.put` 存入 ContentStore 并改写 output） | blob? | TH: `tool.after`                                                                              |
| 6e   | 写 SH（assistant + tool result，使用 tool.after 返回的 output）                                                             | SH    | AH: `session.message.beforeWrite` (each)                                                      |
| 6f   | 更新 SC                                                                                                                     | —     | TH: `context.assemble` (trigger=incremental) · RE: `context.ingest` · RE: `context.afterTurn` |
| 6g   | 返回步骤 1                                                                                                                  | —     | —                                                                                             |
| 7    | final answer → 写 SH                                                                                                        | SH    | AH: `session.message.beforeWrite`                                                             |
| 8    | RE: compute.after                                                                                                           | —     | RE: `compute.after`                                                                           |
| 9    | 检查终止条件                                                                                                                | —     | —                                                                                             |
| 9a   | 继续 → 步骤 1                                                                                                               | —     | —                                                                                             |
| 9b   | interrupt → 写 interrupt 事实                                                                                               | SH    | RE: `session.interrupted`                                                                     |
| 9c   | compaction → 见第 5 节                                                                                                      | SH    | —                                                                                             |
| 9d   | 完成 → 退出循环                                                                                                             | —     | —                                                                                             |

---

## 5. Compaction 流程

| 步骤 | 动作                                                 | 写入 | Hook                                                         |
| ---- | ---------------------------------------------------- | ---- | ------------------------------------------------------------ |
| 1    | phase = `compacting`                                 | SCB  | —                                                            |
| 2    | 计算建议区间 [fromSeq, toSeq]                        | —    | —                                                            |
| 3    | Admission: session.compaction.before（携带建议区间） | —    | AH: `session.compaction.before`                              |
| 4    | 调用上下文引擎；引擎输出的 fromSeq/toSeq 为最终区间  | —    | TH: `context.compact`                                        |
| 5    | 若 mode=instruct 且无 summaryText：调用 LLM 生成摘要 | —    | —                                                            |
| 6    | 追加 CompactionMarkerMessage（instruct 模式）        | SH   | AH: `session.message.beforeWrite`                            |
| 7    | 追加 CompactionSummaryMessage（instruct 模式）       | SH   | AH: `session.message.beforeWrite`                            |
| 8    | reinject（若 reinjectSkills=true）                   | SH   | AH: `session.reinject.before` → RE: `session.reinject.after` |
| 9    | 重建 SC                                              | —    | TH: `context.assemble` (trigger=rebuild)                     |
| 10   | phase = `idle`                                       | SCB  | RE: `session.compaction.after`                               |

步骤 5-7 在 `mode=managed` 时跳过——引擎自行通过 AOSCP 完成 SH 写入。步骤 8-10（reinject、rebuild、phase 复位）在两种模式下均由内核执行。

失败回滚：compaction 过程中异常，phase 回退到之前状态。

---

## 6. Plugin 生命周期

### 6.1 启动

| 步骤 | 动作                                                                                                                             |
| ---- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1    | daemon spawn 子进程（SKILL.md 中 `plugin` 字段指定的可执行文件）                                                                 |
| 2    | 注入环境变量：AOS_API_URL、AOS_API_TOKEN；agent-owned 额外注入 AOS_AGENT_ID；session-owned 额外注入 AOS_AGENT_ID、AOS_SESSION_ID |
| 3    | 等待 Plugin 发送 `register` 消息（超时 10 秒）                                                                                   |
| 4    | 验证注册权限（owner 级别校验）                                                                                                   |
| 5    | 状态 = `running`                                                                                                                 |

### 6.2 崩溃处理

| 步骤 | 动作                                       |
| ---- | ------------------------------------------ |
| 1    | 检测到子进程退出                           |
| 2    | 状态 = `error`，记录 exitCode 和 lastError |
| 3    | 注销该 Plugin 注册的所有 Hook              |
| 4    | RE: `plugin.error`                         |
| 5    | 不自动拉起                                 |

手动重启：通过 `aos call skill.stop` + `aos call skill.start`。

### 6.3 停止

| 步骤 | 动作                                  |
| ---- | ------------------------------------- |
| 1    | daemon 发送 `shutdown` 消息           |
| 2    | 等待子进程退出（超时 5 秒后 SIGKILL） |
| 3    | 注销所有 Hook                         |
| 4    | 状态 = `stopped`                      |

### 6.4 Owner 归档联动

Owner 归档 → 停止所有归属该 owner 的 Plugin。

---

## 7. 归档

| 作用域  | 动作                                                   | Hook                   |
| ------- | ------------------------------------------------------ | ---------------------- |
| Session | 释放 lease，停止 Plugin，写 archivedAt                 | RE: `session.archived` |
| Agent   | 停止 Plugin，写 archivedAt                             | RE: `agent.archived`   |
| AOS     | `aos.stopping` 事件，停止 system 级 Plugin，释放注册表 | RE: `aos.stopping`     |

---

## 8. 恢复协议

### 8.1 恢复依据

恢复只依赖三种静态真相：AOSCB、ACB/SCB、SessionHistory。ContentStore 中的 blob 是辅助依据。所有运行时结构可重建。

### 8.2 Lease 恢复

| SCB 状态                         | 恢复动作                                    |
| -------------------------------- | ------------------------------------------- |
| phase=`idle`                     | 直接使用                                    |
| phase=`dispatched`，lease 未过期 | 不主动抢占；等待 lease TTL 到期后按下行处理 |
| phase=`dispatched`，lease 已过期 | 立即清空 lease，phase=`idle`                |
| phase=`compacting`               | 视为 interrupted，phase=`idle`              |

### 8.3 SessionContext 恢复

调用 TH: `context.assemble` (trigger=rebuild)。见 [aos-hooks.md](./aos-hooks.md) §3.5.1。

### 8.4 Bootstrap 恢复

| marker 状态       | 含义     | 恢复动作                        |
| ----------------- | -------- | ------------------------------- |
| 无 begin          | 尚未开始 | 完整 bootstrap                  |
| 有 begin，无 done | 中途崩溃 | 补齐剩余注入，写 done，置 ready |
| 有 done           | 已完成   | 直接置 ready                    |

结构不一致或无法解析时，恢复失败：RE: `session.error { source: "recovery", recoverable: false }`。

### 8.5 Compaction 完整性

已完成条件：marker + summary 同时存在，且 `summary.metadata.finish = completed`。未满足则该 pair 不作为 rebuild 起始点。
