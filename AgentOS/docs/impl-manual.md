# Agent OS 实现手册 v0.9

_本手册是规范性文档，配套 charter v0.9 与 ADR `docs/decisions/0001-v09-arch-redesign.md` 使用。_

---

## 第一章 规范约定

### 1.1 文档地位与术语

凡使用「必须（MUST）」「不得（MUST NOT）」「应当（SHOULD）」「可以（MAY）」等措辞，均按 RFC 2119 语义理解。

| 术语            | 含义                                                      |
| --------------- | --------------------------------------------------------- |
| AOSCP           | AOS Control Plane，内核态/用户态唯一边界                  |
| CB              | ControlBlock，泛指 AOSCB / ACB / SCB                      |
| SH              | SessionHistory                                            |
| SC              | SessionContext                                            |
| RL              | RuntimeLog                                                |
| RU              | ReActUnit                                                 |
| AH              | Admission Hook（同步准入拦截器）                          |
| TH              | Transform Hook（同步数据改写器）                          |
| RE              | Runtime Event（异步只读通知）                             |
| HistoryRef      | 指向 SH 中某条消息或某个 part 的运行时引用                |
| ContextMessage  | SC 的内部消息单位，由 `wire` + `aos` 两部分构成           |
| pluginInstance  | plugin 启动后的运行实体                                   |
| ownerType       | `system` / `agent` / `session` 三者之一                   |
| compaction pair | CompactionMarkerMessage + CompactionSummaryMessage 的配对 |
| contentId       | 大内容在 ContentStore 中的不透明引用标识                  |
| foldedRefs      | SC 中当前被折叠的 HistoryRef 集合                         |

### 1.2 通用约定

**标识符：** 所有 ID 字段（agentId、sessionId、messageId、partId、contentId 等）为不透明字符串，建议使用 UUID v4。在同一命名空间内必须唯一。

**时间格式：** 所有时间字段使用 RFC 3339 UTC 字符串，如 `2026-03-19T10:00:00Z`。

**修订号（revision）：** 每次成功改写 ControlBlock，revision 必须严格单调递增（+1），从 1 开始。AOSCP 命令返回的 revision 是本次操作完成后的新值。

**追加写原则：** SH 是 append-only；RL 是 append-only；ContentStore 的 blob 一经写入不可修改（不可变）。ControlBlock 允许字段覆写，每次覆写伴随 revision 递增与 updatedAt 更新。

**错误响应：** 所有 AOSCP 操作遵循统一 AosResponse 结构（见第五章 5.10）。错误情形下 `ok` 为 false，`error.code` 与 `error.message` 必须填写。

**Schema 版本：** 当前版本标识为 `aos/v0.9`。所有持久化结构的 `schemaVersion` 字段必须填写此值。

---

## 第二章 持久化结构

### 2.1 AOSCB

| 字段              | 类型               | 必填 | 可变 | 含义                                  |
| ----------------- | ------------------ | ---- | ---- | ------------------------------------- |
| schemaVersion     | string             | 是   | 否   | 固定为 `aos/v0.9`                     |
| name              | string             | 是   | 是   | AOS 实例名称                          |
| skillRoot         | string             | 是   | 是   | skill 根目录绝对路径                  |
| revision          | integer            | 是   | 是   | system 级修订号                       |
| createdAt         | RFC 3339 UTC       | 是   | 否   | 创建时间                              |
| updatedAt         | RFC 3339 UTC       | 是   | 是   | 最近更新时间                          |
| defaultSkills     | SkillDefaultRule[] | 否   | 是   | system 级默认 skill 条目              |
| permissions       | object             | 否   | 是   | system 级权限策略（语法 v0.9 未固定） |
| autoFoldThreshold | integer            | 否   | 是   | auto-fold 字符数阈值，默认 16384      |

### 2.2 ACB

| 字段              | 类型                  | 必填 | 可变 | 含义                                  |
| ----------------- | --------------------- | ---- | ---- | ------------------------------------- |
| schemaVersion     | string                | 是   | 否   | 固定为 `aos/v0.9`                     |
| agentId           | string                | 是   | 否   | Agent 唯一标识                        |
| status            | `active` / `archived` | 是   | 是   | 生命周期状态                          |
| displayName       | string                | 否   | 是   | 展示名                                |
| revision          | integer               | 是   | 是   | agent 级修订号                        |
| createdBy         | `human` / agentId     | 是   | 否   | 创建来源                              |
| createdAt         | RFC 3339 UTC          | 是   | 否   | 创建时间                              |
| updatedAt         | RFC 3339 UTC          | 是   | 是   | 最近更新时间                          |
| archivedAt        | RFC 3339 UTC          | 否   | 是   | 归档时间；仅 `status=archived` 时出现 |
| defaultSkills     | SkillDefaultRule[]    | 否   | 是   | agent 级默认 skill 条目               |
| permissions       | object                | 否   | 是   | agent 级权限策略                      |
| autoFoldThreshold | integer               | 否   | 是   | agent 级 auto-fold 阈值覆盖           |

### 2.3 SCB

| 字段              | 类型                                  | 必填 | 可变 | 含义                                     |
| ----------------- | ------------------------------------- | ---- | ---- | ---------------------------------------- |
| schemaVersion     | string                                | 是   | 否   | 固定为 `aos/v0.9`                        |
| sessionId         | string                                | 是   | 否   | Session 唯一标识                         |
| agentId           | string                                | 是   | 否   | 所属 Agent                               |
| status            | `initializing` / `ready` / `archived` | 是   | 是   | 生命周期状态                             |
| phase             | 见下表                                | 是   | 是   | 运行阶段，与 status 正交                 |
| leaseId           | string                                | 否   | 是   | 当前 lease 标识；phase=dispatched 时必填 |
| leaseHolder       | string                                | 否   | 是   | 持有 lease 的节点/进程标识               |
| leaseExpiresAt    | RFC 3339 UTC                          | 否   | 是   | lease 过期时间；默认 TTL = 30 分钟       |
| title             | string                                | 否   | 是   | Session 标题                             |
| revision          | integer                               | 是   | 是   | session 级修订号                         |
| createdBy         | `human` / agentId                     | 是   | 否   | 创建来源                                 |
| createdAt         | RFC 3339 UTC                          | 是   | 否   | 创建时间                                 |
| updatedAt         | RFC 3339 UTC                          | 是   | 是   | 最近更新时间                             |
| archivedAt        | RFC 3339 UTC                          | 否   | 是   | 归档时间；仅 `status=archived` 时出现    |
| defaultSkills     | SkillDefaultRule[]                    | 否   | 是   | session 级默认 skill 条目                |
| permissions       | object                                | 否   | 是   | session 级权限策略                       |
| autoFoldThreshold | integer                               | 否   | 是   | session 级 auto-fold 阈值覆盖            |

**phase 枚举：**

| phase           | 含义                                    |
| --------------- | --------------------------------------- |
| `bootstrapping` | Session 正在执行 bootstrap 流程         |
| `idle`          | Session 就绪，等待下一次 dispatch       |
| `dispatched`    | dispatch lease 活跃，ReActUnit 正在运行 |
| `compacting`    | 正在执行 compaction                     |
| `interrupted`   | 已接收中断指令，等待当前操作完成后终止  |

**autoFoldThreshold 解析：** 按 system → agent → session 顺序，后层覆盖前层。最终生效值 = 三层中最后一个非空声明。

