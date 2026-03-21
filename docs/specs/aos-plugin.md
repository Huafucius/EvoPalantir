# AOS Plugin Spec

_插件协议。stdio JSON-RPC、任何语言、hook 注册、SDK 封装。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-hooks.md](./aos-hooks.md) · [aos-lifecycle.md](./aos-lifecycle.md)_

---

## 1. 总则

### 1.1 Plugin 是什么

Plugin 是由 daemon spawn 的子进程。通过 stdin/stdout 的 JSON-RPC 协议与 daemon 通信。任何语言都可以编写 Plugin，只需实现 stdio JSON-RPC 协议。

### 1.2 两个方向

| 方向     | 发起方          | 协议                          | 含义                                      |
| -------- | --------------- | ----------------------------- | ----------------------------------------- |
| AOSCP    | Plugin → Daemon | JSON-RPC request              | Plugin 主动调用内核操作                   |
| AOS Hook | Daemon → Plugin | JSON-RPC request/notification | Daemon 向 Plugin 投递 Hook 调用或事件通知 |

两个方向复用同一 stdio 通道，通过 `id` 字段区分请求/响应归属。

### 1.3 SKILL.md 声明

在 SKILL.md 的 frontmatter 中以顶层 `plugin` 字段声明 Plugin 可执行文件：

```yaml
---
name: my-guard
description: A security guard plugin
plugin: ./plugin.py
---
```

`plugin` 路径相对于 SKILL.md 所在目录。daemon 在 start 操作时 spawn 该文件。

可执行文件要求：

- 必须有执行权限（或由解释器运行，如 `python plugin.py`）
- daemon 根据文件扩展名选择运行方式：`.py` → `python`、`.ts` → `npx tsx`、`.js` → `node`、无扩展名 → 直接执行

---

## 2. stdio JSON-RPC 协议

### 2.1 消息格式

遵循 [JSON-RPC 2.0](https://www.jsonrpc.org/specification)。每条消息占一行，以 `\n` 结尾。

```
{"jsonrpc":"2.0","id":1,"method":"register","params":{...}}\n
```

- stdin：daemon → plugin（hook 调用、事件通知、shutdown）
- stdout：plugin → daemon（register、aoscp 调用、hook 响应）
- stderr：plugin 自由使用（日志输出，daemon 不处理）

### 2.2 Plugin → Daemon 消息

#### 2.2.1 register

Plugin 启动后必须发送的第一条消息。注册要监听的 hooks。

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "register",
  "params": {
    "hooks": ["tool.before", "tool.after", "session.dispatch.after"]
  }
}
```

daemon 响应：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "ok",
    "registered": ["tool.before", "tool.after", "session.dispatch.after"]
  }
}
```

注册失败（越权）：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "permission denied: session-owned plugin cannot register aos.started"
  }
}
```

注册校验规则见 [aos-hooks.md](./aos-hooks.md) §1.4。

#### 2.2.2 aoscp

Plugin 主动调用内核操作。等同于 HTTP `POST /aoscp`，但走 stdio。

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "aoscp",
  "params": {
    "op": "session.history.list",
    "sessionId": "sess-abc"
  }
}
```

daemon 响应：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "ok": true,
    "op": "session.history.list",
    "data": {
      "items": [...]
    }
  }
}
```

### 2.3 Daemon → Plugin 消息

#### 2.3.1 hook（Admission / Transform）

同步调用。daemon 发送请求后等待 Plugin 响应。

**Admission Hook 调用：**

```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "method": "hook",
  "params": {
    "name": "tool.before",
    "input": { "toolCallId": "tc-1", "args": { "command": "rm -rf /" } },
    "output": { "args": { "command": "rm -rf /" } }
  }
}
```

Plugin 响应（允许）：

```json
{ "jsonrpc": "2.0", "id": 100, "result": { "action": "allow" } }
```

Plugin 响应（拒绝）：

```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "result": { "action": "reject", "reason": "dangerous command" }
}
```

Plugin 响应（改写 output）：

```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "result": {
    "action": "allow",
    "output": { "args": { "command": "echo safe" } }
  }
}
```

**Transform Hook 调用：**

```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "method": "hook",
  "params": {
    "name": "tool.after",
    "input": { "toolCallId": "tc-1", "rawResult": "..." },
    "output": { "result": "..." }
  }
}
```

Plugin 响应：

```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": { "output": { "result": "<modified visible result>" } }
}
```

#### 2.3.2 event（Runtime Event）

异步通知。不期望 Plugin 响应（JSON-RPC notification，无 `id` 字段）。

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "name": "session.dispatch.after",
    "payload": {
      "agentId": "agent-1",
      "sessionId": "sess-1",
      "dispatchId": "d-1",
      "appendedCount": 5
    }
  }
}
```

