# OpenClaw 架构调研

> **非规范文档。** 本文是外部项目调研，不定义 AgentOS 行为。文中涉及 AgentOS 的段落仅为作者观察，不构成设计决策。

日期: 2026-03-21
作者: AgentOS 团队（调研文档）

---

## 1. OpenClaw 是什么

OpenClaw 是一个开源的个人 AI 代理框架，由奥地利开发者 Peter Steinberger（PSPDFKit 创始人）于 2025 年 11 月创建。最初名为 Clawdbot，因 Anthropic 商标投诉于 2026 年 1 月 27 日更名 Moltbot，两天后再次更名为 OpenClaw。项目在 2026 年 1 月末爆发式增长，72 小时内获得 60,000 GitHub stars。2026 年 2 月 Steinberger 加入 OpenAI，项目移交开源基金会。

**定位差异**：OpenClaw 不是 Claude Code 的开源复刻。Claude Code 是终端内的 AI 编码代理（单用户、单会话、编码优先）；OpenClaw 是跨平台消息代理（多渠道、多设备、生活自动化优先）。它连接 WhatsApp / Telegram / Slack / Discord / iMessage / Signal 等平台，通过一个持久 Gateway 将消息路由给 LLM，再由 LLM 调用本地工具执行操作。

**技术栈**：TypeScript / Node.js，MIT 许可证。核心依赖包括 Baileys（WhatsApp）、grammY（Telegram）、discord.js（Discord）、Playwright（浏览器自动化）、sqlite-vec（向量搜索）。运行要求极低——1 GB RAM、500 MB 磁盘。

**模型无关**：支持 Anthropic、OpenAI、Google Gemini、DeepSeek、MiniMax、OpenRouter、以及通过 Ollama 运行的本地模型。

---

## 2. 架构总览

OpenClaw 采用 **Hub-and-Spoke** 架构，所有流量经过一个中心 Gateway。

```
 ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
 │  WhatsApp    │  │  Telegram   │  │  Discord     │
 │  Extension   │  │  Extension  │  │  Extension   │
 └──────┬───────┘  └──────┬──────┘  └──────┬───────┘
        │                 │                │
        ▼                 ▼                ▼
 ┌──────────────────────────────────────────────────┐
 │              Gateway (WS :18789)                  │
 │  ┌───────────┐ ┌──────────┐ ┌─────────────────┐ │
 │  │ Session   │ │ Tool     │ │ Skill Loader    │ │
 │  │ Router    │ │ Registry │ │ (3-tier)        │ │
 │  └───────────┘ └──────────┘ └─────────────────┘ │
 │  ┌───────────┐ ┌──────────┐ ┌─────────────────┐ │
 │  │ Agent     │ │ Memory   │ │ MCPorter        │ │
 │  │ Runtime   │ │ (SQLite) │ │ (MCP bridge)    │ │
 │  └───────────┘ └──────────┘ └─────────────────┘ │
 └──────────┬───────────────────────────┬───────────┘
            │                           │
   ┌────────▼────────┐        ┌────────▼────────┐
   │  CLI / Web UI   │        │  Mobile Nodes   │
   │  (WS clients)   │        │  (camera/screen) │
   └─────────────────┘        └─────────────────┘
```

### 2.1 Gateway

Gateway 是唯一的控制平面。绑定单端口 `127.0.0.1:18789`，同时承载：

- **WebSocket RPC**：所有客户端（CLI、Web UI、移动 Node）通过 WS 双向通信。协议版本当前为 v3，消息为 JSON 文本帧，定义三种帧类型：`req`（请求）、`res`（响应）、`event`（服务端推送事件）。
- **HTTP API**：OpenAI 兼容端点、Webhook 接收器、工具调用入口。
- **认证**：Bearer token 或密码。非 loopback 绑定强制要求 token。支持 Ed25519 签名的 challenge-response 设备配对。

所有副作用操作要求 idempotency key，确保重试安全。TypeBox 生成 JSON Schema，`pnpm protocol:gen` 输出协议定义。

### 2.2 Agent Runtime

Agent Runtime（`src/agents/piembeddedrunner.ts`）执行单轮对话循环的四个阶段：