**Lease 规则：** phase=`dispatched` 时 leaseId / leaseHolder / leaseExpiresAt 必须非空。phase 回到 `idle` 时三个字段必须清空。若当前时间 > leaseExpiresAt 且 phase=`dispatched`，内核必须将 phase 强制置为 `idle` 并清空 lease 字段。

### 2.4 SkillManifest

| 字段         | 类型     | 必填 | 含义                                         |
| ------------ | -------- | ---- | -------------------------------------------- |
| name         | string   | 是   | skill 名；在 AOS 实例内唯一                  |
| description  | string   | 是   | 给 RU 看的简短说明                           |
| plugin       | string   | 否   | `metadata.aos-plugin` 解析而来；运行入口路径 |
| capabilities | string[] | 否   | `metadata.aos-capabilities` 解析而来         |

### 2.5 CapabilityManifest

CapabilityManifest 是 Skill 的权限声明结构，从 SkillManifest.capabilities 数组物化而来。

**标准 capability 标识符：**

| 标识符            | 含义                                |
| ----------------- | ----------------------------------- |
| `session.read`    | 查询 session 及其历史/上下文        |
| `session.write`   | 追加 SH 消息、执行 dispatch         |
| `tool.execute`    | 触发 bash 执行（via 内核）          |
| `resource.manage` | 创建/停止 ManagedResource           |
| `agent.read`      | 查询 Agent 信息                     |
| `filesystem.read` | 通过 AOSCP 读取文件系统资源         |
| `network.egress`  | 建立出站网络连接（ManagedResource） |

v0.9 中没有 CapabilityManifest 的 skill 获得默认全量权限，触发 `CAPABILITY_MANIFEST_MISSING` warning。强制校验为推迟事项。

### 2.6 SkillCatalogItem

| 字段        | 类型   | 必填 | 含义               |
| ----------- | ------ | ---- | ------------------ |
| name        | string | 是   | skill 名           |
| description | string | 是   | 来自 SkillManifest |

plugin 与 capabilities 字段不进入 SkillCatalogItem。

### 2.7 SkillDefaultRule

| 字段  | 类型                 | 必填 | 含义                                     |
| ----- | -------------------- | ---- | ---------------------------------------- |
| name  | string               | 是   | skill 名                                 |
| load  | `enable` / `disable` | 否   | 是否参与默认上下文注入                   |
| start | `enable` / `disable` | 否   | plugin 是否在 owner 生命周期起点默认启动 |

load 与 start 相互独立，字段缺失表示当前层不作声明。同一 CB 内不得出现同名重复条目。

### 2.8 SkillDiscoveryStrategy 接口

```text
discover(input) -> SkillCatalogItem[]
```

| 字段      | 类型      | 含义                           |
| --------- | --------- | ------------------------------ |
| skillRoot | string    | skill 根目录或上游来源         |
| ownerType | ownerType | 当前 discover 的归属层         |
| ownerId   | string    | 当前归属对象；可选             |
| query     | object    | 上下文、标签、过滤条件等；可选 |
| limit     | integer   | 暴露给 RU 的 skill 数量上限    |
| params    | object    | 算法自定义参数                 |

v0.9 默认策略为文件系统扫描。

### 2.9 SessionHistoryMessage

SH 以消息为顶层单位，遵循并扩展 AI SDK UIMessage[] 标准。

#### 顶层结构

| 字段     | 类型                            | 含义           |
| -------- | ------------------------------- | -------------- |
| id       | string                          | 消息唯一标识   |
| role     | `system` / `user` / `assistant` | 消息角色       |
| parts    | SessionHistoryPart[]            | 消息内容       |
| metadata | object                          | AOS 附加元数据 |

#### metadata 字段

| 字段      | 类型                          | 含义                                       |
| --------- | ----------------------------- | ------------------------------------------ |
| seq       | integer                       | session 内严格单调递增，从 1 开始          |
| createdAt | RFC 3339 UTC                  | 消息创建时间                               |
| origin    | `human` / `assistant` / `aos` | 真实来源                                   |
| parentId  | string                        | 可选；compaction summary 指向 marker 的 id |
| summary   | boolean                       | 可选；`true` 表示 compaction 摘要          |
| finish    | string                        | 可选；完成状态                             |
| error     | `{ code, message, details? }` | 可选                                       |

#### role / origin 对照表

| 消息类型                           | role        | origin      |
| ---------------------------------- | ----------- | ----------- |
| 用户输入                           | `user`      | `human`     |
| 模型输出与 bash 工具活动           | `assistant` | `assistant` |
| AOS 默认注入、skill load、reinject | `user`      | `aos`       |
| AOS compaction marker              | `user`      | `aos`       |
| AOS compaction summary             | `assistant` | `aos`       |
| AOS interrupt、bootstrap marker    | `user`      | `aos`       |

#### Part 类型

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

**ToolBashOutput 结构：**

| 字段          | 类型           | 必填     | 含义                                                      |
| ------------- | -------------- | -------- | --------------------------------------------------------- |
| visibleResult | string \| null | 是       | 会话可见结果；使用 contentId 时必须为 `null`              |
| contentId     | string         | 否       | 大内容在 ContentStore 中的引用；存在时 visibleResult=null |
| sizeChars     | integer        | 仅大内容 | 完整内容的字符数                                          |
| lineCount     | integer        | 仅大内容 | 完整内容的行数                                            |
| preview       | string         | 仅大内容 | 前 10 行预览文本                                          |

**大内容判定：** `len(visible result) > autoFoldThreshold`（三层继承解析后的生效值）。满足时内核将内容存入 ContentStore，以 contentId 引用，visibleResult 置为 null。

**SkillLoadPart**

| 字段           | 类型                                | 含义                  |
| -------------- | ----------------------------------- | --------------------- |
| id             | string                              | part 标识             |
| type           | `data-skill-load`                   | 类型标记              |
| data.cause     | `default` / `explicit` / `reinject` | 注入来源              |
| data.ownerType | ownerType                           | 来源 owner 类型       |
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

#### Compaction Pair 语义

CompactionMarkerMessage（role=`user`, origin=`aos`）与 CompactionSummaryMessage（role=`assistant`, origin=`aos`, summary=`true`, finish=`completed`）配对。二者同时存在且 finish=`completed` 才算已完成，可作为 rebuild 起始边界。

### 2.10 RuntimeLogEntry

| 字段      | 类型                      | 必填 | 含义             |
| --------- | ------------------------- | ---- | ---------------- |
| id        | string                    | 是   | 日志条目唯一标识 |
| time      | RFC 3339 UTC              | 是   | 事件发生时间     |
| level     | `info` / `warn` / `error` | 是   | 日志级别         |
| op        | string                    | 是   | 操作名；点分形式 |
| ownerType | ownerType                 | 是   | 操作归属         |
| ownerId   | string                    | 否   | owner 标识       |
| agentId   | string                    | 否   | 所属 Agent       |
| sessionId | string                    | 否   | 所属 Session     |
| refs      | object                    | 否   | 关联引用         |
| data      | object                    | 否   | 操作相关数据     |

refs 字段：historyMessageId、historyPartId、contextRevision、contentId，均可选。

**RL 写入规则：** 仅 AOSCP 命令路径产生 RL 条目。查询不产生 RL 条目。Fold / unfold 操作仅产生 RL 条目，不写入 SH。

