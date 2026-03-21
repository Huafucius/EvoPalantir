# AI Agent 能力声明机制：生态研究与对比

> **非规范文档。** 本文是行业生态调研，不定义 AgentOS 行为。文中涉及 AgentOS 的段落仅为作者观察，不构成设计决策。

_面向 AgentOS 开发者的技术参考。涵盖行业主流方案的定义格式、发现机制、安全模型，以及对 AgentOS Skill 设计的启示。_

_最后更新：2026-03-21_

---

## 1. 问题域

AI Agent 需要一种标准化方式来：

1. **声明能力** —— 告诉外界（人或其他 Agent）"我能做什么"
2. **发现能力** —— 在运行时找到可用的工具/技能/服务
3. **调用能力** —— 以结构化方式传参、获取结果
4. **控制权限** —— 限制 Agent 对工具的访问范围

当前生态中，至少有 6 种不同层次的方案在解决上述问题。它们并非互斥，而是工作在不同抽象层。本文逐一分析。

---

## 2. 方案概览

| 方案                              | 层次               | 核心思路                                           | 发起方              |
| --------------------------------- | ------------------ | -------------------------------------------------- | ------------------- |
| **Agent Skills** (SKILL.md)       | 知识/指令打包      | Markdown 文件 + YAML 元数据，渐进式加载            | Anthropic (2025.10) |
| **AGENTS.md**                     | 项目级指令         | 纯 Markdown，无结构约束，给 coding agent 的 README | OpenAI (2025.08)    |
| **MCP** (Model Context Protocol)  | 工具/数据连接协议  | JSON-RPC 2.0 协议，Server 暴露 Tools + Resources   | Anthropic (2024.11) |
| **OpenAI Function Calling**       | LLM API 级工具调用 | JSON Schema 定义函数签名，模型输出结构化调用       | OpenAI (2023.06)    |
| **A2A** (Agent2Agent)             | Agent 间通信协议   | Agent Card + 任务委派，跨框架互操作                | Google (2025.04)    |
| **框架级抽象** (LangChain/CrewAI) | 应用框架           | 代码级 Tool 类/装饰器，框架内编排                  | 社区                |

---

## 3. Agent Skills (SKILL.md 开放标准)

### 3.1 解决什么问题

Agent 有推理能力，但缺乏特定领域的**程序性知识**。Agent Skills 将领域知识打包为可发现、可按需加载的指令集，避免将所有知识一次性塞入上下文。

### 3.2 核心设计

**格式**：一个目录，包含 `SKILL.md` 文件（必须）和可选的 `scripts/`、`references/`、`assets/` 子目录。

```
pdf-processing/
├── SKILL.md          # 必须：YAML frontmatter + Markdown 指令
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：参考文档
└── assets/           # 可选：模板、数据
```

**SKILL.md 结构**：

```yaml
---
name: pdf-processing                    # 必填，1-64 字符，小写 + 连字符
description: >                          # 必填，最长 1024 字符
  Extract PDF text, fill forms, merge files.
  Use when handling PDFs.
license: Apache-2.0                     # 可选
compatibility: Requires pdfplumber      # 可选，最长 500 字符
metadata:                               # 可选，任意 KV
  author: example-org
  version: '1.0'
allowed-tools: Bash(git:*) Read         # 可选，实验性
---

# PDF Processing

## When to use this skill
Use when the user needs to work with PDF files...

## How to extract text
1. Use pdfplumber for text extraction...
```

### 3.3 三层渐进式披露（Progressive Disclosure）

这是 Agent Skills 最核心的架构思想：

| 层级                 | 加载内容                 | 加载时机       | Token 开销           |
| -------------------- | ------------------------ | -------------- | -------------------- |
| Tier 1: Catalog      | name + description       | Session 启动时 | ~50-100 tokens/skill |
| Tier 2: Instructions | SKILL.md 全文            | Skill 被激活时 | <5000 tokens（建议） |
| Tier 3: Resources    | scripts/、references/ 等 | 指令中引用时   | 按需                 |

**效果**：安装 20 个 skill，启动时只消耗 ~2000 tokens（20 x 100）。只有当前任务匹配的 skill 才会被完整加载。

### 3.4 发现机制

客户端扫描约定目录：

