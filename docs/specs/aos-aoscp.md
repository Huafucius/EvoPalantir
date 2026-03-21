# AOSCP (AOS Control Protocol) Spec

_内核函数表。每个 AOSCP 操作的签名、参数、返回值、语义。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-data-model.md](./aos-data-model.md) · [aos-hooks.md](./aos-hooks.md) · [aos-transport.md](./aos-transport.md)_

---

## 1. 总则

### 1.1 命令与查询分离 (CQRS)

**命令** 改变系统状态，可经过 Admission Hook 拦截，产生 RuntimeLog 条目。修改 ControlBlock 的命令返回新 revision（见 §1.2 响应格式）。

**查询** 读取系统状态，不经过 Admission Hook，不产生 RuntimeLog 条目，轻量可缓存。

### 1.2 响应格式

所有 AOSCP 操作返回统一 AosResponse 结构：

| 字段          | 类型    | 必填 | 含义                   |
| ------------- | ------- | ---- | ---------------------- |
| ok            | boolean | 是   | 操作是否成功           |
| op            | string  | 是   | 操作名                 |
| revision      | integer | 否   | 新修订号（命令成功时） |
| data          | object  | 否   | 成功结果               |
| error.code    | string  | 否   | 错误码                 |
| error.message | string  | 否   | 错误信息               |
| error.details | object  | 否   | 额外上下文             |

控制面响应 JSON-only。

### 1.3 常用错误码

| code                         | 含义                      |
| ---------------------------- | ------------------------- |
| `session.busy`               | Session phase=dispatched  |
| `session.not_ready`          | Session status 不是 ready |
| `session.archived`           | Session 已归档            |
| `agent.archived`             | Agent 已归档              |
| `skill.not_found`            | skill 不存在              |
| `permission.denied`          | 权限不足                  |
| `revision.conflict`          | 修订号冲突                |
| `lease.expired`              | dispatch lease 已过期     |
| `content.not_found`          | contentId 不存在          |
| `context.engine_unavailable` | 上下文引擎不可用          |

### 1.4 环境变量

daemon 启动子进程时注入环境变量。注入范围因进程类型和 Plugin ownerType 而异：

| 变量             | ReActUnit | system Plugin | agent Plugin | session Plugin |
| ---------------- | --------- | ------------- | ------------ | -------------- |
| `AOS_API_URL`    | ✓         | ✓             | ✓            | ✓              |
| `AOS_API_TOKEN`  | ✓         | ✓             | ✓            | ✓              |
| `AOS_AGENT_ID`   | ✓         | —             | ✓            | ✓              |
| `AOS_SESSION_ID` | ✓         | —             | —            | ✓              |

ReActUnit 始终在 session 上下文中运行，四个变量全部注入。Plugin 按 ownerType 决定可见范围，详见 [aos-plugin.md](./aos-plugin.md) §3.2。

---

## 2. System 操作域

### 2.1 system.get (查询)

返回：`AOSCB`

### 2.2 system.update (命令)

| 参数                | 类型               | 必填 | 含义                   |
| ------------------- | ------------------ | ---- | ---------------------- |
| defaultSkills       | SkillDefaultRule[] | 否   | system 级默认 skill    |
| autoFoldThreshold   | integer            | 否   | auto-fold 阈值         |
| compactionThreshold | integer            | 否   | compaction token 阈值  |
| maxTurns            | integer            | 否   | ReActUnit 最大循环次数 |

返回：`{ revision }`

---

## 3. Skill 操作域

### 3.1 skill.index.refresh (命令)

重新扫描 skillRoot，更新 SkillManifest 索引。

| 参数 | 类型 | 必填 | 含义   |
| ---- | ---- | ---- | ------ |
| —    |      |      | 无参数 |

返回：`{ indexedCount: integer }`

Hook：AH `skill.index.refresh.before` → RE `skill.index.refresh.after`

### 3.2 skill.catalog.refresh (命令)

刷新 discovery cache，产生 SkillCatalog。

| 参数      | 类型      | 必填 | 含义          |
| --------- | --------- | ---- | ------------- |
| ownerType | OwnerType | 是   | discover 归属 |
| ownerId   | string    | 否   | owner 标识    |
| query     | object    | 否   | 过滤条件      |

返回：`SkillCatalog`

Hook：AH `skill.discovery.before` → TH `skill.discovery.resolve` → RE `skill.discovery.after`

### 3.3 skill.catalog.preview (查询)

预览当前 SkillCatalog（不刷新 cache）。

