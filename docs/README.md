# EvoPalantir Documentation

Spec-driven development: 文档是唯一真相，代码忠实反映规范。优先级：**specs**（内核实现依据）> **charter**（总纲与原则）> **skills**（内置 Skill 实现）> **references**（外部调研）。

---

## 宪章

| 文档                               | 说明                                                      |
| ---------------------------------- | --------------------------------------------------------- |
| [aos-charter.md](./aos-charter.md) | AgentOS 宪章 — 是什么、为什么、核心原则。面向初次接触者。 |

## 规范 (specs/)

内核实现的唯一依据。定义内核接口、协议、数据结构、生命周期。面向人类开发者和 AI coding agent。

| 文档                                           | 说明                                                                                          |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [aos-data-model.md](./specs/aos-data-model.md) | 数据结构定义 — ControlBlock / SessionHistory / SessionContext / RuntimeLog 的字段、类型、约束 |
| [aos-aoscp.md](./specs/aos-aoscp.md)           | AOSCP (AOS Control Protocol) — 每个内核操作的签名、参数、返回值、语义                         |
| [aos-hooks.md](./specs/aos-hooks.md)           | Hook 体系 — 44 个扩展点的名称、语义分类、触发时机、注册规则、详细接口契约                     |
| [aos-lifecycle.md](./specs/aos-lifecycle.md)   | 生命周期时序 — 启动、bootstrap、dispatch、恢复、归档                                          |
| [aos-content.md](./specs/aos-content.md)       | 内容存储 — blob 存取、通过 AOSCP 读取、后端可替换                                             |
| [aos-transport.md](./specs/aos-transport.md)   | 传输协议 — daemon 模式、HTTP/SSE、统一端点、鉴权                                              |
| [aos-plugin.md](./specs/aos-plugin.md)         | 插件协议 — stdio JSON-RPC、任何语言、hook 注册、SDK 封装                                      |
| [aos-deployment.md](./specs/aos-deployment.md) | 部署模型 — monorepo 结构、参考部署图、分布式预留                                              |

## 内置 Skill (skills/)

项目提供的参考实现。定义每个内置 Skill 的行为、策略、格式。AOS 内核不提供策略默认值——所有算法由 Skill 提供。

| 文档                                        | 说明                                                                            |
| ------------------------------------------- | ------------------------------------------------------------------------------- |
| [aos.md](./skills/aos.md)                   | `aos` Skill — 纯 skillText，告诉 ReActUnit 如何使用 AOSCP；bootstrap 时强制注入 |
| [aos-context.md](./skills/aos-context.md)   | `aos-context` Skill — 上下文管理参考实现：投影、折叠、压缩、大内容检测          |
| [aos-frontend.md](./skills/aos-frontend.md) | `aos-frontend` Skill — 前端 UI，服务型 Plugin，启动 Next.js Web 应用            |

## 调研参考 (references/)

| 文档                                                                | 说明                                                                                          |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [opencode-plugin-system.md](./references/opencode-plugin-system.md) | OpenCode 插件体系调研（非规范）                                                               |
| [openclaw-architecture.md](./references/openclaw-architecture.md)   | OpenClaw 架构调研（非规范）— 消息型 AI Agent 的 Hub-Spoke 架构、Skill 生态、沙箱模型          |
| [agent-skills-docs.md](./references/agent-skills-docs.md)           | Agent Skills 生态对比（非规范）— 6 种能力声明标准横评（SKILL.md/MCP/A2A/Function Calling 等） |
| [lightllm-provider.md](./references/lightllm-provider.md)           | LLM Provider 抽象层调研（非规范，含设计草案）— LiteLLM/OpenRouter 对比与接口探索              |