1. **Session Resolution** — 根据消息来源确定目标 session。
2. **Context Assembly** — 加载历史、组装系统提示词、查询记忆、注入 Skill。
3. **Model Invocation** — 流式调用 LLM，监测工具调用。
4. **State Persistence** — 将更新后的 session 持久化到磁盘。

系统提示词由多来源组合：`AGENTS.md`（基线行为）、`SOUL.md`（人格）、`TOOLS.md`（约定）、动态 Skill 注入、自动生成的工具定义、记忆搜索结果。

### 2.3 角色模型

Gateway 定义两种角色：

| 角色         | 用途                                     | Scope 示例                                          |
| ------------ | ---------------------------------------- | --------------------------------------------------- |
| **Operator** | 控制平面客户端（CLI / UI / 自动化）      | `operator.read`, `operator.write`, `operator.admin` |
| **Node**     | 设备能力提供者（摄像头、屏幕录制、位置） | 声明 `caps` + `commands` + `permissions`            |

Node 通过 `node.invoke` 协议方法被 Gateway 远程调用——这使 agent 的工具集可以动态扩展到任何连接设备的硬件能力。

---

## 3. Session 管理

### 3.1 Session 标识

Session 是安全边界。标识符编码了所有权关系：

| 模式     | 格式                                           | 隔离级别     |
| -------- | ---------------------------------------------- | ------------ |
| 主会话   | `agent:<agentId>:main`                         | 完全主机访问 |
| DM 会话  | `agent:<agentId>:<channel>:dm:<identifier>`    | 沙箱隔离     |
| 群组会话 | `agent:<agentId>:<channel>:group:<identifier>` | 沙箱隔离     |

### 3.2 持久化

Session 以 JSONL 文件存储在 `~/.openclaw/agents/<agentId>/sessions/<sessionKey>.jsonl`，采用 append-only 事件日志，支持分支。超出上下文窗口限制时自动 compaction。

### 3.3 记忆系统

长期记忆基于 SQLite + sqlite-vec 向量扩展，存储在 `~/.openclaw/memory/<agentId>.sqlite`。采用混合搜索：向量相似度 + BM25 关键词搜索。记忆文件包括 `MEMORY.md`（结构化事实）和 `memory/YYYY-MM-DD.md`（每日运行日志）。

**与 AgentOS 对比**：AgentOS 通过 AOSCP 操作（`content.read`、`content.search`）统一内容访问，不依赖本地文件物化。OpenClaw 的记忆直接落盘为 Markdown 文件 + SQLite 索引，更适合单机部署但不利于分布式。

---

## 4. Skill 系统

### 4.1 三层加载

| 层        | 路径                  | 优先级 |
| --------- | --------------------- | ------ |
| Bundled   | 随安装包发布          | 最低   |
| Managed   | `~/.openclaw/skills/` | 中     |
| Workspace | `<workspace>/skills/` | 最高   |

同名冲突按优先级覆盖。额外目录可通过 `skills.load.extraDirs` 配置。

### 4.2 SKILL.md 格式

```yaml
---
name: my-skill
description: 做某事的技能
version: 1.0.0
user-invocable: true # 暴露为斜杠命令
disable-model-invocation: false # 是否排除出模型提示词
command-dispatch: tool # 绕过模型直接调用工具
command-tool: my_tool_name
metadata:
  {
    'openclaw':
      {
        'bins': ['ffmpeg'],
        'env': ['MY_API_KEY'],
        'primaryEnv': 'MY_API_KEY',
        'os': ['darwin', 'linux'],
      },
  }
---
## 指令正文（纯英文/自然语言）

告诉 agent 如何使用这个 skill 的 step-by-step 指令。
```

关键设计：`metadata.openclaw` 字段声明运行时门控——要求特定二进制（`bins`）、环境变量（`env`）、操作系统（`os`）。不满足门控条件的 Skill 不会被注入提示词。

### 4.3 运行时 Skill 注入

OpenClaw **不会**把所有 Skill 注入每次提示词。而是在 session 启动时做一次快照，后续每轮根据上下文选择性注入相关 Skill。每个 Skill 的提示词开销约 `97 + name.length + description.length` 字符（约 24+ token）。

