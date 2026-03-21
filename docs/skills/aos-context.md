# aos-context Skill

_上下文管理参考实现。投影、折叠、压缩、大内容检测。_

_关联文档：[aos-hooks.md](../specs/aos-hooks.md) §3.5 · [aos-content.md](../specs/aos-content.md) · [aos-lifecycle.md](../specs/aos-lifecycle.md)_

---

## 1. 概述

`aos-context` 是项目提供的上下文管理 Skill，以 system 级 Plugin 运行。它注册以下 Hook：

| Hook                | 分类 | 职责                                        |
| ------------------- | ---- | ------------------------------------------- |
| `tool.after`        | TH   | 大内容检测与存储                            |
| `context.assemble`  | TH   | SH→SC 投影（折叠、占位符）                  |
| `context.compact`   | TH   | 压缩策略（摘要 prompt）                     |
| `context.ingest`    | RE   | 状态追踪（auto-fold 候选、compaction 边界） |
| `context.afterTurn` | RE   | 预留扩展（当前 no-op）                      |

**AOS 内核不提供任何上下文算法的默认实现。** 如本 Skill 被删除或未启动，上下文将持续膨胀直至溢出。这是预期行为——AOS 内核提供机制，不提供策略。

---

## 2. 大内容检测（tool.after）

`aos-context` 注册 `tool.after` TH，在 bash 执行结果返回后检查内容长度：

1. 读取 `autoFoldThreshold`（system → agent → session 三层继承解析，默认 16384 字符）
2. 若 `len(result) > autoFoldThreshold`：
   - 通过 AOSCP `content.put` 将内容存入 ContentStore，获得 `contentId`
   - 返回修改后的 output：`{ visibleResult: null, contentId, sizeChars, lineCount, preview }`
3. 若未超过阈值：不做修改，原始 result 直接写入 SH

---

## 3. 投影规则（context.assemble）

从 SH 末尾向前扫描，寻找最新已完成 compaction pair（marker + summary 且 `finish=completed`）。找到则起始于 marker 位置（含），否则起始于 SH 第一条消息。按 seq 升序收集。

| SH 消息特征                                                | 投影结果 (wire)                                                | kind                                  |
| ---------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------- |
| role=`user`, origin=`human`, TextPart                      | `{role:"user", content:text}`                                  | `user-input`                          |
| role=`assistant`, TextPart（无 tool_call）                 | `{role:"assistant", content:text}`                             | `assistant-output`                    |
| role=`assistant`, 含 ToolBashPart (output-available/error) | tool_calls + tool result                                       | `tool-bash-call` + `tool-bash-result` |
| role=`assistant`, ToolBashPart 在 foldedRefs               | tool call 正常 + folded 占位符                                 | `tool-bash-call` + `tool-bash-folded` |
| role=`user`, origin=`aos`, SkillLoadPart                   | `{role:"system", content:"[[AOS-SKILL <name>]]\n<skillText>"}` | `skill-load`                          |
| role=`user`, origin=`aos`, CompactionMarkerPart            | `{role:"user", content:"What did we do so far?"}`              | `compaction-marker`                   |
| role=`assistant`, origin=`aos`, summary=true               | `{role:"assistant", content:<summaryText>}`                    | `compaction-summary`                  |
| role=`user`, origin=`aos`, InterruptPart                   | `{role:"system", content:"[[AOS-INTERRUPT <reason>]]"}`        | `interrupt`                           |
| BootstrapPart                                              | 不投影                                                         | —                                     |
| ToolBashPart state=`input-streaming`/`input-available`     | 不投影（调用未完成）                                           | —                                     |
| 整条消息在 foldedRefs                                      | message-folded 占位符                                          | `message-folded`                      |

含 ToolBashPart 的 assistant 消息投影为两条 ContextMessage。SkillLoadPart 按 seq 顺序插入。

---

## 4. Fold 占位符格式