| 参数      | 类型      | 必填 | 含义       |
| --------- | --------- | ---- | ---------- |
| ownerType | OwnerType | 否   | 过滤归属   |
| ownerId   | string    | 否   | owner 标识 |
| query     | object    | 否   | 过滤条件   |
| limit     | integer   | 否   | 数量上限   |

返回：`SkillCatalog`

### 3.4 skill.catalog.list (查询)

列出已索引的全部 skill。

返回：`SkillCatalog`

### 3.5 skill.default.resolve (查询)

解析三层 SkillDefaultRule 合并后的最终默认 skill 集合。作为查询，本身不触发 Admission Hook，不产生 RuntimeLog。同名生命周期 hook（`skill.default.resolve.before/after`）仅在 bootstrap / reinject 命令路径中触发，与此查询无关。

| 参数      | 类型      | 必填 | 含义       |
| --------- | --------- | ---- | ---------- |
| ownerType | OwnerType | 是   | 解析归属   |
| ownerId   | string    | 否   | owner 标识 |

返回：`{ resolvedNames: string[] }`

### 3.6 skill.load (命令)

将 skillText 写入 SH 并投影到 SC。

| 参数      | 类型   | 必填 | 含义                     |
| --------- | ------ | ---- | ------------------------ |
| name      | string | 是   | skill 名                 |
| sessionId | string | 否   | 目标 session（默认当前） |

返回：`{ name, skillText }`

Hook：AH `skill.load.before` → RE `skill.load.after`

### 3.7 skill.unload (命令)

从 SC 中移除指定 skill 的 skillText。

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| name      | string | 是   | skill 名     |
| sessionId | string | 否   | 目标 session |

返回：`{ name }`

### 3.8 skill.start (命令)

启动 skill 的插件面，spawn Plugin 子进程。

| 参数      | 类型      | 必填 | 含义       |
| --------- | --------- | ---- | ---------- |
| skillName | string    | 是   | skill 名   |
| ownerType | OwnerType | 是   | owner 类型 |
| ownerId   | string    | 否   | owner 标识 |

返回：`PluginInstance`

Hook：AH `skill.start.before` → RE `skill.start.after`

### 3.9 skill.stop (命令)

停止 Plugin 子进程。

| 参数       | 类型   | 必填 | 含义            |
| ---------- | ------ | ---- | --------------- |
| instanceId | string | 是   | plugin 实例标识 |

返回：`{ instanceId }`

Hook：AH `skill.stop.before` → RE `skill.stop.after`

### 3.10 skill.list (查询)

列出全部已索引 skill 的 SkillManifest。

返回：`SkillManifest[]`

---

## 4. Agent 操作域

### 4.1 agent.create (命令)

| 参数        | 类型   | 必填 | 含义   |
| ----------- | ------ | ---- | ------ |
| displayName | string | 否   | 展示名 |

返回：`ACB`

Hook：RE `agent.started`

### 4.2 agent.update (命令)

| 参数              | 类型               | 必填 | 含义                    |
| ----------------- | ------------------ | ---- | ----------------------- |
| agentId           | string             | 是   | Agent ID                |
| displayName       | string             | 否   | 新展示名                |
| defaultSkills     | SkillDefaultRule[] | 否   | 新默认 skill            |
| autoFoldThreshold | integer            | 否   | agent 级 auto-fold 阈值 |

返回：`{ revision }`

### 4.3 agent.archive (命令)

| 参数    | 类型   | 必填 | 含义     |
| ------- | ------ | ---- | -------- |
| agentId | string | 是   | Agent ID |

返回：`{ revision }`

副作用：停止 agent 下所有 Plugin。

Hook：RE `agent.archived`

### 4.4 agent.get (查询)

| 参数    | 类型   | 必填 | 含义     |
| ------- | ------ | ---- | -------- |
| agentId | string | 是   | Agent ID |

返回：`ACB`

### 4.5 agent.list (查询)

返回：`ACB[]`

---

## 5. Session 操作域

### 5.1 session.create (命令)

| 参数    | 类型   | 必填 | 含义       |
| ------- | ------ | ---- | ---------- |
| agentId | string | 是   | 所属 Agent |
| title   | string | 否   | 标题       |

返回：`SCB`

副作用：进入 bootstrap 流程。

### 5.2 session.dispatch (命令)

触发 ReAct 循环的唯一正式入口。内核语义是异步的——创建 dispatch 后立即返回，ReActUnit 独立推进。

| 参数      | 类型                                | 必填 | 含义         |
| --------- | ----------------------------------- | ---- | ------------ |
| sessionId | string                              | 是   | 目标 Session |
| message   | `{ role: "user", content: string }` | 是   | 用户消息     |