### 4.4 ClawHub 生态

ClawHub 是公开的 Skill 注册中心，截至 2026 年 2 月已有 13,700+ 社区贡献的 Skill。但缺乏审核机制——安全分析发现约 12%-20% 的 Skill 包含恶意代码（ClawHavoc 事件，详见 S6）。

**与 AgentOS 对比**：AgentOS 的 SKILL.md 也采用 YAML frontmatter，但 Plugin 通过 stdio JSON-RPC 与 daemon 双向通信，具备真正的代码执行能力。OpenClaw 的 Skill 本质是提示词注入——纯文本指令，不是可执行代码。OpenClaw 的可执行扩展能力由 Plugin 系统（`docs/tools/plugin.md`）和 MCP 集成分别承担。

---

## 5. 工具执行与沙箱

### 5.1 工具注册

工具在 `src/tools/registry.ts` 集中注册。内建工具包括：bash/exec、文件读写编辑、Playwright 浏览器自动化、记忆搜索、agent 间消息。Plugin 通过 `api.registerTool()` 注册自定义工具。

### 5.2 权限策略（多层 Policy）

| 层                    | 含义                      |
| --------------------- | ------------------------- |
| Global                | 全局 allowlist / denylist |
| Per-Agent             | 每个 agent 独立策略       |
| Per-Session (Sandbox) | 非主会话受限              |
| Per-Tool              | 单工具粒度控制            |

deny 优先于 allow。标记为 `elevated` 的工具即使在沙箱中也在主机上执行。

### 5.3 沙箱模型（三档）

| 模式               | 行为                                                |
| ------------------ | --------------------------------------------------- |
| `off`              | 无隔离                                              |
| `non-main`（默认） | 仅主会话在主机执行，DM/群组会话在 Docker 容器中执行 |
| `all`              | 所有工具调用都在容器中执行                          |

容器隔离通过 Docker（或 Podman）实现。工作区可配置为 read-only 挂载或完全不挂载。

**与 AgentOS 对比**：AgentOS v1.0 的 Plugin 子进程天然提供进程级隔离（每个 Plugin 是独立子进程，通过 stdio 通信），但不提供文件系统/网络级隔离。OpenClaw 的容器隔离更彻底但更重。AgentOS 如果未来需要更强隔离，可参考 NanoClaw 的做法——为每个 agent 分配独立 Docker 容器或 MicroVM。

### 5.4 NanoClaw：极端隔离参考

NanoClaw 是 OpenClaw 的轻量替代品，构建在 Claude Agent SDK 之上。每次调用创建临时容器，执行完销毁。Agent 只能看到显式挂载的内容，bash 命令在容器内运行而非主机。NanoClaw 与 Docker Sandboxes 合作，每个 agent 运行在独立 MicroVM 中。

---

## 6. MCP 集成

OpenClaw 通过 **MCPorter**（TypeScript 运行时 + CLI 工具）桥接 MCP 服务器。MCPorter 负责：

1. 将 MCP tool schema 转换为 OpenClaw 的 LLM 可理解格式。
2. 将 agent 的 tool call 路由到正确的 MCP server。
3. 与核心运行时解耦——增减 MCP server 不需要重启 Gateway。

配置文件：`~/.openclaw/workspace/config/mcporter.json`。超过 65% 的活跃 Skill 底层包装了 MCP server——即一个 SKILL.md（告诉 agent 何时/如何用）+ 一个 MCP server（实际处理请求）。

**与 AgentOS 对比**：AgentOS 不直接集成 MCP——Plugin 通过 stdio JSON-RPC 与 daemon 通信，这是自有协议。如需支持 MCP，可作为一个 Plugin 桥接层实现（类似 MCPorter 的角色），而非侵入内核。

---

## 7. 安全事件与教训

### 7.1 CVE-2026-25253（CVSS 8.8）

2026 年 1 月末发现的关键漏洞。Control UI 从 URL query string 接受 `gatewayUrl` 参数并自动建立 WebSocket 连接，将认证 token 泄漏给攻击者控制的端点。一次点击即可实现 RCE。披露时超过 40,000 实例暴露在公网，63% 可被远程利用。

