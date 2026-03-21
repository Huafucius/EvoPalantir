# AOS Data Model Spec

_数据结构定义。面向开发者和 AI coding agent。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-aoscp.md](./aos-aoscp.md) · [aos-hooks.md](./aos-hooks.md)_

---

## 1. 约定

**标识符：** 所有 ID 字段（agentId、sessionId、messageId、partId、contentId 等）为不透明字符串，建议 UUID v4。同一命名空间内必须唯一。

**时间格式：** RFC 3339 UTC 字符串，如 `2026-03-19T10:00:00Z`。

**修订号 (revision)：** 每次成功改写 ControlBlock，revision 严格单调递增（+1），从 1 开始。追加 SH 的命令同步更新所属 SCB 的元数据（messageCount 等），因而也产生新 revision。AOSCP 命令返回的 revision 是操作完成后的新值。

**追加写原则：** SH 是 append-only；RL 是 append-only；ContentStore 的 blob 一经写入不可修改。ControlBlock 允许字段覆写，每次覆写伴随 revision 递增与 updatedAt 更新。

**Schema 版本：** 当前版本标识为 `aos/v1`。所有持久化结构的 `schemaVersion` 字段必须填写此值。

---

## 2. 控制块 (Control Blocks)

### 2.1 AOSCB — AOS 控制块

| 字段                | 类型               | 必填 | 可变     | 含义                                                       |
| ------------------- | ------------------ | ---- | -------- | ---------------------------------------------------------- |
| schemaVersion       | string             | 是   | 否       | 固定为 `aos/v1`                                            |
| name                | string             | 是   | 启动刷新 | AOS 实例名称；每次启动从 `AOS_NAME` 环境变量读取           |
| skillRoot           | string             | 是   | 启动刷新 | skill 根目录路径；每次启动从 `AOS_SKILL_ROOT` 环境变量读取 |
| revision            | integer            | 是   | 是       | system 级修订号                                            |
| createdAt           | RFC 3339 UTC       | 是   | 否       | 创建时间                                                   |
| updatedAt           | RFC 3339 UTC       | 是   | 是       | 最近更新时间                                               |
| defaultSkills       | SkillDefaultRule[] | 否   | 是       | system 级默认 skill 条目                                   |
| permissions         | object             | 否   | 预留     | system 级权限策略（语法未固定，v1 不可通过 AOSCP 写入）    |
| autoFoldThreshold   | integer            | 否   | 是       | auto-fold 字符数阈值，默认 16384                           |
| compactionThreshold | integer            | 否   | 是       | 触发 compaction 的 token 数阈值                            |
| maxTurns            | integer            | 否   | 是       | ReActUnit 单次 dispatch 最大循环次数                       |

### 2.2 ACB — Agent 控制块

| 字段              | 类型                  | 必填 | 可变 | 含义                                                   |
| ----------------- | --------------------- | ---- | ---- | ------------------------------------------------------ |
| schemaVersion     | string                | 是   | 否   | 固定为 `aos/v1`                                        |
| agentId           | string                | 是   | 否   | Agent 唯一标识                                         |
| status            | `active` / `archived` | 是   | 是   | 生命周期状态                                           |
| displayName       | string                | 否   | 是   | 展示名                                                 |
| revision          | integer               | 是   | 是   | agent 级修订号                                         |
| createdBy         | `human` / agentId     | 是   | 否   | 创建来源                                               |
| createdAt         | RFC 3339 UTC          | 是   | 否   | 创建时间                                               |
| updatedAt         | RFC 3339 UTC          | 是   | 是   | 最近更新时间                                           |
| archivedAt        | RFC 3339 UTC          | 否   | 是   | 归档时间；仅 `status=archived` 时                      |
| defaultSkills     | SkillDefaultRule[]    | 否   | 是   | agent 级默认 skill 条目                                |
| permissions       | object                | 否   | 预留 | agent 级权限策略（语法未固定，v1 不可通过 AOSCP 写入） |
| autoFoldThreshold | integer               | 否   | 是   | agent 级 auto-fold 阈值覆盖                            |