---

## 第三章 运行时结构

### 3.1 SessionContext

| 字段            | 类型              | 含义                                    |
| --------------- | ----------------- | --------------------------------------- |
| sessionId       | string            | 所属 Session                            |
| contextRevision | integer           | 单调递增；每次 rebuild 或增量更新后递增 |
| messages        | ContextMessage[]  | 下一次调用 RU 时传入的完整消息列表      |
| foldedRefs      | Set\<HistoryRef\> | 当前被折叠的历史引用集合                |

**HistoryRef 两种形式：**

- `{ historyMessageId }` — 折叠整条消息
- `{ historyMessageId, historyPartId }` — 折叠单个 part

**foldedRefs 语义：** 折叠引用不从 SC 中消失，而是降级为 fold placeholder（见 3.3）。foldedRefs 是纯运行时状态，不持久化，宕机恢复后不自动恢复（auto-fold 的 ref 在 rebuild 时重新生成）。

### 3.2 ContextMessage

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

RU 消费 `wire` 部分，发给 LiteLLM 之前剥离 `aos`。

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

### 3.3 Fold 占位符格式

#### tool-bash-folded（part 级折叠）

产生两条 ContextMessage：

**第一条**（tool call，正常投影，kind=`tool-bash-call`）：

```json
{
  "wire": {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "<toolCallId>",
        "function": { "name": "bash", "arguments": "..." }
      }
    ]
  },
  "aos": {
    "sourceMessageId": "...",
    "sourcePartId": "...",
    "kind": "tool-bash-call"
  }
}
```

**第二条**（folded result，kind=`tool-bash-folded`）：

```json
{
  "wire": {
    "role": "tool",
    "tool_call_id": "<toolCallId>",
    "content": "[[AOS-FOLDED]]\ntype: tool-bash-result\ntool_call_id: <toolCallId>\nsize: <sizeChars> chars, <lineCount> lines\npreview:\n<preview text>\nfile: $AOS_RUNTIME_DIR/blobs/<contentId>\nunfold: aos session context unfold --ref <messageId>:<partId>\n[[/AOS-FOLDED]]"
  },
  "aos": {
    "sourceMessageId": "...",
    "sourcePartId": "...",
    "kind": "tool-bash-folded"
  }
}
```

#### message-folded（整条消息折叠）

```json
{
  "wire": {
    "role": "<原消息 role>",
    "content": "[[AOS-FOLDED]]\ntype: message\nseq: <seq>\nrole: <role>\norigin: <origin>\nunfold: aos session context unfold --ref <messageId>\n[[/AOS-FOLDED]]"
  },
  "aos": {
    "sourceMessageId": "...",
    "sourcePartId": null,
    "kind": "message-folded"
  }
}
```

### 3.4 运行时注册表

| 结构                      | 作用                            | 持久化 |
| ------------------------- | ------------------------------- | ------ |
| discovery cache           | SkillManifest 索引              | 否     |
| skillText cache           | 默认 load skill 的 skillText    | 否     |
| plugin module cache       | plugin 运行入口模块引用         | 否     |
| pluginInstance registry   | 所有运行中的 pluginInstance     | 否     |
| resource registry         | ManagedResource                 | 否     |
| materialized files        | contentId → 本地文件路径映射    | 否     |
| admission hook registry   | 已注册的 Admission Hooks        | 否     |
| transform hook registry   | 已注册的 Transform Hooks        | 否     |
| event subscriber registry | 已订阅的 Runtime Event handlers | 否     |

### 3.5 PluginInstance 运行时视图

| 字段               | 类型                                                      | 含义                                       |
| ------------------ | --------------------------------------------------------- | ------------------------------------------ |
| instanceId         | string                                                    | ownerType + ownerId + skillName 组合       |
| skillName          | string                                                    | 所属 skill 名                              |
| ownerType          | ownerType                                                 | owner 类型                                 |
| ownerId            | string                                                    | owner 标识                                 |
| state              | `starting` / `running` / `stopping` / `stopped` / `error` | 实例状态                                   |
| startedAt          | RFC 3339 UTC                                              | 启动时间                                   |
| admissionHooks     | string[]                                                  | 已注册的 Admission Hook 名列表             |
| transformHooks     | string[]                                                  | 已注册的 Transform Hook 名列表             |
| eventSubscriptions | string[]                                                  | 已订阅的 Runtime Event 名列表              |
| capabilities       | string[]                                                  | 来自 CapabilityManifest 的 capability 集合 |
| lastError          | string                                                    | 最近错误；可选                             |

### 3.6 ManagedResource

| 字段            | 类型                                                      | 含义                           |
| --------------- | --------------------------------------------------------- | ------------------------------ |
| resourceId      | string                                                    | 资源标识                       |
| kind            | `app` / `service` / `worker`                              | 资源类型                       |
| ownerType       | ownerType                                                 | owner 类型                     |
| ownerId         | string                                                    | owner 标识                     |
| ownerInstanceId | string                                                    | 创建该资源的 pluginInstance id |
| state           | `starting` / `running` / `stopping` / `stopped` / `error` | 资源状态                       |
| startedAt       | RFC 3339 UTC                                              | 启动时间                       |
| endpoints       | string[]                                                  | 对外端点；可选                 |
| lastError       | string                                                    | 最近错误；可选                 |

### 3.7 ReActUnit 模块边界

| RU 负责              | 说明                                                      |
| -------------------- | --------------------------------------------------------- |
| 接收 SessionContext  | 读取 SC 当前 messages 窗口                                |
| 触发 Admission Hooks | 在命令路径正确位置调用；由 Execution Layer 执行           |
| 触发 Transform Hooks | 在管线特定位置调用；由 Execution Layer 执行               |
| 调用 LiteLLM         | 统一多 provider 的消息发送、流式响应、tool-calling        |
| 执行 bash            | 调用宿主 shell，捕获 stdout / stderr                      |
| 大内容判定与物化     | 判断 visible result 是否超阈值，超阈值时存入 ContentStore |
| 循环终止判断         | 检查 final answer / interrupt / compaction / archive      |
| 写 SH / 更新 SC      | 每步产出通过 AOSCP 命令写入 SH 并增量投影到 SC            |

| 由内核其他模块承担  | 归属                |
| ------------------- | ------------------- |
| AH / TH 注册表管理  | AOS Extension Layer |
| RE 投递             | RuntimeEventBus     |
| RL 写入             | Control Layer       |
| 权限判断            | AOSCP               |
| ContentStore 持久化 | State Layer         |

---

## 第四章 SH → SC 物化规则

### 4.1 起始边界确定

从 SH 末尾向前扫描，寻找最新已完成 compaction pair（marker + summary 同时存在且 finish=`completed`）。找到则起始于 marker 消息位置（含），否则起始于 SH 第一条消息。

### 4.2 消息收集

从起始点到 SH 最新消息，按 seq 升序收集。

### 4.3 Fold 处理

对每条收集到的消息及其 parts，检查对应的 HistoryRef 是否在 foldedRefs 中：

| foldedRefs 匹配类型                                   | 行为                                                                      |
| ----------------------------------------------------- | ------------------------------------------------------------------------- |
| `{ historyMessageId }`（整条消息）                    | 整条消息投影为 message-folded 占位符（见 3.3）                            |
| `{ historyMessageId, historyPartId }`（ToolBashPart） | tool result 投影为 tool-bash-folded 占位符；同条消息的 tool call 正常投影 |
| 未命中                                                | 正常投影（见 4.4）                                                        |