**根因**：Gateway 的 WebSocket 端点缺乏 origin 校验，UI 对外部输入（URL 参数）无条件信任。

### 7.2 ClawHavoc 供应链攻击

ClawHub 无审核机制，数百个恶意 Skill 被上传。攻击手段包括：API key 窃取（Atomic Stealer）、键盘记录注入、持久化记忆篡改（修改 `MEMORY.md` / `SOUL.md`）、加密货币钱包凭证盗窃。

**教训**：

- Skill/Plugin 注册中心必须有审核机制或签名验证。
- 将第三方扩展视为不可信代码，默认最小权限。
- AgentOS 的 Hook 权限校验（owner 级别的注册权限约束）和 Plugin 子进程隔离在安全性上优于 OpenClaw 的"Skill 即提示词注入"模型。

---

## 8. 关键设计决策对比

| 维度             | OpenClaw                                                                | AgentOS (v1.0)                                                                       |
| ---------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **运行形态**     | 持久 Gateway（WS 单端口）                                               | 持久 Daemon（HTTP + SSE）                                                            |
| **客户端协议**   | WebSocket JSON 帧（3 种帧类型）                                         | HTTP `POST /aoscp` + SSE 事件流                                                      |
| **扩展模型**     | Skill（纯文本注入）+ Plugin（`registerTool` API）+ MCP（MCPorter 桥接） | Plugin 子进程（stdio JSON-RPC）+ Hook 系统（Admission/Transform/Event）              |
| **Plugin 语言**  | TypeScript（Gateway 内 `api.registerTool`）                             | 任何语言（实现 stdio JSON-RPC 即可）                                                 |
| **Skill 格式**   | SKILL.md（frontmatter + 自然语言指令）                                  | SKILL.md（frontmatter + Plugin 可执行文件声明）                                      |
| **安全边界**     | Session 级（主会话/DM/群组）；Docker 容器可选                           | Owner 级（system/agent/session）；Plugin 子进程天然进程隔离                          |
| **Hook/事件**    | 简单 hook 对象（`hooks.newSession` 等）；内部耦合                       | 统一 HookEngine（Admission/Transform/Event 三语义）；Plugin 通过 stdio 接收          |
| **记忆**         | SQLite + sqlite-vec 混合搜索 + Markdown 文件                            | AOSCP content 操作（不物化文件）                                                     |
| **控制平面操作** | WS RPC 方法（无统一操作集合）                                           | AOSCP 37 操作，按域分组（System/Skill/Agent/Session/Context/History/Plugin/Content） |
| **多设备**       | Node 概念（移动设备声明硬件能力，Gateway 远程调用）                     | 未规划                                                                               |
| **模型支持**     | 多模型（Anthropic/OpenAI/Gemini/本地）                                  | 模型无关（由 Agent 配置决定）                                                        |

---

## 9. 观察：AgentOS 可借鉴之处

> 以下为调研者的非规范性观察，不构成设计决策。正式采纳需经 spec 评审流程。

### 9.1 Node 概念与能力发现

OpenClaw 的 Node 机制允许移动设备作为能力提供者连接到 Gateway（声明 `caps` / `commands` / `permissions`），由 Gateway 通过 `node.invoke` 远程调用设备能力。这对 AgentOS 未来扩展到多设备场景有参考价值——可以将 Node 建模为一种特殊的 Plugin（通过网络而非 stdio 通信），在 AOSCP 中新增 `node.*` 操作域。

### 9.2 Skill 运行时选择性注入

OpenClaw 不盲目注入所有 Skill 到提示词。Session 启动时做 Skill 快照，每轮根据上下文选择性注入。AgentOS 的 Skill 加载逻辑也应避免全量注入——可在 `session.dispatch` 时由 Transform Hook 裁剪 Skill 注入集合。

### 9.3 Idempotency Key

OpenClaw 的 WS 协议要求所有副作用操作携带 idempotency key。AgentOS 的 AOSCP HTTP 端点也应考虑为写操作引入幂等 key，特别是在不可靠网络或 Plugin 重试场景下。