前置检查：status=`ready` 且 phase=`idle`，否则返回 `session.busy` 或 `session.not_ready`。

返回：`{ sessionId, dispatchId }`

客户端如何消费 dispatch 结果是传输层关注点，不属于 AOSCP 语义：

| 模式            | 传输层行为                                                                                  | 典型使用者 |
| --------------- | ------------------------------------------------------------------------------------------- | ---------- |
| fire-and-forget | 拿到 dispatchId 即完成                                                                      | 自动化管道 |
| streaming       | 连接 `GET /aoscp/dispatch/{dispatchId}/stream`，通过 SSE 实时接收中间结果和最终 `done` 事件 | 前端 UI    |
| blocking        | 连接 SSE 并等待 `done` 事件；SDK 封装为同步调用                                             | CLI 默认   |

完成信息（finalMessageSeq、usage）通过 SSE `done` 事件获取，见 [aos-transport.md](./aos-transport.md) §2.3。

Hook：AH `session.dispatch.before` → RE `session.dispatch.after`

### 5.3 session.append (命令)

追加 SH 消息，不触发执行。

| 参数      | 类型         | 必填 | 含义         |
| --------- | ------------ | ---- | ------------ |
| sessionId | string       | 是   | 目标 Session |
| message   | MessageInput | 是   | 消息         |

返回：`{ revision }`

### 5.4 session.interrupt (命令)

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| sessionId | string | 是   | 目标 Session |
| reason    | string | 是   | 中断原因     |
| payload   | object | 否   | 附加信息     |

返回：`{ revision }`

Hook：RE `session.interrupted`

### 5.5 session.compact (命令)

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| sessionId | string | 是   | 目标 Session |

返回：`{ revision }`

副作用：compaction + reinject + rebuild。

Hook：AH `session.compaction.before` → TH `context.compact` → RE `session.compaction.after`

### 5.6 session.update (命令)

| 参数              | 类型               | 必填 | 含义                      |
| ----------------- | ------------------ | ---- | ------------------------- |
| sessionId         | string             | 是   | Session ID                |
| title             | string             | 否   | 新标题                    |
| defaultSkills     | SkillDefaultRule[] | 否   | session 级默认 skill      |
| autoFoldThreshold | integer            | 否   | session 级 auto-fold 阈值 |

返回：`{ revision }`

### 5.7 session.archive (命令)

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| sessionId | string | 是   | 目标 Session |

返回：`{ revision }`

副作用：释放 lease，停止 Plugin。

Hook：RE `session.archived`

### 5.8 session.get (查询)

| 参数      | 类型   | 必填 | 含义       |
| --------- | ------ | ---- | ---------- |
| sessionId | string | 是   | Session ID |

返回：`SCB`

### 5.9 session.list (查询)

| 参数    | 类型    | 必填 | 含义       |
| ------- | ------- | ---- | ---------- |
| agentId | string  | 否   | 过滤 Agent |
| cursor  | string  | 否   | 分页游标   |
| limit   | integer | 否   | 分页大小   |

返回：`{ items: SCB[], nextCursor? }`

---

## 6. Session Context 操作域

### 6.1 session.context.fold (命令)

将 ref 加入 foldedRefs，SC 中替换为 fold 占位符。内核调用 TH `context.assemble` (trigger=fold)。

| 参数      | 类型       | 必填 | 含义         |
| --------- | ---------- | ---- | ------------ |
| sessionId | string     | 是   | 目标 Session |
| ref       | HistoryRef | 是   | 要折叠的引用 |

返回：`{ contextRevision }`

不写 SH，只写 RL。

### 6.2 session.context.unfold (命令)

从 foldedRefs 移除 ref，恢复完整投影。内核调用 TH `context.assemble` (trigger=unfold)。

| 参数      | 类型       | 必填 | 含义         |
| --------- | ---------- | ---- | ------------ |
| sessionId | string     | 是   | 目标 Session |
| ref       | HistoryRef | 是   | 要展开的引用 |

返回：`{ contextRevision }`

不写 SH，只写 RL。

### 6.3 session.context.compact (命令)

触发 compaction。等同于 `session.compact`。

### 6.4 session.context.get (查询)

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| sessionId | string | 是   | 目标 Session |

返回：`{ sessionId, contextRevision, messageCount, foldedRefCount }`

### 6.5 session.context.rebuild (查询)

从 SH 重新构建 SC（运行时缓存）。内核调用 TH `context.assemble` (trigger=rebuild)。SC 不属于持久化状态——它从 SH 物化而来，关机即消失——因此重建不构成 CQRS 意义上的状态变更，不写 SH，不写 RL。