### 2.3 SCB — Session 控制块

| 字段              | 类型                                  | 必填 | 可变 | 含义                                                     |
| ----------------- | ------------------------------------- | ---- | ---- | -------------------------------------------------------- |
| schemaVersion     | string                                | 是   | 否   | 固定为 `aos/v1`                                          |
| sessionId         | string                                | 是   | 否   | Session 唯一标识                                         |
| agentId           | string                                | 是   | 否   | 所属 Agent                                               |
| status            | `initializing` / `ready` / `archived` | 是   | 是   | 生命周期状态                                             |
| phase             | 见下表                                | 是   | 是   | 运行阶段，与 status 正交                                 |
| leaseId           | string                                | 否   | 是   | 当前 lease 标识；phase=dispatched 时必填                 |
| leaseHolder       | string                                | 否   | 是   | 持有 lease 的节点/进程标识                               |
| leaseExpiresAt    | RFC 3339 UTC                          | 否   | 是   | lease 过期时间；默认 TTL = 30 分钟                       |
| title             | string                                | 否   | 是   | Session 标题                                             |
| revision          | integer                               | 是   | 是   | session 级修订号                                         |
| createdBy         | `human` / agentId                     | 是   | 否   | 创建来源                                                 |
| createdAt         | RFC 3339 UTC                          | 是   | 否   | 创建时间                                                 |
| updatedAt         | RFC 3339 UTC                          | 是   | 是   | 最近更新时间                                             |
| archivedAt        | RFC 3339 UTC                          | 否   | 是   | 归档时间；仅 `status=archived` 时                        |
| defaultSkills     | SkillDefaultRule[]                    | 否   | 是   | session 级默认 skill 条目                                |
| permissions       | object                                | 否   | 预留 | session 级权限策略（语法未固定，v1 不可通过 AOSCP 写入） |
| autoFoldThreshold | integer                               | 否   | 是   | session 级 auto-fold 阈值覆盖                            |
| messageCount      | integer                               | 是   | 是   | SH 中消息总数                                            |
| lastMessageSeq    | integer                               | 否   | 是   | SH 中最新消息的 seq；无消息时为 null                     |

**Phase 枚举：**

| phase           | 含义                                   |
| --------------- | -------------------------------------- |
| `bootstrapping` | 正在执行 bootstrap 流程                |
| `idle`          | 就绪，等待下一次 dispatch              |
| `dispatched`    | lease 活跃，ReActUnit 正在运行         |
| `compacting`    | 正在执行 compaction                    |
| `interrupted`   | 已接收中断指令，等待当前操作完成后终止 |

**autoFoldThreshold 解析：** 按 system → agent → session 顺序，后层覆盖前层。最终生效值 = 三层中最后一个非空声明。注：内核不消费此值做任何决策；由 `aos-context` Skill 的 `tool.after` TH 使用此值判断是否需要 fold。

**Lease 规则：** phase=`dispatched` 时 leaseId / leaseHolder / leaseExpiresAt 必须非空。phase 回到 `idle` 时三个字段必须清空。若当前时间 > leaseExpiresAt 且 phase=`dispatched`，内核必须将 phase 强制置为 `idle` 并清空 lease 字段。

---

## 3. Skill 相关结构

### 3.1 SkillManifest

| 字段        | 类型   | 必填 | 含义                                           |
| ----------- | ------ | ---- | ---------------------------------------------- |
| name        | string | 是   | skill 名；在 AOS 实例内唯一                    |
| description | string | 是   | 给 RU 看的简短说明                             |
| plugin      | string | 否   | frontmatter 顶层 `plugin` 字段；可执行入口路径 |
| skillPath   | Path   | 是   | SKILL.md 文件路径                              |
| skillText   | string | 是   | SKILL.md 正文（去除 frontmatter）              |

### 3.2 SkillCatalogItem

| 字段        | 类型   | 必填 | 含义               |
| ----------- | ------ | ---- | ------------------ |
| name        | string | 是   | skill 名           |
| description | string | 是   | 来自 SkillManifest |

### 3.3 SkillDefaultRule