#### 2.3.3 shutdown

优雅关闭通知。Plugin 收到后应清理资源并退出。

```json
{
  "jsonrpc": "2.0",
  "id": 200,
  "method": "shutdown",
  "params": {}
}
```

Plugin 响应：

```json
{ "jsonrpc": "2.0", "id": 200, "result": { "status": "ok" } }
```

Plugin 应在响应后尽快退出。daemon 等待最多 5 秒，超时后 SIGKILL。

---

## 3. Plugin 生命周期

### 3.1 启动流程

| 步骤 | 动作                                                   |
| ---- | ------------------------------------------------------ |
| 1    | daemon 根据 SKILL.md 中 `plugin` 字段路径 spawn 子进程 |
| 2    | 注入环境变量（见 §3.2）                                |
| 3    | 等待 Plugin 发送 `register` 消息（超时 10 秒）         |
| 4    | 校验注册权限（owner 级别校验，见 §5）                  |
| 5    | 状态 = `running`                                       |

超时未收到 `register` 消息：状态 = `error`，记录超时错误。

### 3.2 环境变量注入

daemon spawn Plugin 子进程时自动注入：

| 变量             | 含义                                 | 示例                    |
| ---------------- | ------------------------------------ | ----------------------- |
| `AOS_API_URL`    | daemon HTTP 端点                     | `http://127.0.0.1:8420` |
| `AOS_API_TOKEN`  | 鉴权 token                           | `my-secret-token`       |
| `AOS_AGENT_ID`   | 所属 Agent ID（agent/session-owned） | `agent-abc`             |
| `AOS_SESSION_ID` | 所属 Session ID（session-owned）     | `sess-xyz`              |

system-owned Plugin 不注入 `AOS_AGENT_ID` 和 `AOS_SESSION_ID`。agent-owned Plugin 不注入 `AOS_SESSION_ID`。完整注入矩阵见 [aos-aoscp.md](./aos-aoscp.md) §1.4。

### 3.3 崩溃处理

| 步骤 | 动作                                       |
| ---- | ------------------------------------------ |
| 1    | daemon 检测到子进程意外退出                |
| 2    | 状态 = `error`，记录 exitCode 和 lastError |
| 3    | 注销该 Plugin 注册的所有 Hook              |
| 4    | RE: `plugin.error`                         |
| 5    | 不自动拉起                                 |

手动重启：`aos call skill.stop --payload '{"instanceId":"..."}' && aos call skill.start --payload '{"skillName":"...","ownerType":"...","ownerId":"..."}'`

### 3.4 停止

| 步骤 | 动作                                |
| ---- | ----------------------------------- |
| 1    | daemon 发送 `shutdown` 消息         |
| 2    | 等待 Plugin 响应并退出（超时 5 秒） |
| 3    | 超时后 SIGKILL                      |
| 4    | 注销所有 Hook                       |
| 5    | 状态 = `stopped`                    |

### 3.5 Owner 归档联动

Owner 归档时，daemon 停止所有归属该 owner 的 Plugin。

- Session 归档 → 停止所有 session-owned Plugin
- Agent 归档 → 停止所有 agent-owned 和其下 session-owned Plugin
- AOS 停止 → 停止所有 Plugin

---

## 4. Hook 超时与错误

### 4.1 Hook 调用超时

Admission Hook 和 Transform Hook 是同步调用。daemon 等待 Plugin 响应，超时默认 30 秒。

超时后：

- Admission Hook：视为拒绝，当前操作失败
- Transform Hook：视为未改写，使用原始数据继续

### 4.2 Hook 响应错误

Plugin 返回 JSON-RPC error：

```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "error": { "code": -32603, "message": "internal error" }
}
```

处理方式与超时相同。错误记录到 RuntimeLog。

### 4.3 多 Plugin 串行

同一 hook 有多个 Plugin 注册时，按 owner 层级串行执行：system → agent → session。

前一个 Plugin 的 output 改写结果传递给下一个 Plugin 作为 output 输入。任一 Admission Hook 拒绝，后续不再执行。

---

## 5. Owner 与作用域

### 5.1 三种 Owner

| ownerType | 含义       | 生命周期             |
| --------- | ---------- | -------------------- |
| `system`  | AOS 全局   | 随 daemon 启停       |
| `agent`   | Agent 级   | 随 Agent 创建/归档   |
| `session` | Session 级 | 随 Session 创建/归档 |