返回：`{ contextRevision }`

---

## 7. Session History 操作域

### 7.1 session.history.list (查询)

| 参数      | 类型    | 必填 | 含义           |
| --------- | ------- | ---- | -------------- |
| sessionId | string  | 是   | 目标 Session   |
| fromSeq   | integer | 否   | 起始序号（含） |
| toSeq     | integer | 否   | 结束序号（含） |
| cursor    | string  | 否   | 分页游标       |
| limit     | integer | 否   | 分页大小       |

`fromSeq`/`toSeq` 与 `cursor` 互斥。指定 seq 范围时按 seq 升序返回。

返回：`{ items: SHMessage[], nextCursor? }`

### 7.2 session.history.get (查询)

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| sessionId | string | 是   | 目标 Session |
| messageId | string | 是   | 消息 ID      |

返回：`SHMessage`

---

## 8. Plugin 操作域

### 8.1 plugin.list (查询)

| 参数      | 类型      | 必填 | 含义            |
| --------- | --------- | ---- | --------------- |
| ownerType | OwnerType | 否   | 过滤 owner 类型 |
| ownerId   | string    | 否   | 过滤 owner      |

返回：`PluginInstance[]`

### 8.2 plugin.get (查询)

| 参数       | 类型   | 必填 | 含义            |
| ---------- | ------ | ---- | --------------- |
| instanceId | string | 是   | plugin 实例标识 |

返回：`PluginInstance`

---

## 9. Content 操作域

### 9.1 content.read (查询)

按 contentId 读取大内容。

| 参数      | 类型    | 必填 | 含义                  |
| --------- | ------- | ---- | --------------------- |
| contentId | string  | 是   | 内容标识              |
| offset    | integer | 否   | 起始行号（从 0 开始） |
| limit     | integer | 否   | 读取行数              |

返回：`{ contentId, content, totalLines, totalChars }`

### 9.2 content.search (查询)

在大内容中搜索 pattern。

| 参数      | 类型    | 必填 | 含义       |
| --------- | ------- | ---- | ---------- |
| contentId | string  | 是   | 内容标识   |
| pattern   | string  | 是   | 搜索正则   |
| limit     | integer | 否   | 最大匹配数 |

返回：`{ contentId, matches: [{ lineNumber, text }] }`

### 9.3 content.put (命令)

将大内容存入 ContentStore。通常由 `aos-context` Skill 的 `tool.after` TH 在检测到大内容时调用。

| 参数      | 类型   | 必填 | 含义         |
| --------- | ------ | ---- | ------------ |
| content   | string | 是   | 待存储的内容 |
| sessionId | string | 是   | 所属 Session |

返回：`{ contentId, sizeChars, lineCount }`

---

## 10. 操作总表

| 操作域          | 命令   | 查询   | 合计   |
| --------------- | ------ | ------ | ------ |
| System          | 1      | 1      | 2      |
| Skill           | 6      | 4      | 10     |
| Agent           | 3      | 2      | 5      |
| Session         | 7      | 2      | 9      |
| Session Context | 3      | 2      | 5      |
| Session History | 0      | 2      | 2      |
| Plugin          | 0      | 2      | 2      |
| Content         | 1      | 2      | 3      |
| **合计**        | **21** | **17** | **38** |

---

## 11. 写入顺序规则

**规则一：** 影响 SH 的命令，先写 SH，再更新 SC。

**规则二：** 只影响 SC 的命令（fold / unfold），只改内存并写 RL，不写 SH。

**规则三：** 所有 AOSCP 命令，完成时写 RL。

**规则四：** 大内容场景（由 `aos-context` Skill 的 `tool.after` TH 触发），Skill 先通过 `content.put` 写 ContentStore，再在 TH output 中返回 contentId 引用，内核随后写 SH（引用），再更新 SC（占位符）。不得反向。

---

## 12. 会话可见事实边界

| 事实                       | 进入 SH                           |
| -------------------------- | --------------------------------- |
| 用户输入                   | 是                                |
| 模型输出                   | 是                                |
| bash 调用与 visible result | 是（visibleResult 或 contentId）  |
| 显式 skill load            | 是（tool-bash + data-skill-load） |
| 默认 skill 注入            | 是                                |
| compaction pair            | 是                                |
| reinject                   | 是                                |
| interrupt                  | 是                                |
| bootstrap marker           | 是                                |
| fold / unfold 操作         | 否（只进 RL）                     |
| Plugin 私有日志            | 否（进入 RL）                     |
| bash raw result            | 否（进入 RL）                     |
| AOSCP 查询操作             | 否（不进 RL，不进 SH）            |