### 4.4 投影规则

| SH 消息特征                                                    | 投影结果（wire）                                                                | kind                                  |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------- |
| role=`user`, origin=`human`, TextPart                          | `{role:"user", content:text}`                                                   | `user-input`                          |
| role=`assistant`, origin=`assistant`, TextPart（无 tool_call） | `{role:"assistant", content:text}`                                              | `assistant-output`                    |
| role=`assistant`, 含 ToolBashPart（output-available/error）    | `{role:"assistant", tool_calls:[...]}` + `{role:"tool", content:visibleResult}` | `tool-bash-call` + `tool-bash-result` |
| role=`assistant`, ToolBashPart 在 foldedRefs                   | tool call 正常 + folded 占位符                                                  | `tool-bash-call` + `tool-bash-folded` |
| role=`user`, origin=`aos`, SkillLoadPart                       | `{role:"system", content:"[[AOS-SKILL <name>]]\n<skillText>"}`                  | `skill-load`                          |
| role=`user`, origin=`aos`, CompactionMarkerPart                | `{role:"user", content:"What did we do so far?"}`                               | `compaction-marker`                   |
| role=`assistant`, origin=`aos`, summary=true                   | `{role:"assistant", content:<summaryText>}`                                     | `compaction-summary`                  |
| role=`user`, origin=`aos`, InterruptPart                       | `{role:"system", content:"[[AOS-INTERRUPT <reason>]]"}`                         | `interrupt`                           |
| BootstrapPart                                                  | 不投影                                                                          | —                                     |
| ToolBashPart state=`input-streaming` / `input-available`       | 不投影（调用未完成）                                                            | —                                     |
| 整条消息在 foldedRefs                                          | message-folded 占位符                                                           | `message-folded`                      |

补充：含 ToolBashPart 的 assistant 消息投影为两条 ContextMessage。SkillLoadPart 按 seq 顺序插入，不聚合到列表头部。

### 4.5 文件物化

对 SC 中所有 kind=`tool-bash-folded` 的 ContextMessage，检查对应 ToolBashPart 的 `output.contentId`。若 `$AOS_RUNTIME_DIR/blobs/<contentId>` 不存在，则从 ContentStore 读取内容并写入该路径。

物化必须在 SC 投影完成后、返回给 RU 之前完成。

### 4.6 物化完成

物化完成后 contextRevision 加一。

---

## 第五章 AOSCP 操作规格

### 5.1 客户端与入口

| 客户端   | 使用方式                               | 典型使用者                |
| -------- | -------------------------------------- | ------------------------- |
| CLI      | `aos session dispatch --message "..."` | RU（通过 bash）、人类终端 |
| SDK      | `aos.session.dispatch({...})`          | pluginInstance、前端 UI   |
| HTTP/API | 与 SDK 同构                            | 远程面板、自动化管道      |

宿主至少注入 `AOS_AGENT_ID` 与 `AOS_SESSION_ID` 两个环境变量。

### 5.2 命令（20 个）

命令改变系统状态，经过 Admission Hooks，产生 RL 条目，返回 revision。

#### Skill 命令（6）

| 操作                    | 输入                        | 返回            | 副作用                                |
| ----------------------- | --------------------------- | --------------- | ------------------------------------- |
| `skill.load`            | name, sessionId?            | SkillLoadResult | 写 SH；若经 bash 调用额外写 tool-bash |
| `skill.start`           | PluginStartArgs             | PluginInstance  | 启动 plugin，验证 Capability          |
| `skill.stop`            | instanceId                  | instanceId      | 停止 pluginInstance                   |
| `skill.default.set`     | ownerType, ownerId?, entry  | revision        | 改写 CB，可能触发缓存刷新             |
| `skill.default.unset`   | ownerType, ownerId?, name   | revision        | 同上                                  |
| `skill.catalog.refresh` | ownerType, ownerId?, query? | SkillCatalog    | 刷新 discovery cache                  |

#### Agent 命令（3）

| 操作            | 输入            | 返回     | 副作用                     |
| --------------- | --------------- | -------- | -------------------------- |
| `agent.create`  | displayName?    | ACB      | 新建 Agent，触发激活流程   |
| `agent.update`  | agentId, fields | revision | 更新 ACB 可变字段          |
| `agent.archive` | agentId         | revision | 停止 pluginInstance 与资源 |

#### Session 命令（6）

| 操作                | 输入                        | 返回           | 副作用                                                |
| ------------------- | --------------------------- | -------------- | ----------------------------------------------------- |
| `session.create`    | agentId, title?             | SCB            | 改写 SCB，进入 bootstrap                              |
| `session.dispatch`  | DispatchArgs                | DispatchResult | 追加 userMessage，获取 lease，创建 RU（异步执行循环） |
| `session.append`    | sessionId, message          | revision       | 追加 SH Message（不触发执行）                         |
| `session.interrupt` | sessionId, reason, payload? | revision       | 写入 interrupt 事实                                   |
| `session.compact`   | sessionId                   | revision       | compaction + reinject + rebuild                       |
| `session.archive`   | sessionId                   | revision       | 释放 lease，停止 pluginInstance 与资源                |

**DispatchArgs：**

| 字段      | 类型         | 必填 | 含义                                  |
| --------- | ------------ | ---- | ------------------------------------- |
| sessionId | string       | 是   | 目标 Session                          |
| message   | MessageInput | 是   | 用户消息（role=user, content=string） |
| stream    | boolean      | 否   | 是否流式回传中间结果；默认 false      |

前置检查：Session 必须处于 `ready` 状态且 phase=`idle`，否则返回 `session.busy`（dispatched）或 `session.not_ready`（其他）。

**DispatchResult：**

| 字段            | 类型       | 含义                                                |
| --------------- | ---------- | --------------------------------------------------- |
| sessionId       | string     | 目标 Session                                        |
| dispatchId      | string     | 本次 dispatch 的唯一标识                            |
| finalMessageSeq | integer    | 循环结束后最后一条消息的 seq（blocking 模式时填充） |
| usage           | UsageStats | token 使用统计（blocking 模式时填充）               |

UsageStats：`{ promptTokens, completionTokens, totalTokens }`。

#### Session Context 命令（3）

| 操作                      | 输入             | 返回            | 写 SH | 副作用                                             |
| ------------------------- | ---------------- | --------------- | ----- | -------------------------------------------------- |
| `session.context.fold`    | sessionId, ref   | contextRevision | 否    | 将 ref 加入 foldedRefs，触发文件物化；写 RL        |
| `session.context.unfold`  | sessionId, ref   | contextRevision | 否    | 移除 ref，恢复完整投影；写 RL                      |
| `session.context.compact` | sessionId, auto? | revision        | 是    | 摘要 + compaction pair + reinject + rebuild；写 RL |

**fold 行为：** 将 ref 加入 foldedRefs → 若 ToolBashPart 的 contentId 存在则物化文件 → 在 SC 中替换为 fold placeholder → contextRevision + 1 → 写 RL。

**unfold 行为：** 从 foldedRefs 移除 ref → 从 SH 读取完整内容，重新投影为标准 ContextMessage → contextRevision + 1 → 写 RL。