### 5.2 Hook 注册权限

Plugin 的 ownerType 决定可注册哪些 hook（见 [aos-hooks.md](./aos-hooks.md) §1.4）。

| Plugin ownerType | 可注册 Admission Hook | 可注册 Transform Hook                   | 可订阅 Runtime Event |
| ---------------- | --------------------- | --------------------------------------- | -------------------- |
| `system`         | 全部                  | 全部                                    | 全部                 |
| `agent`          | agent / session 相关  | 全部                                    | agent / session 级   |
| `session`        | session 相关          | session / tool / compute / context 相关 | session 级           |

越权注册在 `register` 阶段立即失败。

---

## 6. SDK 封装

SDK 封装 stdio JSON-RPC 协议，提供开发者友好的 API。

### 6.1 Python SDK（Plugin 模式）

```python
# plugin.py
from aos_sdk import define_plugin, AosClient

def my_guard(input, output):
    if "rm -rf" in output["args"]["command"]:
        return {"action": "reject", "reason": "dangerous command"}
    return {"action": "allow"}

def my_logger(payload):
    print(f"Dispatch completed: {payload['dispatchId']}")

@define_plugin
def plugin():
    return {
        "tool.before": my_guard,
        "session.dispatch.after": my_logger,
    }
```

`define_plugin` 装饰器自动：

1. 解析返回的 hooks 字典
2. 通过 stdio 发送 `register` 消息
3. 监听 stdin，分发 hook 调用和事件通知到对应函数
4. 处理 `shutdown` 消息，优雅退出

Plugin 内调用内核：

```python
from aos_sdk import AosClient

client = AosClient(transport="stdio")  # Plugin 内自动使用 stdio
result = client.call("session.history.list", sessionId="sess-1")
```

### 6.2 TypeScript SDK（Plugin 模式）

```typescript
// plugin.ts
import { definePlugin, AosClient } from '@evop/sdk';

export default definePlugin({
  hooks: {
    'tool.before': async (input, output) => {
      if (output.args.command.includes('rm -rf')) {
        return { action: 'reject', reason: 'dangerous command' };
      }
      return { action: 'allow' };
    },
    'session.dispatch.after': async (payload) => {
      console.error(`Dispatch completed: ${payload.dispatchId}`);
    },
  },
});
```

Plugin 内调用内核：

```typescript
import { AosClient } from '@evop/sdk';

const client = new AosClient({ transport: 'stdio' });
const result = await client.call('session.history.list', {
  sessionId: 'sess-1',
});
```

### 6.3 其它语言

任何语言只需实现 stdio JSON-RPC 协议即可编写 Plugin。无需使用 SDK。

最小实现要求：

1. 从 stdout 写 JSON-RPC 消息（register、aoscp 调用）
2. 从 stdin 读 JSON-RPC 消息（hook 调用、event 通知、shutdown）
3. 正确处理 `id` 字段的请求/响应匹配

### 6.4 SDK 两种 Transport

同一个 SDK 支持两种 transport 模式：

| 模式    | 使用场景                         | 底层                  |
| ------- | -------------------------------- | --------------------- |
| `http`  | 独立程序、前端 skill、自动化脚本 | HTTP + SSE            |
| `stdio` | Plugin 子进程                    | stdin/stdout JSON-RPC |

API 完全相同，只是底层通信方式不同。`define_plugin` 内部自动使用 stdio 模式。

---

## 7. Plugin 示例

### 7.1 安全守卫

```python
# skills/security-guard/plugin.py
from aos_sdk import define_plugin

BLOCKED_PATTERNS = ["rm -rf /", "DROP TABLE", ":(){ :|:& };:"]

def guard(input, output):
    cmd = output["args"].get("command", "")
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd:
            return {"action": "reject", "reason": f"blocked pattern: {pattern}"}
    return {"action": "allow"}

@define_plugin
def plugin():
    return {"tool.before": guard}
```

### 7.2 执行日志

```python
# skills/audit-log/plugin.py
from aos_sdk import define_plugin
import json, sys

def log_dispatch(payload):
    entry = {
        "event": "dispatch.completed",
        "sessionId": payload["sessionId"],
        "dispatchId": payload["dispatchId"],
        "appendedCount": payload["appendedCount"],
    }
    print(json.dumps(entry), file=sys.stderr)

def log_tool(input, output):
    result = output.get("result", "")
    if len(result) > 1000:
        result = result[:1000] + "...(truncated)"
    return {"output": {"result": result}}

@define_plugin
def plugin():
    return {
        "session.dispatch.after": log_dispatch,
        "tool.after": log_tool,
    }
```
