# AOS Transport Spec

_传输协议。daemon 模式、HTTP/SSE、统一端点、鉴权。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-aoscp.md](./aos-aoscp.md) · [aos-deployment.md](./aos-deployment.md)_

---

## 1. Daemon

AgentOS 以 daemon 形式运行。CLI、SDK、前端通过 HTTP 与 daemon 通信；Plugin 通过 stdio JSON-RPC 与 daemon 通信（见 [aos-plugin.md](./aos-plugin.md)）。

### 1.1 启动

```bash
# 前台运行，Ctrl+C 优雅退出
aos daemon start

# 后台运行
aos daemon start --detach

# 指定端口
aos daemon start --port 9000
```

前置条件：

- `AOS_API_TOKEN` 环境变量已设置，否则拒绝启动
- skillRoot 目录存在

### 1.2 停止

```bash
aos daemon stop
```

向后台 daemon 发送 SIGTERM，触发优雅关闭流程（见 [aos-lifecycle.md](./aos-lifecycle.md) §1.3）。

### 1.3 默认端口

`8420`。可通过 `--port` 或 `AOS_PORT` 环境变量覆盖。

### 1.4 实现

基于 FastAPI + uvicorn。

- 单机部署使用单 worker + async 并发（内核依赖内存状态）
- 多 worker 部署需先将 Lease/EventBus 切换为外部后端（见 [aos-deployment.md](./aos-deployment.md) §3）
- 开发模式支持 `--reload`（file watcher 自动重启）

---

## 2. HTTP 端点

### 2.1 统一操作端点

```
POST /aoscp
Content-Type: application/json
Authorization: Bearer <token>
```

请求体：

```json
{
  "op": "session.dispatch",
  "sessionId": "sess-abc",
  "message": { "role": "user", "content": "hello" }
}
```

`op` 字段指定 AOSCP 操作名（见 [aos-aoscp.md](./aos-aoscp.md)），其余字段为操作参数，平铺在顶层。

响应：统一 AosResponse 格式（见 §4）。

### 2.2 SSE 事件流

```
GET /aoscp/events
Authorization: Bearer <token>
```

查询参数（可选）：

| 参数      | 类型   | 含义                                   |
| --------- | ------ | -------------------------------------- |
| scope     | string | 过滤范围：`system`、`agent`、`session` |
| agentId   | string | 过滤 Agent                             |
| sessionId | string | 过滤 Session                           |

返回 Server-Sent Events 流，推送 Runtime Event。

```
event: session.dispatch.after
data: {"name":"session.dispatch.after","payload":{"agentId":"agent-1","sessionId":"sess-1","dispatchId":"d-1","appendedCount":5},"timestamp":"2026-01-01T00:00:00Z"}

event: compute.after
data: {"name":"compute.after","payload":{"agentId":"agent-1","sessionId":"sess-1","appendedMessageCount":2},"timestamp":"2026-01-01T00:00:01Z"}
```

客户端通过 scope 参数缩小关注范围。未指定 scope 时，返回客户端权限范围内的所有事件。

连接保活：每 30 秒发送 `:keepalive\n\n` 注释行。

### 2.3 SSE dispatch 流

```
GET /aoscp/dispatch/{dispatchId}/stream
Authorization: Bearer <token>
```

实时推送 dispatch 过程中产生的中间结果。

```
event: message
data: {"seq":10,"role":"assistant","content":"Let me check..."}

event: tool_call
data: {"seq":11,"toolCallId":"tc-1","name":"bash","arguments":"ls -la"}

event: tool_result
data: {"seq":12,"toolCallId":"tc-1","status":"output-available","preview":"total 42\n..."}

event: done
data: {"dispatchId":"d-1","finalMessageSeq":15,"usage":{"promptTokens":1000,"completionTokens":500}}
```

事件类型：

| event         | 含义                                     |
| ------------- | ---------------------------------------- |
| `message`     | assistant 产生文本                       |
| `tool_call`   | assistant 发起 tool call                 |
| `tool_result` | tool 执行结果（可能包含 contentId 引用） |
| `error`       | 执行错误                                 |
| `done`        | dispatch 完成                            |

连接在 `done` 或 `error` 事件后关闭。

### 2.4 健康检查

```
GET /health
```