| 字段  | 类型                 | 必填 | 含义                                     |
| ----- | -------------------- | ---- | ---------------------------------------- |
| name  | string               | 是   | skill 名                                 |
| load  | `enable` / `disable` | 否   | 是否参与默认上下文注入                   |
| start | `enable` / `disable` | 否   | plugin 是否在 owner 生命周期起点默认启动 |

load 与 start 相互独立，字段缺失表示当前层不作声明。同一 CB 内不得出现同名重复条目。

### 3.4 SkillDiscoveryStrategy 接口

```
discover(input) -> SkillCatalogItem[]
```

| 字段      | 类型      | 含义                           |
| --------- | --------- | ------------------------------ |
| skillRoot | string    | skill 根目录或上游来源         |
| ownerType | OwnerType | 当前 discover 的归属层         |
| ownerId   | string    | 当前归属对象；可选             |
| query     | object    | 上下文、标签、过滤条件等；可选 |
| limit     | integer   | 暴露给 RU 的 skill 数量上限    |
| params    | object    | 算法自定义参数                 |

默认策略为文件系统扫描。可替换为云端存储、Git 仓库等。

### 3.5 复合类型别名

| 别名         | 展开                                                                                       | 使用位置                      |
| ------------ | ------------------------------------------------------------------------------------------ | ----------------------------- |
| SkillCatalog | `SkillCatalogItem[]`                                                                       | AOSCP skill.catalog.\* 返回值 |
| MessageInput | `{ role, parts }` — 与 SHMessage 结构相同，由内核填充 id、metadata.seq、metadata.createdAt | AOSCP session.append 参数     |

---

## 4. SessionHistory 消息

SH 以消息为顶层单位，遵循并扩展 AI SDK UIMessage[] 标准。

### 4.1 顶层结构

| 字段     | 类型                            | 含义           |
| -------- | ------------------------------- | -------------- |
| id       | string                          | 消息唯一标识   |
| role     | `system` / `user` / `assistant` | 消息角色       |
| parts    | SessionHistoryPart[]            | 消息内容       |
| metadata | object                          | AOS 附加元数据 |

### 4.2 metadata 字段

| 字段      | 类型                          | 含义                                       |
| --------- | ----------------------------- | ------------------------------------------ |
| seq       | integer                       | session 内严格单调递增，从 1 开始          |
| createdAt | RFC 3339 UTC                  | 消息创建时间                               |
| origin    | `human` / `assistant` / `aos` | 真实来源                                   |
| parentId  | string                        | 可选；compaction summary 指向 marker 的 id |
| summary   | boolean                       | 可选；`true` 表示 compaction 摘要          |
| finish    | string                        | 可选；完成状态                             |
| error     | `{ code, message, details? }` | 可选                                       |

### 4.3 role / origin 对照表

| 消息类型                           | role        | origin      |
| ---------------------------------- | ----------- | ----------- |
| 用户输入                           | `user`      | `human`     |
| 模型输出与 bash 工具活动           | `assistant` | `assistant` |
| AOS 默认注入、skill load、reinject | `user`      | `aos`       |
| AOS compaction marker              | `user`      | `aos`       |
| AOS compaction summary             | `assistant` | `aos`       |
| AOS interrupt、bootstrap marker    | `user`      | `aos`       |

### 4.4 Part 类型

**TextPart**

| 字段 | 类型   | 含义      |
| ---- | ------ | --------- |
| id   | string | part 标识 |
| type | `text` | 类型标记  |
| text | string | 文本内容  |

**ToolBashPart**

| 字段       | 类型                                                                        | 含义                            |
| ---------- | --------------------------------------------------------------------------- | ------------------------------- |
| id         | string                                                                      | part 标识                       |
| type       | `tool-bash`                                                                 | 类型标记                        |
| toolCallId | string                                                                      | 工具调用标识                    |
| state      | `input-streaming` / `input-available` / `output-available` / `output-error` | AI SDK 标准四态                 |
| input      | `{ command, cwd?, timeoutMs? }`                                             | bash 调用参数                   |
| output     | ToolBashOutput                                                              | state=`output-available` 时必填 |
| errorText  | string                                                                      | state=`output-error` 时必填     |

