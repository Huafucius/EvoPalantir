# AOS Content Store Spec

_内容存储。blob 存取、通过 AOSCP 读取、后端可替换。_

_关联文档：[aos-hooks.md](./aos-hooks.md) · [aos-aoscp.md](./aos-aoscp.md) · [aos-data-model.md](./aos-data-model.md)_

---

## 1. 总则

### 1.1 职责

ContentStore 存储超过 autoFoldThreshold 的大内容。SessionHistory 中通过 contentId 按引用指向 ContentStore 中的 blob。

### 1.2 不可变性

Blob 一经写入不可修改。contentId 和内容的映射关系永久不变。这使得 blob 可以无限期缓存，天然适合分布式环境。

### 1.3 无文件物化

AOS 不将 blob 写入本地文件系统。所有大内容访问通过 AOSCP 操作（`content.read`、`content.search`）完成。

这保持了「AOSCP 是唯一边界」的一致性。AI 不需要知道内容存储在哪里——它只需要通过 AOSCP 读取。分布式场景下，节点 A 存的内容，节点 B 的 AI 一样可以通过 AOSCP 读取。

---

## 2. 存储接口

```
put(content: string, sessionId: string) → contentId: string
get(contentId: string) → content: string
exists(contentId: string) → bool
```

### 2.1 put

存入内容，返回 contentId。同时记录 sessionId、sizeChars、lineCount、createdAt。

### 2.2 get

按 contentId 读取完整内容。contentId 不存在时抛异常。

### 2.3 exists

检查 contentId 是否存在。

---

## 3. AOSCP 访问

AI 通过 bash 调用 AOSCP 操作读取大内容。

### 3.1 content.read

```bash
# 读取全部
aos call content.read --payload '{"contentId":"blob-abc123"}'

# 读取前 20 行
aos call content.read --payload '{"contentId":"blob-abc123","limit":20}'

# 从第 100 行开始读 50 行
aos call content.read --payload '{"contentId":"blob-abc123","offset":100,"limit":50}'
```

返回：

```json
{
  "ok": true,
  "data": {
    "contentId": "blob-abc123",
    "content": "...",
    "totalLines": 500,
    "totalChars": 25000
  }
}
```

### 3.2 content.search

```bash
aos call content.search --payload '{"contentId":"blob-abc123","pattern":"error"}'
```

返回：

```json
{
  "ok": true,
  "data": {
    "contentId": "blob-abc123",
    "matches": [
      { "lineNumber": 42, "text": "  Error: connection refused" },
      { "lineNumber": 108, "text": "  RuntimeError: timeout" }
    ]
  }
}
```

---

## 4. 与 SessionHistory 的集成

### 4.1 Auto-fold 触发

内核不执行 auto-fold 判定。大内容检测与存储由 `aos-context` Skill 的 `tool.after` TH 负责：

1. `tool.after` TH 检查 `len(visibleResult) > autoFoldThreshold`（三层继承解析后的生效值，默认 16384）
2. 满足时，TH 通过 AOSCP `content.put` 将内容存入 ContentStore，获得 `contentId`
3. TH 返回修改后的 output：`{ visibleResult: null, contentId, sizeChars, lineCount, preview }`
4. 内核将 TH 返回的 output 写入 SH
5. `context.ingest` RE 通知上下文引擎，引擎将对应 HistoryRef 加入 foldedRefs
6. `context.assemble` TH 在 SC 中生成 tool-bash-folded 占位符

如无 Skill 注册 `tool.after`，原始 visible result 直接写入 SH，不做折叠。

当 `len(visibleResult) <= autoFoldThreshold`：

- TH 不做修改，原始 visible result 写入 SH：`{ visibleResult: "<full content>", contentId: null }`

### 4.2 Fold 占位符中的 AOSCP 命令

Fold 占位符中包含以下命令提示，供 AI 使用：

```
read: aos call content.read --payload '{"contentId":"<contentId>"}'
head: aos call content.read --payload '{"contentId":"<contentId>","limit":20}'
grep: aos call content.search --payload '{"contentId":"<contentId>","pattern":"<pattern>"}'
unfold: aos call session.context.unfold --payload '{...}'
```

### 4.3 visible result 与 raw result

```
bash 执行 → raw result → tool.after Transform Hook → visible result
```

- visible result → SH（visibleResult 或 contentId 引用）
- raw result → RL（审计）

---

## 5. 后端可替换

### 5.1 接口定义

ContentStore 是抽象接口。实现只需提供 put / get / exists 三个方法。

### 5.2 SQLite 默认实现

```sql
CREATE TABLE blobs (
    blob_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    size_chars INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### 5.3 未来后端

- PostgreSQL Large Object
- S3 / 对象存储
- 分布式文件系统

切换后端只需替换 ContentStore 实现，不影响 SH 中的 contentId 引用和 AOSCP 操作语义。