| 范围   | 路径                          | 用途         |
| ------ | ----------------------------- | ------------ |
| 项目级 | `<project>/.agents/skills/`   | 跨客户端共享 |
| 项目级 | `<project>/.<client>/skills/` | 客户端专属   |
| 用户级 | `~/.agents/skills/`           | 跨客户端共享 |
| 用户级 | `~/.<client>/skills/`         | 客户端专属   |

冲突规则：项目级覆盖用户级。同范围内，先到先得或后到覆盖，需一致。

### 3.5 激活方式

两种：

1. **File-read 激活**：模型直接读取 SKILL.md 文件路径（最简，无需额外工具）
2. **专用工具激活**：注册 `activate_skill` 工具，参数为 skill name（可控性更强，支持权限、分析、包装）

### 3.6 安全模型

- 项目级 skill 来自仓库，可能不受信。建议：**仅在用户标记项目为可信后才加载项目级 skill**
- `allowed-tools` 字段（实验性）预声明 skill 可使用的工具白名单
- 无沙箱隔离、无签名验证机制

### 3.7 采纳状况

2025.12 由 Anthropic 开源为开放标准。已被 Claude Code、OpenAI Codex、Gemini CLI、Cursor、VS Code、GitHub Copilot 等 30+ 客户端支持。GitHub: [github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)

---

## 4. AGENTS.md（给 Coding Agent 的 README）

### 4.1 解决什么问题

开发者需要告诉 AI coding agent 项目的构建步骤、测试命令、代码规范等上下文。README 是写给人的，AGENTS.md 是写给 Agent 的。

### 4.2 核心设计

- **纯 Markdown**，无 frontmatter，无必填字段，无结构约束
- 支持**目录树就近加载**：子目录的 AGENTS.md 覆盖父目录的
- 内容通常包括：构建命令、测试方式、代码风格、架构概述

```markdown
# AGENTS.md

## Build

npm run build

## Test

npm test -- --watch

## Code style

- Use TypeScript strict mode
- Prefer functional components
```

### 4.3 与 Agent Skills 的区别

| 维度     | AGENTS.md                        | Agent Skills             |
| -------- | -------------------------------- | ------------------------ |
| 粒度     | 一个项目一份（或每个子目录一份） | 每个能力一份             |
| 元数据   | 无                               | name, description (必填) |
| 发现     | 目录树向上搜索                   | 约定目录扫描             |
| 按需加载 | 否，启动即全量加载               | 是，三层渐进式           |
| 适用场景 | 项目通用上下文                   | 可复用的领域能力         |

### 4.4 采纳状况

2025.08 由 OpenAI 发布。60,000+ 开源项目采用。2025.12 捐赠给 Linux Foundation 的 Agentic AI Foundation (AAIF)。

---

## 5. MCP（Model Context Protocol）

### 5.1 解决什么问题

LLM 应用需要连接外部数据源和工具。MCP 提供标准化的 Client-Server 协议，让 LLM 无需为每个工具写定制集成。类比：USB-C 之于外设。

### 5.2 核心设计

**协议层**：基于 JSON-RPC 2.0，传输层支持 stdio（本地进程）和 HTTP+SSE（远程服务）。

**三种原语（Primitives）**：

| 原语          | 方向            | 用途                                           |
| ------------- | --------------- | ---------------------------------------------- |
| **Tools**     | Server → Client | 可执行的操作（有副作用），如文件写入、API 调用 |
| **Resources** | Server → Client | 只读数据源，如数据库查询、文件内容             |
| **Prompts**   | Server → Client | 预定义的提示词模板                             |

**Tool 定义格式**（JSON Schema）：

```json
{
  "name": "query_database",
  "title": "Query Database",
  "description": "Run a read-only SQL query against the database",
  "inputSchema": {
    "type": "object",
    "properties": {
      "sql": { "type": "string", "description": "The SQL query" }
    },
    "required": ["sql"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "rows": { "type": "array" }
    }
  },
  "annotations": {
    "audience": ["assistant"],
    "readOnlyHint": true
  }
}
```

### 5.3 发现机制

- **本地**：Client 配置 Server 的启动命令或 URL
- **远程**：2025.11 规范更新引入 OAuth 2.1 认证 + 社区注册表
- Server 通过 `tools/list` 方法动态声明可用工具

### 5.4 安全模型