#### Resource 命令（2）

| 操作             | 输入                      | 返回            | 副作用       |
| ---------------- | ------------------------- | --------------- | ------------ |
| `resource.start` | ownerType, ownerId?, spec | ManagedResource | 启动受管资源 |
| `resource.stop`  | resourceId                | resourceId      | 停止受管资源 |

### 5.3 查询（16 个）

查询读取系统状态，不经过 Admission Hooks，不产生 RL 条目。

#### Skill 查询（4）

| 操作                    | 输入                                | 返回               |
| ----------------------- | ----------------------------------- | ------------------ |
| `skill.list`            | —                                   | SkillCatalog       |
| `skill.show`            | name                                | SkillManifest      |
| `skill.default.list`    | ownerType, ownerId?                 | SkillDefaultRule[] |
| `skill.catalog.preview` | ownerType, ownerId?, query?, limit? | SkillCatalog       |

#### Agent 查询（2）

| 操作         | 输入    | 返回  |
| ------------ | ------- | ----- |
| `agent.list` | —       | ACB[] |
| `agent.get`  | agentId | ACB   |

#### Session 查询（2）

| 操作           | 输入            | 返回              |
| -------------- | --------------- | ----------------- |
| `session.list` | SessionListArgs | SessionListResult |
| `session.get`  | sessionId       | SCB               |

#### Session History 查询（2）

| 操作                   | 输入                       | 返回                      |
| ---------------------- | -------------------------- | ------------------------- |
| `session.history.list` | sessionId, cursor?, limit? | SH Message[], nextCursor? |
| `session.history.get`  | sessionId, messageId       | SH Message                |

#### Session Context 查询（2）

| 操作                      | 输入      | 返回               |
| ------------------------- | --------- | ------------------ |
| `session.context.get`     | sessionId | SessionContextView |
| `session.context.rebuild` | sessionId | contextRevision    |

`session.context.rebuild` 按第四章规则重新物化 SC，不写 SH，不写 RL。contextRevision 递增。

SessionContextView：`{ sessionId, contextRevision, messageCount, foldedRefCount }`。

#### Plugin 查询（2）

| 操作          | 输入                 | 返回             |
| ------------- | -------------------- | ---------------- |
| `plugin.list` | ownerType?, ownerId? | PluginInstance[] |
| `plugin.get`  | instanceId           | PluginInstance   |

#### Resource 查询（2）

| 操作            | 输入                 | 返回              |
| --------------- | -------------------- | ----------------- |
| `resource.list` | ownerType?, ownerId? | ManagedResource[] |
| `resource.get`  | resourceId           | ManagedResource   |

### 5.4 ContentStore 接口

```text
put(content: string) → contentId: string
get(contentId: string) → content: string
materialize(contentId: string) → localPath: string
```

v0.9 默认实现：SQLite `blobs` 表（blob_id, session_id, content, size_chars, line_count, created_at）；materialize 写入 `$AOS_RUNTIME_DIR/blobs/<contentId>`。可替换为 S3 / PostgreSQL Large Object 等。

Blob 不可变——一经写入不修改，可以无限期缓存，适合分布式环境。

### 5.5 共享数据结构

**AosResponse**

| 字段          | 类型    | 必填 | 含义         |
| ------------- | ------- | ---- | ------------ |
| ok            | boolean | 是   | 操作是否成功 |
| op            | string  | 是   | 操作名       |
| revision      | integer | 否   | 新修订号     |
| data          | object  | 否   | 成功结果     |
| error.code    | string  | 否   | 错误码       |
| error.message | string  | 否   | 错误信息     |
| error.details | object  | 否   | 额外上下文   |

**常用错误码：**

| code                | 含义                     |
| ------------------- | ------------------------ |
| `session.busy`      | Session phase=dispatched |
| `session.not_ready` | Session status≠ready     |
| `session.archived`  | Session 已归档           |
| `agent.archived`    | Agent 已归档             |
| `skill.not_found`   | skill 不存在             |
| `capability.denied` | 请求的 capability 未声明 |
| `permission.denied` | 权限不足                 |
| `revision.conflict` | 修订号冲突               |
| `lease.expired`     | dispatch lease 已过期    |

**其他结构：**

- `SkillLoadResult`：`{ name, skillText }`
- `PluginStartArgs`：`{ skillName, ownerType, ownerId? }`
- `MessageInput`：`{ role: "user", content: string }`
- `SessionListArgs`：`{ agentId?, cursor?, limit? }`
- `SessionListResult`：`{ items: SCB[], nextCursor? }`
- `RuntimeResourceSpec`：`{ kind, entry?, cwd?, args?, env? }`
- `UsageStats`：`{ promptTokens, completionTokens, totalTokens }`

### 5.6 JSON-only 约束

控制面响应必须 JSON-only。stdout 不得混入 prose。CLI 流式模式以 JSON Lines 格式逐行推送中间结果，最后一行为最终 AosResponse。

### 5.7 默认 skill 生效规则

| 维度  | 修改命中运行中 owner 时 | 立即影响 | 未来消费             |
| ----- | ----------------------- | -------- | -------------------- |
| load  | 刷新 skillText 缓存     | 否       | bootstrap / reinject |
| start | 立即 reconcile          | 是       | 同一请求内生效       |

---

## 第六章 扩展点完整清单

### 6.1 执行模型对比

| 维度            | Admission Hooks    | Transform Hooks     | Runtime Events           |
| --------------- | ------------------ | ------------------- | ------------------------ |
| 串行执行        | 是                 | 是                  | 并行（订阅者独立）       |
| 共享可变 output | 是（input 可改写） | 是（output 可改写） | 否（只读）               |
| 可拒绝操作      | 是（抛出异常）     | 否                  | 否                       |
| 阻塞主流程      | 是                 | 是                  | 否                       |
| 错误处理        | 抛出即失败当前操作 | 抛出即失败当前操作  | 错误被隔离，不影响主流程 |

Admission Hooks 和 Transform Hooks 按注册顺序串行执行：system → agent → session（before/transform 类型），session → agent → system（after 类型，但 AH/TH 没有 after 类型，after 均已归入 Runtime Events）。

### 6.2 注册权限

| ownerType | 可注册的 Admission Hooks | 可注册的 Transform Hooks    | 可订阅的 Runtime Events |
| --------- | ------------------------ | --------------------------- | ----------------------- |
| `system`  | 全部（13）               | 全部（6）                   | 全部（22）              |
| `agent`   | agent / session 相关 AH  | 全部 TH                     | agent / session 级 RE   |
| `session` | session 相关 AH          | session / tool / compute TH | session 级 RE           |

越权注册必须在注册时立即失败。

### 6.3 Admission Hooks 完整清单（13 个）

`input` 为只读；`output` 为可改写的准入对象（改写 output 可修改操作参数；拒绝操作时抛出异常）。

#### skill 相关 AH（6）

| hook                           | 可注册 owner             | 时机                    | input                            | output          |
| ------------------------------ | ------------------------ | ----------------------- | -------------------------------- | --------------- |
| `skill.index.refresh.before`   | system                   | 重新扫描 skill 元数据前 | skillRoot                        | —               |
| `skill.discovery.before`       | session / agent / system | discover 策略执行前     | ownerType, ownerId, query        | query（可改写） |
| `skill.default.resolve.before` | session / agent / system | 解析默认 skill 集合前   | ownerType, ownerId, plannedNames | —               |
| `skill.load.before`            | session / agent / system | load skillText 前       | name, sessionId                  | —               |
| `skill.start.before`           | session / agent / system | start plugin 前         | skillName, ownerType, ownerId    | —               |
| `skill.stop.before`            | session / agent / system | 停止 pluginInstance 前  | instanceId                       | —               |