**ToolBashOutput：**

| 字段          | 类型           | 必填     | 含义                                         |
| ------------- | -------------- | -------- | -------------------------------------------- |
| visibleResult | string \| null | 是       | 会话可见结果；使用 contentId 时必须为 `null` |
| contentId     | string         | 否       | 大内容在 ContentStore 中的引用               |
| sizeChars     | integer        | 仅大内容 | 完整内容的字符数                             |
| lineCount     | integer        | 仅大内容 | 完整内容的行数                               |
| preview       | string         | 仅大内容 | 前 10 行预览文本                             |

**大内容判定：** 内核不执行大内容判定。`aos-context` Skill 通过 `tool.after` TH 检查 `len(visible result) > autoFoldThreshold`，满足时通过 AOSCP `content.put` 将内容存入 ContentStore，返回修改后的 output（contentId 引用，visibleResult 置为 null）。如无 Skill 注册 `tool.after`，原始 visible result 直接写入 SH。

**SkillLoadPart**

| 字段           | 类型                                | 含义                  |
| -------------- | ----------------------------------- | --------------------- |
| id             | string                              | part 标识             |
| type           | `data-skill-load`                   | 类型标记              |
| data.cause     | `default` / `explicit` / `reinject` | 注入来源              |
| data.ownerType | OwnerType                           | 来源 owner 类型       |
| data.ownerId   | string                              | owner 标识；可选      |
| data.name      | string                              | skill 名              |
| data.skillText | string                              | 注入的 skillText 全文 |

**CompactionMarkerPart**

| 字段          | 类型              | 含义                 |
| ------------- | ----------------- | -------------------- |
| id            | string            | part 标识            |
| type          | `data-compaction` | 类型标记             |
| data.auto     | boolean           | 自动触发             |
| data.overflow | boolean           | 可选；上下文溢出触发 |
| data.fromSeq  | integer           | 覆盖起始 seq（含）   |
| data.toSeq    | integer           | 覆盖终止 seq（含）   |

**InterruptPart**

| 字段         | 类型             | 含义           |
| ------------ | ---------------- | -------------- |
| id           | string           | part 标识      |
| type         | `data-interrupt` | 类型标记       |
| data.reason  | string           | 中断原因       |
| data.payload | object           | 附加信息；可选 |

**BootstrapPart**

| 字段              | 类型             | 含义                          |
| ----------------- | ---------------- | ----------------------------- |
| id                | string           | part 标识                     |
| type              | `data-bootstrap` | 类型标记                      |
| data.phase        | `begin` / `done` | 阶段标记                      |
| data.reason       | string           | 可选                          |
| data.plannedNames | string[]         | 可选；计划注入的 skill 名列表 |

### 4.5 Compaction Pair 语义

CompactionMarkerMessage（role=`user`, origin=`aos`）与 CompactionSummaryMessage（role=`assistant`, origin=`aos`, summary=`true`, finish=`completed`）配对。二者同时存在且 finish=`completed` 才算已完成，可作为 rebuild 起始边界。

---

## 5. 运行时日志 (RuntimeLog)

### 5.1 RuntimeLogEntry

| 字段      | 类型                      | 必填 | 含义                                                                    |
| --------- | ------------------------- | ---- | ----------------------------------------------------------------------- |
| id        | string                    | 是   | 日志条目唯一标识                                                        |
| time      | RFC 3339 UTC              | 是   | 事件发生时间                                                            |
| level     | `info` / `warn` / `error` | 是   | 日志级别                                                                |
| op        | string                    | 是   | 操作名；点分形式                                                        |
| ownerType | OwnerType                 | 是   | 操作归属                                                                |
| ownerId   | string                    | 否   | owner 标识                                                              |
| agentId   | string                    | 否   | 所属 Agent                                                              |
| sessionId | string                    | 否   | 所属 Session                                                            |
| refs      | object                    | 否   | 关联引用（historyMessageId、historyPartId、contextRevision、contentId） |
| data      | object                    | 否   | 操作相关数据                                                            |