- Server 运行为独立进程，与 LLM 隔离
- OAuth 2.1 用于远程 Server 认证
- 每个 Tool 可声明 `annotations`（只读提示、受众控制等）
- 无内置沙箱；安全边界取决于 Server 实现

### 5.5 与 Agent Skills 的关系

互补而非竞争：

| 维度     | Agent Skills                  | MCP                       |
| -------- | ----------------------------- | ------------------------- |
| 提供什么 | **指令**（告诉 Agent 怎么做） | **能力**（让 Agent 能做） |
| 格式     | Markdown + YAML               | JSON-RPC 协议             |
| 运行时   | 无（纯文本注入上下文）        | 有（独立 Server 进程）    |
| 典型用法 | "做 PDF 提取时遵循这些步骤"   | "调用 `extract_pdf` 工具" |

一个 Skill 可以引用 MCP Tools；一个 MCP Server 可以在 Tool 描述中包含类似 Skill 的指令。

### 5.6 采纳状况

2024.11 发布。月 SDK 下载量超 9700 万次，10,000+ 活跃 Server。被 ChatGPT、Claude、Cursor、Gemini、VS Code 等支持。2025.12 捐赠给 AAIF。

---

## 6. OpenAI Function Calling

### 6.1 解决什么问题

让 LLM 以结构化方式调用外部函数，而非输出自由文本。解决的是 LLM → 工具的**调用接口**问题。

### 6.2 核心设计

在 API 请求中声明 `tools` 数组，每个工具用 JSON Schema 描述参数：

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get the current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": { "type": "string" },
        "unit": { "type": "string", "enum": ["celsius", "fahrenheit"] }
      },
      "required": ["location"]
    },
    "strict": true
  }
}
```

模型输出 `tool_calls` 而非文本：

```json
{
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"Tokyo\", \"unit\": \"celsius\"}"
      }
    }
  ]
}
```

### 6.3 关键特性

- **Strict 模式**：`strict: true` 保证模型输出**严格匹配** JSON Schema（非尽力而为）
- **Parallel 调用**：模型可一次输出多个 tool_calls
- **无状态**：每次 API 调用需重新传入完整 tools 定义

### 6.4 与其他方案的关系

Function Calling 是**底层调用机制**。MCP Server 的 Tool 最终通过 Function Calling 格式传给模型；Agent Skills 的 `allowed-tools` 引用的也是这些工具名。

### 6.5 API 演进

OpenAI 正从 Chat Completions API 迁移至 Responses API（agent-native），Assistants API 将在 2026 年中下线。Function Calling 格式保持兼容。

---

## 7. A2A（Agent2Agent Protocol）

### 7.1 解决什么问题

不同框架、不同厂商构建的 Agent 需要互相发现和委派任务。MCP 解决 Agent → Tool 连接；A2A 解决 **Agent → Agent** 通信。

### 7.2 核心设计

**Agent Card**（能力声明）：每个 Agent 在 `/.well-known/agent-card.json` 发布元数据：

```json
{
  "id": "agent-purchase-001",
  "name": "Purchasing Agent",
  "description": "Handles procurement workflows",
  "version": "1.0",
  "provider": { "organization": "Example Corp" },
  "skills": [
    {
      "id": "purchase-order",
      "name": "Create Purchase Order",
      "description": "Create and submit a purchase order"
    }
  ],
  "interfaces": [
    { "protocol": "a2a/http", "url": "https://agent.example.com/a2a" }
  ],
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "securitySchemes": { "oauth2": { "type": "oauth2" } }
}
```

**交互模型**：Client Agent 发现 Remote Agent Card → 创建 Task → Remote Agent 执行 → 返回 Artifact。

### 7.3 与 MCP 的分工

| 维度     | MCP               | A2A                      |
| -------- | ----------------- | ------------------------ |
| 连接对象 | Agent ↔ Tool/Data | Agent ↔ Agent            |
| 透明度   | Client 控制执行流 | Remote Agent 自主执行    |
| 典型场景 | 读数据库、调 API  | 委派子任务给另一个 Agent |

### 7.4 采纳状况

2025.04 由 Google 发布，50+ 技术合作伙伴。当前版本 0.3，已支持 gRPC 传输和签名验证。

---

## 8. 框架级工具抽象（LangChain / CrewAI / AutoGPT）

### 8.1 共同模式

所有主流 Agent 框架都有 "Tool" 概念：

```python
# LangChain @tool 装饰器
@tool
def search_web(query: str) -> str:
    """Search the web for information about a topic."""
    return requests.get(f"https://api.search.com?q={query}").text