#### session 相关 AH（5）

| hook                          | 可注册 owner             | 时机           | input                              | output            |
| ----------------------------- | ------------------------ | -------------- | ---------------------------------- | ----------------- |
| `session.dispatch.before`     | session / agent / system | dispatch 准入  | agentId, sessionId, userMessage    | —                 |
| `session.bootstrap.before`    | session / agent / system | 默认注入前     | agentId, sessionId, plannedNames   | —                 |
| `session.reinject.before`     | session / agent / system | reinject 前    | agentId, sessionId, plannedNames   | —                 |
| `session.message.beforeWrite` | session / agent / system | 消息写入 SH 前 | agentId, sessionId, message        | message（可替换） |
| `session.compaction.before`   | session / agent / system | compaction 前  | agentId, sessionId, fromSeq, toSeq | —                 |

#### compute / tool AH（2）

| hook             | 可注册 owner             | 时机            | input                       | output             |
| ---------------- | ------------------------ | --------------- | --------------------------- | ------------------ |
| `compute.before` | session / agent / system | 每次 LLM 调用前 | agentId, sessionId, lastSeq | —                  |
| `tool.before`    | session / agent / system | bash 执行前     | toolCallId, args            | args（可改写命令） |

### 6.4 Transform Hooks 完整清单（6 个）

Transform Hooks 改写流经数据，不可拒绝操作。`output` 为可改写的数据对象。

| hook                           | 可注册 owner             | 时机                      | input                              | output                          |
| ------------------------------ | ------------------------ | ------------------------- | ---------------------------------- | ------------------------------- |
| `session.system.transform`     | session / agent / system | RU 调用前构造 system 注入 | agentId, sessionId, userMessage?   | system（可覆盖）                |
| `session.messages.transform`   | session / agent / system | RU 调用前投影完成后       | agentId, sessionId, messages       | messages（可改写）              |
| `compute.params.transform`     | session / agent / system | LLM 参数构造完成后        | agentId, sessionId, params         | params（可改写）                |
| `tool.env`                     | session / agent / system | bash 执行前               | toolCallId, args                   | env（合并环境变量）             |
| `tool.after`                   | session / agent / system | bash 执行后               | toolCallId, rawResult              | result（可改写 visible result） |
| `session.compaction.transform` | session / agent / system | 摘要 prompt 构造时        | agentId, sessionId, fromSeq, toSeq | contextParts, summaryHint?      |

`tool.after` 读取 rawResult，返回的 result 成为 visible result 写入 SH。rawResult 由 AOS 记入 RL。

Transform Hooks 的结果只影响当次调用，不写入 SH，不修改 SC 持久状态。

### 6.5 Runtime Events 完整清单（22 个）

Runtime Events 是异步只读通知，fire-and-forget，不阻塞主流程。`payload` 为只读数据。

#### aos 级事件（2）

| event          | 可见 owner | 时机         | payload                       |
| -------------- | ---------- | ------------ | ----------------------------- |
| `aos.started`  | system     | AOS 启动完成 | cause, timestamp, catalogSize |
| `aos.stopping` | system     | AOS 即将停止 | reason, timestamp             |

#### skill 级事件（6）

| event                         | 可见 owner               | 时机            | payload                           |
| ----------------------------- | ------------------------ | --------------- | --------------------------------- |
| `skill.index.refresh.after`   | system                   | 扫描完成后      | indexedCount                      |
| `skill.discovery.after`       | session / agent / system | discover 完成后 | ownerType, ownerId, catalog       |
| `skill.default.resolve.after` | session / agent / system | 解析完成后      | ownerType, ownerId, resolvedNames |
| `skill.load.after`            | session / agent / system | load 完成后     | name, sessionId, skillText        |
| `skill.start.after`           | session / agent / system | plugin 启动后   | instanceId, skillName             |
| `skill.stop.after`            | session / agent / system | plugin 停止后   | instanceId                        |

#### agent 级事件（2）

| event            | 可见 owner     | 时机               | payload                   |
| ---------------- | -------------- | ------------------ | ------------------------- |
| `agent.started`  | agent / system | Agent 创建或恢复后 | agentId, cause, timestamp |
| `agent.archived` | agent / system | Agent 归档后       | agentId, timestamp        |

#### session 级事件（8）

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

#### compute 级事件（1）

| event           | 可见 owner               | 时机         | payload                                  |
| --------------- | ------------------------ | ------------ | ---------------------------------------- |
| `compute.after` | session / agent / system | LLM 调用结束 | agentId, sessionId, appendedMessageCount |

#### resource 级事件（3）

| event               | 可见 owner | 时机                   | payload                      |
| ------------------- | ---------- | ---------------------- | ---------------------------- |
| `resource.started`  | owner 向上 | ManagedResource 启动后 | resourceId, kind, endpoints? |
| `resource.stopping` | owner 向上 | 停止前                 | resourceId, kind             |
| `resource.error`    | owner 向上 | 失败                   | resourceId, kind, message    |

「owner 向上」：session-owned 可被 session/agent/system 接收；agent-owned 可被 agent/system 接收；system-owned 仅 system 接收。

### 6.6 Plugin 工厂接口

```typescript
type Plugin = (ctx: PluginContext) => Promise<{
  admissionHooks?: AdmissionHookRegistrations;
  transformHooks?: TransformHookRegistrations;
  eventSubscriptions?: EventSubscriptions;
}>;
```

AOS 执行 start 时，加载 SkillManifest.plugin 指向的模块，对每个满足 Plugin 签名的导出函数执行一次工厂调用。工厂函数只在 pluginInstance 启动时执行一次。

### 6.7 PluginContext

| 字段      | 类型            | 含义                                     |
| --------- | --------------- | ---------------------------------------- |
| ownerType | ownerType       | 当前 pluginInstance 的 owner 类型        |
| ownerId   | string          | 当前 pluginInstance 的 owner 标识        |
| skillName | string          | 当前 skill 名                            |
| agentId   | string          | 当 ownerType 为 agent 或 session 时存在  |
| sessionId | string          | 当 ownerType 为 session 时存在           |
| aos       | AosSDK 受限子集 | 受 CapabilityManifest 约束的控制面客户端 |

### 6.8 热更新规则

- SKILL.md 变化：刷新 SkillManifest，失效 skillText 缓存，发出 `skill.index.refresh.after` 事件。
- `metadata.aos-plugin` 解析结果变化：失效 plugin module cache。
- 既有 SH Message 不可被重写。
- 运行中 pluginInstance 继续使用启动时模块，直到 owner 生命周期结束或显式重启。
- 新的显式 load、未来 bootstrap reinjection 与未来 plugin 启动使用新版本。

---

## 第七章 大内容物化与审计

### 7.1 visible result 与 raw result

```
bash 执行 → raw result → tool.after Transform Hook → visible result
```

- visible result → SH（ToolBashOutput.visibleResult 或 contentId）
- raw result → RL

### 7.2 大内容物化流程