### 4.1 tool-bash-folded（part 级折叠）

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
    "content": "[[AOS-FOLDED]]\ntype: tool-bash-result\ntool_call_id: <toolCallId>\nsize: <sizeChars> chars, <lineCount> lines\npreview:\n<preview text>\nread: aos call content.read --payload '{\"contentId\":\"<contentId>\"}'\nhead: aos call content.read --payload '{\"contentId\":\"<contentId>\",\"limit\":20}'\ngrep: aos call content.search --payload '{\"contentId\":\"<contentId>\",\"pattern\":\"<pattern>\"}'\nunfold: aos call session.context.unfold --payload '{\"sessionId\":\"<sessionId>\",\"ref\":{\"historyMessageId\":\"<msgId>\",\"historyPartId\":\"<partId>\"}}'\n[[/AOS-FOLDED]]"
  },
  "aos": {
    "sourceMessageId": "...",
    "sourcePartId": "...",
    "kind": "tool-bash-folded"
  }
}
```

### 4.2 message-folded（整条消息折叠）

```json
{
  "wire": {
    "role": "<原消息 role>",
    "content": "[[AOS-FOLDED]]\ntype: message\nseq: <seq>\nrole: <role>\norigin: <origin>\nunfold: aos call session.context.unfold --payload '{\"sessionId\":\"<sessionId>\",\"ref\":{\"historyMessageId\":\"<msgId>\"}}'\n[[/AOS-FOLDED]]"
  },
  "aos": {
    "sourceMessageId": "...",
    "sourcePartId": null,
    "kind": "message-folded"
  }
}
```

---

## 5. Fold / Unfold 机制

**三种触发：**

- **Auto-fold：** `tool.after` TH 检测到 bash 输出超过 autoFoldThreshold 时自动触发
- **AI 主动 fold：** `aos call session.context.fold --payload '{...}'`
- **AI 主动 unfold：** `aos call session.context.unfold --payload '{...}'`

**foldedRefs 管理：**

- foldedRefs 是纯运行时状态，不持久化
- auto-fold 的 ref 在 rebuild 时从 SH 中重新提取（扫描所有 output.contentId 存在的 ToolBashPart）
- 人工 fold 操作在 rebuild 后不保留

**Fold vs Compact：**

| 维度     | Fold            | Compact       |
| -------- | --------------- | ------------- |
| 操作对象 | 单条消息或 part | 一段历史区间  |
| 可逆性   | 完全可逆        | 不可逆        |
| 类比     | 换页到 swap     | 内存压缩 / GC |

---

## 6. Compaction 策略（context.compact）

默认始终返回 `mode: "instruct"`，由内核执行 LLM 调用。

步骤：

1. 通过 `session.history.list` AOSCP 查询获取 [fromSeq, toSeq] 范围内的消息
2. 提取文本内容，构建摘要 prompt
3. 返回 `{ mode: "instruct", summaryPrompt, fromSeq, toSeq, reinjectSkills: true }`

summaryPrompt 模板（大纲）：

```
请将以下对话摘要为简洁的总结，保留：
- 关键决策和结论
- 重要的代码变更和文件路径
- 未完成的任务和待办事项
- 用户偏好和约束条件

对话内容：
{messages}
```

---

## 7. Rebuild 流程

1. 清空 SC（messages = [], foldedRefs = {}）
2. 确定起始边界（最新已完成 compaction pair，或 SH 第一条）
3. 按 seq 升序收集消息
4. 对每条消息执行投影规则
5. 恢复 auto-fold：扫描 SH，对所有 output.contentId 存在的 ToolBashPart 加入 foldedRefs
6. contextRevision 递增

恢复后 foldedRefs 只包含 auto-fold（大内容）。人工 fold 操作不保留。

---

## 8. context.ingest 行为

- 检查新消息是否包含 ToolBashPart 且有 contentId（大内容）→ 自动加入 foldedRefs
- 更新 lastCompactionSeq（如果消息是 CompactionSummary 且 `finish=completed`）

---

## 9. context.afterTurn 行为

当前为 no-op，预留扩展。

---

## 10. 自定义引擎指南

### 10.1 最小实现

只注册 `context.assemble` TH。compact 不被处理——上下文不会被压缩。

### 10.2 完整实现

注册全部 5 个 Hook（3 TH + 2 RE）：`tool.after`、`context.assemble`、`context.compact`、`context.ingest`、`context.afterTurn`。

### 10.3 managed 模式 compact

引擎返回 `mode: "managed"` 后，自行通过 AOSCP 完成：

- `session.history.list` — 读取历史
- `session.append` — 写入 CompactionMarker 和 CompactionSummary
- 内核在 managed 模式下不执行 compaction 相关的 LLM 调用和 SH 写入（reinject 和 rebuild 仍由内核执行）

### 10.4 约束

- `context.assemble` 的输出 messages 必须符合 ContextMessage 格式
- `context.compact` 的输出必须包含 fromSeq 和 toSeq
- 引擎通过 defaultSkills 的 `start: enable` 启用
- 替换引擎：在 agent/session 级 defaultSkills 中 `start: enable` 自定义引擎 Skill。自定义引擎注册同名算法 TH（`context.assemble`、`context.compact`），TH 按 owner 层级串行执行，后注册者输出覆盖前者。`aos-context`（system-owned）继续运行但其输出被覆盖