### 9.4 混合搜索（Vector + BM25）

记忆检索使用 sqlite-vec 向量搜索 + BM25 全文搜索的混合策略。如果 AgentOS 未来需要内建记忆能力，这是成熟且低成本的技术选择。

### 9.5 三档沙箱的灵活性

`off / non-main / all` 三档沙箱模型让运维者按需选择隔离级别。AgentOS 可在 Plugin 层面提供类似选择：子进程直接运行（当前默认）、子进程在容器中运行、子进程在 MicroVM 中运行。

---

## 10. 观察：AgentOS 应保持的差异化

### 10.1 AOSCP 是唯一边界

OpenClaw 的能力分散在 WS RPC 方法、HTTP 端点、Plugin API、Skill 文本注入四处，没有统一的操作集合。AgentOS 的 AOSCP 37 操作集合提供了单一、可审计、可版本化的控制平面——这是核心优势，不应为了灵活性而打破。

### 10.2 Plugin 是子进程，不是进程内对象

OpenClaw 的 Plugin 通过 `api.registerTool()` 在 Gateway 进程内注册工具。一个恶意 Plugin 可以访问整个 Gateway 进程的内存。AgentOS 的 Plugin 子进程模型通过 stdio 通信，天然具备进程隔离——保持这一设计。

### 10.3 Hook 语义三分类

OpenClaw 的 hook 是简单的回调对象，没有 Admission（拦截/拒绝）、Transform（改写）、Event（异步通知）的语义区分。AgentOS 的三语义 Hook 系统在安全控制上更强——Admission Hook 可以拒绝操作，这在 OpenClaw 中没有对应概念。

### 10.4 安全优先于便利

OpenClaw 的 ClawHub 生态证明了"无审核的社区贡献"的危险。AgentOS 的 Skill 分发如果做公开注册中心，必须从 Day 1 就包含签名验证或审核流程。Plugin 的 Hook 注册权限校验（`register` 阶段校验 owner 级别）是正确方向。

---

## 11. 相关开源项目速览

| 项目          | 定位                                 | 技术栈                | 与 AgentOS 关系                    |
| ------------- | ------------------------------------ | --------------------- | ---------------------------------- |
| **OpenClaw**  | 跨平台消息 AI 代理                   | TypeScript / Node.js  | 架构参考（Gateway / Skill / Node） |
| **NanoClaw**  | OpenClaw 轻量替代，容器隔离优先      | 基于 Claude Agent SDK | 隔离模型参考                       |
| **OpenCode**  | 终端 AI 编码代理（Claude Code 替代） | Go                    | 更接近 AgentOS CLI 使用场景        |
| **Aider**     | Git-aware AI 编程助手                | Python                | 编码工具参考                       |
| **Cline**     | 开源 CLI AI 编码助手                 | TypeScript            | 终端交互参考                       |
| **OpenHands** | 自主编码 agent 平台                  | Python                | 多 agent 编排参考                  |
| **Goose**     | Block 出品的 CLI AI agent            | Go                    | DevOps 工作流参考                  |

---

## 参考来源

- [OpenClaw Architecture, Explained](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)
- [OpenClaw DeepWiki](https://deepwiki.com/openclaw/openclaw)
- [OpenClaw Gateway Protocol](https://docs.openclaw.ai/gateway/protocol)
- [OpenClaw Skills 文档](https://docs.openclaw.ai/tools/skills)
- [OpenClaw 安全加固指南 (Nebius)](https://nebius.com/blog/posts/openclaw-security)
- [CVE-2026-25253 分析 (SonicWall)](https://www.sonicwall.com/blog/openclaw-auth-token-theft-leading-to-rce-cve-2026-25253)
- [NanoClaw 容器隔离 (Docker Blog)](https://www.docker.com/blog/run-nanoclaw-in-docker-shell-sandboxes/)
- [OpenCode GitHub](https://github.com/opencode-ai/opencode)
- [OpenClaw vs Claude Code (ZenVanRiel)](https://zenvanriel.com/ai-engineer-blog/openclaw-vs-claude-code-comparison-guide/)