当 `len(visible result) > autoFoldThreshold`（三层继承解析后的生效值，默认 16,384）：

1. `ContentStore.put(visibleResult)` → `contentId`
2. ToolBashPart.output 写入：`{ visibleResult: null, contentId, sizeChars, lineCount, preview }`
3. `ContentStore.materialize(contentId)` → 确保文件存在于 `$AOS_RUNTIME_DIR/blobs/<contentId>`
4. 将对应 HistoryRef 加入 foldedRefs，SC 中生成 tool-bash-folded 占位符（含 materializedPath）

当 `len(visible result) <= autoFoldThreshold`：

- ToolBashPart.output 写入：`{ visibleResult: "<full content>", contentId: null }`

### 7.3 会话可见事实边界

| 事实                       | 进入 SH                           |
| -------------------------- | --------------------------------- |
| 用户输入                   | 是                                |
| 模型输出                   | 是                                |
| bash 调用与 visible result | 是（visibleResult 或 contentId）  |
| 显式 `aos skill load`      | 是（tool-bash + data-skill-load） |
| 默认 skill 注入            | 是                                |
| compaction pair            | 是                                |
| reinject                   | 是                                |
| interrupt                  | 是                                |
| bootstrap marker           | 是                                |
| fold / unfold 操作         | 否（只进 RL）                     |
| pluginInstance 私有日志    | 否（进入 RL）                     |
| bash raw result            | 否（进入 RL）                     |
| blob 物化操作              | 否（进入 RL）                     |
| AOSCP 查询操作             | 否（不进 RL，不进 SH）            |

### 7.4 控制面写入顺序

**规则一：** 影响 SH 的命令，先写 SH，再更新 SC。

**规则二：** 只影响 SC 的命令（fold / unfold），只改内存并写 RL，不写 SH。

**规则三：** 所有 AOSCP 命令，完成时写 RL。

**规则四：** 大内容命令，先写 ContentStore，再写 SH（引用），再更新 SC（占位符）。不得反向。

---

## 第八章 生命周期与执行时序

### 8.1 AOS 启动顺序

| 步骤 | 动作                                   | 触发                                                              |
| ---- | -------------------------------------- | ----------------------------------------------------------------- |
| 1    | 读取 AOSCB                             | —                                                                 |
| 2    | skill.index.refresh                    | AH: `skill.index.refresh.before`；RE: `skill.index.refresh.after` |
| 3    | 注册内建 skill `aos`                   | —                                                                 |
| 4    | system 级 discover                     | AH: `skill.discovery.before`；RE: `skill.discovery.after`         |
| 5    | 预热 system 级默认 load skillText 缓存 | —                                                                 |
| 6    | 启动 system 级默认 start plugin        | AH: `skill.start.before`；RE: `skill.start.after`                 |
| 7    | AOS ready                              | RE: `aos.started`                                                 |

### 8.2 Agent 激活顺序

| 步骤 | 动作                                  | 触发                                              |
| ---- | ------------------------------------- | ------------------------------------------------- |
| 1    | 读取或创建 ACB                        | —                                                 |
| 2    | 预热 agent 级默认 load skillText 缓存 | —                                                 |
| 3    | agent 级 start reconcile              | AH: `skill.start.before`；RE: `skill.start.after` |
| 4    | 建立 agent 级 event 订阅              | —                                                 |
| 5    | Agent ready                           | RE: `agent.started`                               |

### 8.3 Session Bootstrap 顺序

| 步骤 | 动作                                    | 写入 | 触发                                                                  |
| ---- | --------------------------------------- | ---- | --------------------------------------------------------------------- |
| 1    | 创建/读取 SCB, status=`initializing`    | SCB  | —                                                                     |
| 2    | 预热 session 级默认 load skillText 缓存 | —    | —                                                                     |
| 3    | session 级 start reconcile              | —    | AH: `skill.start.before`；RE: `skill.start.after`                     |
| 4    | phase = `bootstrapping`                 | SCB  | —                                                                     |
| 5    | 追加 begin marker                       | SH   | AH: `session.message.beforeWrite`                                     |
| 6    | skill.default.resolve                   | —    | AH: `skill.default.resolve.before`；RE: `skill.default.resolve.after` |
| 7    | 开始默认注入                            | —    | AH: `session.bootstrap.before`                                        |
| 8    | 注入默认 load skill skillText           | SH   | AH: `skill.load.before`；RE: `skill.load.after`（each）               |
| 9    | 追加 done marker                        | SH   | AH: `session.message.beforeWrite`                                     |
| 10   | 结束默认注入                            | —    | RE: `session.bootstrap.after`                                         |
| 11   | rebuild SC                              | —    | —                                                                     |
| 12   | session 级 discover                     | —    | AH: `skill.discovery.before`；RE: `skill.discovery.after`             |
| 13   | status=`ready`, phase=`idle`            | SCB  | RE: `session.started`                                                 |

**默认 load 解析规则：**

1. 取 AOSCB / ACB / SCB 三层条目，只看 load 条目
2. system → agent → session 顺序覆盖同名冲突
3. 最终保留 load=enable 的 skill
4. 从 skillText 缓存取正文；缺失则先补齐
5. 强制追加 `aos` skill
6. 按 system → agent → session 排序注入；每个 skill 一条消息

**默认 start 消费规则：** 各 owner 生命周期起点独立消费各层 CB 中的 start 条目。

### 8.4 session.dispatch 执行顺序

| 步骤 | 动作                                      | 写入  | 触发                              |
| ---- | ----------------------------------------- | ----- | --------------------------------- |
| 1    | 校验：status=ready, phase=idle            | —     | —                                 |
| 2    | AH: session.dispatch.before               | —     | AH: `session.dispatch.before`     |
| 3    | 追加 userMessage 到 SH                    | SH    | AH: `session.message.beforeWrite` |
| 4    | 增量投影到 SC                             | —     | —                                 |
| 5    | 获取 lease，phase = `dispatched`          | SCB   | —                                 |
| 6    | **立即返回 { dispatchId }**（异步分界点） | —     | —                                 |
| 7    | 创建 ReActUnit                            | —     | —                                 |
| 8    | ReActUnit 执行 ReAct 循环                 | SH/SC | —（见 8.5）                       |
| 9    | 释放 lease，phase = `idle`                | SCB   | —                                 |
| 10   | 写 RL                                     | RL    | RE: `session.dispatch.after`      |

### 8.5 ReAct 循环主形态