# LangChain BaseTool 类
class DatabaseTool(BaseTool):
    name = "query_db"
    description = "Query the production database"
    args_schema = QueryInput  # Pydantic model

    def _run(self, sql: str) -> str:
        return db.execute(sql)
```

**共同字段**：`name`（必填）、`description`（推荐）、`args_schema`（参数 Schema，通常由类型标注自动推断）。

### 8.2 各框架差异

| 框架                    | 工具定义方式                   | 编排模型               | 特色                       |
| ----------------------- | ------------------------------ | ---------------------- | -------------------------- |
| **LangChain/LangGraph** | `@tool` 装饰器 / `BaseTool` 类 | DAG / 循环图           | 生态最广，底层原语最灵活   |
| **CrewAI**              | `@tool` 装饰器                 | 角色分工 (Crew + Flow) | 高层抽象，按"角色"分配工具 |
| **AutoGPT**             | 插件/Agent Store               | 自主循环               | 有 Agent Marketplace 概念  |

### 8.3 局限性

- **不可移植**：LangChain 的 Tool 无法直接用于 CrewAI，反之亦然
- **无标准发现**：工具在代码中硬编码注册，无运行时动态发现
- **无跨进程隔离**：工具与 Agent 在同一进程，安全边界弱

MCP 正是为了解决这些局限而设计的跨框架标准。

---

## 9. 行业治理：Agentic AI Foundation (AAIF)

2025.12，Anthropic、OpenAI、Block 联合在 Linux Foundation 下成立 **AAIF**，整合三个开放标准：

| 项目      | 原发起方  | 定位                        |
| --------- | --------- | --------------------------- |
| MCP       | Anthropic | Agent ↔ Tool/Data 连接协议  |
| AGENTS.md | OpenAI    | 项目级 Agent 指令           |
| Goose     | Block     | 开源 Agent 框架（基于 MCP） |

Agent Skills 尚未正式加入 AAIF，但已被 AAIF 成员广泛采纳。

NIST 于 2026.02 启动 **AI Agent Standards Initiative**，聚焦安全、互操作、审计三个领域，预计 2027 年形成监管指引。

---

## 10. 全景对比表

| 维度               | Agent Skills                                                       | AGENTS.md               | MCP                                                              | Function Calling                      | A2A                                             | 框架 Tool                      |
| ------------------ | ------------------------------------------------------------------ | ----------------------- | ---------------------------------------------------------------- | ------------------------------------- | ----------------------------------------------- | ------------------------------ |
| **抽象层**         | 知识打包                                                           | 项目指令                | 工具协议                                                         | LLM API                               | Agent 间协议                                    | 应用框架                       |
| **定义格式**       | YAML + Markdown                                                    | 纯 Markdown             | JSON Schema (JSON-RPC)                                           | JSON Schema                           | Agent Card (JSON)                               | 代码 (Python/TS)               |
| **元数据**         | name, description, license, compatibility, metadata, allowed-tools | 无结构化元数据          | name, title, description, inputSchema, outputSchema, annotations | name, description, parameters, strict | id, name, skills, capabilities, securitySchemes | name, description, args_schema |
| **发现机制**       | 约定目录扫描                                                       | 目录树向上搜索          | Client 配置 + 注册表                                             | API 请求内联                          | well-known URL                                  | 代码注册                       |
| **按需加载**       | 三层渐进式                                                         | 无（全量加载）          | tools/list 动态列举                                              | 每次请求全量                          | Agent Card 预获取                               | 无                             |
| **运行时隔离**     | 无（纯文本）                                                       | 无                      | Server 独立进程                                                  | 由调用方实现                          | 独立 Agent                                      | 同进程                         |
| **安全模型**       | 信任标记 + allowed-tools                                           | 无                      | OAuth 2.1 + annotations                                          | 无内置                                | OAuth 2.0 + 签名 Card                           | 无内置                         |
| **跨客户端互操作** | 高（30+ 客户端）                                                   | 高（60k+ 项目）         | 高（9700 万月下载）                                              | 中（多厂商兼容格式）                  | 中（50+ 合作方）                                | 低（框架锁定）                 |
| **治理**           | 开放标准 (Anthropic)                                               | AAIF (Linux Foundation) | AAIF (Linux Foundation)                                          | OpenAI 私有 API                       | Google 开源                                     | 各框架社区                     |

---

## 11. 观察：对 AgentOS Skill 设计的启示

> 以下为调研者的非规范性观察，不构成设计决策。正式采纳需经 spec 评审流程。

AgentOS 已有自己的 Skill 体系（SKILL.md + Plugin + Hook），以下是从行业对比中提取的设计要点：

### 11.1 AgentOS 已经做对的

| 设计决策                                      | 行业验证                                              |
| --------------------------------------------- | ----------------------------------------------------- |
| **SKILL.md 作为声明文件**                     | 与 Agent Skills 开放标准完全一致，天然兼容            |
| **YAML frontmatter + Markdown body**          | 同上，行业事实标准                                    |
| **Skill = 指令 + Plugin（可选）**             | 合并了 Agent Skills（指令层）和 MCP（工具层）的关注点 |
| **三层结构：Skill 发现 → 加载 → Plugin 启动** | 对齐 Agent Skills 的 progressive disclosure           |
| **Plugin 通过 stdio JSON-RPC 隔离**           | 与 MCP Server 的本地传输模式一致，安全边界清晰        |
| **Hook 机制（Admission/Transform/Event）**    | 超越了当前所有开放标准，提供了控制面拦截能力          |

### 11.2 值得考虑的增强

| 方向                                | 行业实践                                   | AgentOS 可行动                                                                                 |
| ----------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| **兼容 `.agents/skills/` 约定路径** | Agent Skills 标准的跨客户端发现路径        | SkillManager 扫描时除 `skillRoot` 外，额外扫描 `.agents/skills/`，实现双向兼容                 |
| **Skill 签名与信任**                | A2A Agent Card 支持签名验证；NIST 要求审计 | 为 SkillManifest 增加可选的 `signature` 字段，或通过 Admission Hook 实现信任策略               |
| **MCP Server 作为 Plugin 的一种**   | MCP 已成为事实标准连接协议                 | Plugin 的 stdio JSON-RPC 已接近 MCP，考虑兼容 MCP 协议使 AgentOS 能直接挂载 MCP Server         |
| **Agent Card 式对外发布**           | A2A 通过 well-known URL 暴露能力           | AgentOS daemon 可在 HTTP 端点暴露 Agent Card（或 skill catalog），支持被其他 Agent 发现        |
| **allowed-tools 语义**              | Agent Skills 标准的实验性字段              | AgentOS 已有 Hook 拦截能力，比 allowed-tools 更强大；可在 SkillManifest 中保留此字段以兼容标准 |

### 11.3 不需要做的

- **不需要实现 AGENTS.md**：AGENTS.md 是项目级指令，粒度太粗。AgentOS 的 `aos` 内建 skill 已覆盖此需求
- **不需要替换 Plugin 为 MCP**：AgentOS 的 Plugin 通过 Hook 获得了 MCP 不具备的控制面能力（Admission 拦截、Transform 变换）。保持自有协议，提供 MCP 兼容层即可
- **不需要实现 A2A**：A2A 解决的是多 Agent 互操作，AgentOS 当前是单机 daemon 架构。可在分布式预留中规划

---

## 12. 参考链接

- Agent Skills 官方站：[agentskills.io](https://agentskills.io/home)
- Agent Skills GitHub：[github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)
- AGENTS.md 官方站：[agents.md](https://agents.md/)
- MCP 规范：[modelcontextprotocol.io/specification](https://modelcontextprotocol.io/specification/2025-11-25)
- OpenAI Function Calling：[platform.openai.com/docs/guides/function-calling](https://platform.openai.com/docs/guides/function-calling)
- A2A 协议规范：[a2a-protocol.org](https://a2a-protocol.org/latest/specification/)
- AAIF 官方站：[aaif.io](https://aaif.io/)
- NIST AI Agent Standards Initiative：[nist.gov/caisi/ai-agent-standards-initiative](https://www.nist.gov/caisi/ai-agent-standards-initiative)
- LangChain Tools 文档：[docs.langchain.com/oss/python/langchain/tools](https://docs.langchain.com/oss/python/langchain/tools)