无需鉴权。返回：

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 3600
}
```

---

## 3. 鉴权

### 3.1 AOS_API_TOKEN

用户在启动 daemon 前设置环境变量：

```bash
export AOS_API_TOKEN=my-secret-token
aos daemon start
```

daemon 启动时读取该值。未设置时拒绝启动，打印错误信息并退出。

### 3.2 Authorization Header

所有 HTTP 请求（除 `/health`）必须携带：

```
Authorization: Bearer <token>
```

### 3.3 验证流程

1. 提取 `Authorization` header
2. 检查格式：`Bearer <token>`
3. 比对 token 与 `AOS_API_TOKEN`
4. 不匹配返回 `401 Unauthorized`
5. 缺少 header 返回 `401 Unauthorized`

### 3.4 Plugin 鉴权

daemon spawn Plugin 子进程时自动注入 `AOS_API_TOKEN` 环境变量。Plugin 通过 stdio JSON-RPC 通信，不经过 HTTP 鉴权。Plugin 若需通过 HTTP 调用 daemon（如通过 SDK HTTP 模式），使用注入的 token。

---

## 4. 请求/响应格式

### 4.1 请求体

```json
{
  "op": "<operation-name>",
  "<param1>": "<value1>",
  "<param2>": "<value2>"
}
```

`op` 为必填，对应 AOSCP 操作名。其余参数因操作而异，参见 [aos-aoscp.md](./aos-aoscp.md)。

### 4.2 成功响应

```json
{
  "ok": true,
  "op": "session.dispatch",
  "revision": 42,
  "data": {
    "sessionId": "sess-abc",
    "dispatchId": "d-123"
  }
}
```

- `revision`：命令操作成功时返回新修订号；查询操作不返回
- `data`：操作结果

### 4.3 错误响应

```json
{
  "ok": false,
  "op": "session.dispatch",
  "error": {
    "code": "session.busy",
    "message": "Session is currently dispatching",
    "details": { "sessionId": "sess-abc", "phase": "dispatched" }
  }
}
```

HTTP 状态码映射：

| 场景                          | HTTP 状态码 |
| ----------------------------- | ----------- |
| 操作成功                      | 200         |
| 参数缺失/格式错误             | 400         |
| 鉴权失败                      | 401         |
| 权限不足                      | 403         |
| 资源不存在                    | 404         |
| 业务错误（busy、conflict 等） | 409         |
| 内部错误                      | 500         |

### 4.4 SSE 消息格式

遵循 [Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html) 标准：

```
event: <event-type>
data: <json-payload>

```

每条消息以两个换行符结尾。`data` 字段为单行 JSON。

---

## 5. 客户端

### 5.1 CLI

CLI 是 HTTP 客户端，面向 LLM 使用。

```bash
# 调用 AOSCP 操作
aos call <op> --payload '<json>'

# 示例
aos call session.dispatch --payload '{"sessionId":"sess-1","message":{"role":"user","content":"hello"}}'
aos call skill.list
aos call content.read --payload '{"contentId":"blob-abc123","limit":20}'

# daemon 管理
aos daemon start [--detach] [--port <port>]
aos daemon stop

# 版本
aos version
```

`aos call` 内部构造 `POST /aoscp` 请求，将 `op` 和 `--payload` 合并为请求体。对于 `session.dispatch`，CLI 自动连接 SSE dispatch 流并等待 `done` 事件，将最终结果输出到 stdout（blocking 模式）。其他操作的响应 JSON 直接输出到 stdout。

CLI 从 `AOS_API_URL`（默认 `http://127.0.0.1:8420`）和 `AOS_API_TOKEN` 环境变量读取连接信息。

### 5.2 Python SDK

```python
from aos_sdk import AosClient

client = AosClient()  # 从环境变量读取 URL 和 token

# 同步调用
result = client.call("session.dispatch", sessionId="sess-1", message={"role": "user", "content": "hello"})

# 事件监听
for event in client.events(scope="session", sessionId="sess-1"):
    print(event.name, event.payload)

# dispatch 流式
for chunk in client.dispatch_stream("sess-1", message={"role": "user", "content": "hello"}):
    print(chunk.type, chunk.data)
```

### 5.3 TypeScript SDK

```typescript
import { AosClient } from '@evop/sdk';

const client = new AosClient(); // 从环境变量读取

// 调用
const result = await client.call('session.dispatch', {
  sessionId: 'sess-1',
  message: { role: 'user', content: 'hello' },
});

// 事件监听
const events = client.events({ scope: 'session', sessionId: 'sess-1' });
for await (const event of events) {
  console.log(event.name, event.payload);
}
```

### 5.4 SDK Transport 模式

SDK 提供两种 transport，同一套 API：

| 模式  | 使用场景             | 底层协议              |
| ----- | -------------------- | --------------------- |
| HTTP  | 独立程序、前端 skill | HTTP + SSE            |
| stdio | Plugin 子进程        | stdin/stdout JSON-RPC |

```python
# HTTP 模式（默认）
client = AosClient()

# stdio 模式（Plugin 内部使用）
client = AosClient(transport="stdio")
```

Plugin SDK 封装自动选择 stdio 模式（见 [aos-plugin.md](./aos-plugin.md)）。

---

## 6. 分布式预留

### 6.1 无状态 daemon

daemon 自身不持有跨请求状态（SC 除外，SC 可随时从 SH rebuild）。多实例部署时，每个请求携带完整上下文（sessionId 等），daemon 从 Store 加载所需数据。

### 6.2 共享存储

多实例场景下，SQLite 替换为共享存储后端（如 PostgreSQL）。所有 daemon 实例读写同一存储。

### 6.3 Load Balancer 兼容

- `/aoscp`：无状态，任意负载均衡策略
- `/aoscp/events`、`/aoscp/dispatch/*/stream`：SSE 长连接，推荐 sticky session 或客户端重连机制

### 6.4 Session 零共享

不同 Session 可在不同 daemon 实例执行。Session lease 机制（见 [aos-lifecycle.md](./aos-lifecycle.md) §8.2）防止同一 Session 被多实例并发 dispatch。