**RL 写入规则：** 仅 AOSCP 命令路径产生 RL 条目。查询不产生 RL 条目。

---

## 6. 运行时对象

### 6.1 PluginInstance

| 字段               | 类型                                                      | 含义                                 |
| ------------------ | --------------------------------------------------------- | ------------------------------------ |
| instanceId         | string                                                    | ownerType + ownerId + skillName 组合 |
| skillName          | string                                                    | 所属 skill 名                        |
| ownerType          | OwnerType                                                 | owner 类型                           |
| ownerId            | string                                                    | owner 标识                           |
| state              | `starting` / `running` / `stopping` / `stopped` / `error` | 实例状态                             |
| startedAt          | RFC 3339 UTC                                              | 启动时间                             |
| hooks              | string[]                                                  | 已注册的 Hook 名列表（所有类型）     |
| eventSubscriptions | string[]                                                  | 已订阅的 Runtime Event 名列表        |
| lastError          | string                                                    | 最近错误；可选                       |

### 6.2 SessionContext

| 字段            | 类型              | 含义                                    |
| --------------- | ----------------- | --------------------------------------- |
| sessionId       | string            | 所属 Session                            |
| contextRevision | integer           | 单调递增；每次 rebuild 或增量更新后递增 |
| messages        | ContextMessage[]  | 下一次调用 RU 时传入的完整消息列表      |
| foldedRefs      | Set\<HistoryRef\> | 当前被折叠的历史引用集合                |

### 6.3 ContextMessage

```json
{
  "wire": { "role": "user", "content": "..." },
  "aos": {
    "sourceMessageId": "<SH message id>",
    "sourcePartId": "<part id>",
    "kind": "<投影类型>"
  }
}
```

RU 消费 `wire` 部分，发给 LLM 之前剥离 `aos`。

**kind 枚举：**

| kind                 | 含义                              |
| -------------------- | --------------------------------- |
| `user-input`         | 用户输入                          |
| `assistant-output`   | 模型文本输出                      |
| `tool-bash-call`     | bash 工具调用请求                 |
| `tool-bash-result`   | bash 工具调用结果（完整）         |
| `tool-bash-folded`   | bash 工具调用结果（折叠，占位符） |
| `message-folded`     | 整条消息折叠（占位符）            |
| `skill-load`         | skill 注入                        |
| `compaction-summary` | compaction 摘要                   |
| `compaction-marker`  | compaction 标记                   |
| `interrupt`          | 中断事实                          |

### 6.4 HistoryRef

两种形式：

- `{ historyMessageId }` — 折叠整条消息
- `{ historyMessageId, historyPartId }` — 折叠单个 part

foldedRefs 是纯运行时状态，不持久化。auto-fold 的 ref 在 rebuild 时重新生成。

### 6.5 RuntimeEvent

| 字段      | 类型         | 含义                                    |
| --------- | ------------ | --------------------------------------- |
| name      | string       | 事件名称（如 `session.dispatch.after`） |
| ownerType | OwnerType    | 事件归属                                |
| timestamp | RFC 3339 UTC | 事件时间                                |
| agentId   | string       | 所属 Agent；可选                        |
| sessionId | string       | 所属 Session；可选                      |
| payload   | object       | 事件数据                                |

---

## 7. 类型枚举汇总

| 类型             | 值                                                                          |
| ---------------- | --------------------------------------------------------------------------- |
| OwnerType        | `system` / `agent` / `session`                                              |
| Status (Agent)   | `active` / `archived`                                                       |
| Status (Session) | `initializing` / `ready` / `archived`                                       |
| Phase (Session)  | `bootstrapping` / `idle` / `dispatched` / `compacting` / `interrupted`      |
| PluginState      | `starting` / `running` / `stopping` / `stopped` / `error`                   |
| ToolBashState    | `input-streaming` / `input-available` / `output-available` / `output-error` |
| Origin           | `human` / `assistant` / `aos`                                               |
| SkillLoadCause   | `default` / `explicit` / `reinject`                                         |
| BootstrapPhase   | `begin` / `done`                                                            |