| 步骤 | 动作                                       | 写入 | 触发                                                                                       |
| ---- | ------------------------------------------ | ---- | ------------------------------------------------------------------------------------------ |
| 1    | 取 SC.messages                             | —    | —                                                                                          |
| 2    | Transform: system / messages / params      | —    | TH: `session.system.transform` → `session.messages.transform` → `compute.params.transform` |
| 3    | AH: compute.before                         | —    | AH: `compute.before`                                                                       |
| 4    | 调用 LiteLLM（流式）                       | —    | —                                                                                          |
| 5    | 判断返回类型                               | —    | —                                                                                          |
| 5a   | tool_call 分支：TH: tool.env               | —    | TH: `tool.env`                                                                             |
| 5b   | AH: tool.before                            | —    | AH: `tool.before`                                                                          |
| 5c   | 执行 bash                                  | —    | —                                                                                          |
| 5d   | TH: tool.after → visible result            | —    | TH: `tool.after`                                                                           |
| 5e   | 大内容判定；超阈值则存 ContentStore + 物化 | blob | —                                                                                          |
| 5f   | 写 SH（assistant + tool result）           | SH   | AH: `session.message.beforeWrite`（each）                                                  |
| 5g   | 增量投影到 SC（含 fold 处理）              | —    | RE: `compute.after`                                                                        |
| 5h   | 返回步骤 1                                 | —    | —                                                                                          |
| 6    | final answer 分支：写 SH                   | SH   | AH: `session.message.beforeWrite`                                                          |
| 7    | RE: compute.after                          | —    | RE: `compute.after`                                                                        |
| 8    | 检查终止条件                               | —    | —                                                                                          |
| 8a   | 继续 → 步骤 1                              | —    | —                                                                                          |
| 8b   | interrupt → 写 interrupt 事实              | SH   | RE: `session.interrupted`                                                                  |
| 8c   | compaction → 见 8.6                        | SH   | —                                                                                          |
| 8d   | 完成 → 退出循环                            | —    | —                                                                                          |

### 8.6 Compaction 顺序

| 步骤 | 动作                                        | 写入 | 触发                                                        |
| ---- | ------------------------------------------- | ---- | ----------------------------------------------------------- |
| 1    | phase = `compacting`                        | SCB  | —                                                           |
| 2    | AH: session.compaction.before               | —    | AH: `session.compaction.before`                             |
| 3    | 计算区间 [fromSeq, toSeq]                   | —    | —                                                           |
| 4    | TH: session.compaction.transform            | —    | TH: `session.compaction.transform`                          |
| 5    | 构造摘要 prompt，调用 LLM                   | —    | —                                                           |
| 6    | 追加 CompactionMarkerMessage                | SH   | AH: `session.message.beforeWrite`                           |
| 7    | 追加 CompactionSummaryMessage               | SH   | AH: `session.message.beforeWrite`                           |
| 8    | reinject                                    | SH   | AH: `session.reinject.before`；RE: `session.reinject.after` |
| 9    | rebuild SC                                  | —    | —                                                           |
| 10   | phase = `idle`（或 dispatched，若在循环内） | SCB  | RE: `session.compaction.after`                              |

### 8.7 归档顺序

| 作用域  | 动作                                                              | 触发                   |
| ------- | ----------------------------------------------------------------- | ---------------------- |
| Session | 释放 lease，停止 pluginInstance 与 ManagedResource，写 archivedAt | RE: `session.archived` |
| Agent   | 停止 pluginInstance 与 ManagedResource，写 archivedAt             | RE: `agent.archived`   |
| AOS     | 发出 `aos.stopping` 事件，停止 system 级资源，释放注册表          | RE: `aos.stopping`     |

---

## 第九章 恢复协议与一致性规则

### 9.1 恢复依据

恢复只依赖：AOSCB、ACB / SCB、SessionHistory。ContentStore 中的 blob 是辅助依据——SH 中的 contentId 必须能在 ContentStore 中找到对应内容。所有运行时结构可重建。

### 9.2 Lease 恢复

| SCB 状态                         | 恢复动作                                                  |
| -------------------------------- | --------------------------------------------------------- |
| phase=`idle`                     | 直接使用，无需处理                                        |
| phase=`dispatched`，lease 未过期 | 等待 TTL 自然到期，然后清空 lease，phase=`idle`           |
| phase=`dispatched`，lease 已过期 | 立即清空 lease，phase=`idle`                              |
| phase=`compacting`               | 视为 interrupted，清空 phase=`idle`，等待下次手动 compact |

### 9.3 SessionContext 恢复

执行一次 rebuild：

1. 找到最新已完成 compaction pair，从 marker 开始物化
2. 清空 foldedRefs
3. 对所有 output.contentId 存在的 ToolBashPart 执行 auto-fold（加入 foldedRefs，生成占位符）
4. 执行文件物化（见第四章 4.5）
5. contextRevision 递增

注意：恢复后 foldedRefs 只包含 auto-fold（大内容）。人工 fold 操作在恢复后不保留。

### 9.4 Bootstrap 恢复情形

| marker 状态       | 含义     | 恢复动作                        |
| ----------------- | -------- | ------------------------------- |
| 无 begin          | 尚未开始 | 完整 bootstrap                  |
| 有 begin，无 done | 中途崩溃 | 补齐剩余注入，写 done，置 ready |
| 有 done           | 已完成   | 直接置 ready                    |

结构不一致或无法解析时，恢复必须失败：RE: `session.error { source: "recovery", recoverable: false }`，保持 `initializing`。

### 9.5 Compaction 完整性判定

已完成条件：marker + summary 同时存在，且 `summary.metadata.finish = completed`。未满足则该 pair 不作为 rebuild 起始点。

### 9.6 物化文件恢复

Session 恢复时，对所有需要物化的 contentId：

1. 检查 `$AOS_RUNTIME_DIR/blobs/<contentId>` 是否存在
2. 不存在则调用 `ContentStore.get(contentId)` 获取内容，写入该路径
3. ContentStore 中不存在该 contentId 时，对应占位符展示错误信息，不中止恢复流程

### 9.7 写入顺序一致性

严格遵守第七章 7.4 的四条规则。违反任一规则的实现视为不一致，不符合本规范。

---

## 第十章 延后事项

### 10.1 权限字段位置

AOSCB、ACB、SCB 都保留 permissions 字段，参与 system → agent → session 继承解析。权限判断由 AOSCP 负责。v0.9 语法未固定，字段位置已预留。

### 10.2 v0.9 延后项

| 项目                          | 状态                                  | 影响                         |
| ----------------------------- | ------------------------------------- | ---------------------------- |
| 权限 DSL 与 enforcement point | 字段预留，语法未固定                  | 权限校验受限                 |
| Admission Hook 超时机制       | 未实现                                | plugin 超时阻塞主流程        |
| Admission Hook 沙箱与资源配额 | 未实现                                | 依赖 plugin 自律             |
| Capability 强制校验           | 声明格式已定义，校验为 warning        | 安全边界不强制               |
| Session loop in-flight 恢复   | bootstrap 有幂等协议；dispatch 中途无 | in-flight 任务视为丢失       |
| compaction contextParts 追踪  | 不进 SH                               | 该次 compaction 不可严格重放 |
| SC 自动调度策略               | 接口已定义，默认算法不内置            | 由 skill / plugin 实现       |
| Fold 部分展开                 | 未实现；AI 通过 bash 读文件替代       | 无原生 partial unfold        |
| Skill 可替换发现算法          | 接口已定义，默认文件系统扫描          | 可逐步接入复杂策略           |
| RL 离线分析                   | 仅基础追加写                          | 高级分析需外部工具           |
| 热更新滚动升级                | 运行中 pluginInstance 使用启动时模块  | 需显式重启                   |
| 分布式 EventBus               | 单进程内存 bus                        | 跨节点事件需替换实现         |
| 分布式 ContentStore           | SQLite 默认实现                       | 多节点共享需替换为 S3 等     |
| Lease 分布式锁                | 单进程内存实现                        | 多节点竞争需 Redis / etcd    |

v0.9 优先保证：核心流程可运行、SH 可恢复、SC 可重建、AOSCP 契约可信赖、Fold / Unfold 可用、大内容按引用存储并物化、Lease 单进程单写者。
