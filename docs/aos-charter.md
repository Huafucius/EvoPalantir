# Agent OS Charter

---

## 第一章 总述

### 1.1 核心命题

一个语言模型能推理，但不能行动。给它一个 bash，它可以执行命令；给它一个循环，它可以反复推理、行动直到任务完成。这就是 ReActUnit——AOS 世界中最基本的认知单元。

ReActUnit 有能力但没有记忆。它不知道自己做过什么、说过什么。给它一个 Session，它的历史就有了持久化的依据——正如程序有了磁盘；它的上下文就有了可重建的工作内存——正如进程有了内存。

Session 有记忆但没有身份。给它一个 Agent，它就有了名字、配置与责任边界——如同操作系统中的用户。Agent 是权责承担的基本单位，跨 Session 持续存在。

系统需要可扩展的能力。Skill 是统一能力抽象：一份说明书可以被读入上下文（上下文面），一个插件可以被启动并介入系统生命周期（插件面）。

治理以上一切的，是 Agent OS（以下简称 AOS）——面向认知推进的认知控制内核。AOS 不做推理，不执行命令，不直接参与认知。它治理认知过程的组织、持续化、注入、恢复与控制。正如传统操作系统治理 CPU、内存与 I/O 而非亲自执行电路级运算，AOS 治理 ReActUnit、Session、Agent 与 Skill。

### 1.2 全局原则

**AOS 是唯一的治理主体。** 凡系统控制，皆经 AOSCP（AOS Control Protocol）完成；持久化真相的唯一写入者是控制面。

**AOSCP 是内核态与用户态的唯一合法边界。** ReActUnit（通过 bash CLI）、Plugin（通过 stdio JSON-RPC）、前端（通过 SDK / HTTP）访问内核功能的唯一合法路径是 AOSCP。

**AOSCP 区分命令与查询。** 命令改变系统状态，可经过 Admission Hook 拦截，产生 RuntimeLog 条目。查询读取系统状态，不经过 Admission Hook，轻量可缓存。

**Skill 是唯一能力抽象。** 一切可被 Agent 借来推进事务的能力，都以 Skill 的形式存在。前端界面、Agent 间通信、外部工具集成——在 AOS 中都是 Skill，没有特殊公民。

**Bash 是 ReActUnit 的唯一正式世界接口。** AOS 不为 ReActUnit 提供其他 native tool。这把世界的复杂性留给现有 CLI 生态，把系统控制的复杂性收回到 AOSCP 本身。

**Session 是单写者 durable actor。** 任一时刻最多有一个 dispatch 持有其 lease。

**Session 之间零共享可变状态。** 跨 Session 的协调通过 Agent 配置与 AOSCP 操作完成。

**Plugin 之间不直接通信。** 能力的组合发生在 ReActUnit 的 bash 编排和 AOSCP 的正式操作中。AOS 不内置 Agent 间通信——它提供通信可以依赖的原语，通信本身是 Skill 的工作。

**Daemon 是标准运行形态。** AOS 以持久守护进程运行，通过 HTTP/SSE 对外提供服务。CLI、Python SDK、TypeScript SDK 都是对等的 HTTP 客户端。

**控制面响应 JSON-only。** 控制面是机器契约。

**所有持久化存储可插拔。** 默认实现基于 SQLite，可替换为 PostgreSQL、S3 或其他后端。

### 1.3 模块化架构

AOS 内核由一个薄协调器和多个独立模块组成。每个模块高内聚、职责单一，模块间通过抽象接口通信。不采用严格分层——模块之间是协作关系，不是上下级关系。

**协调器 (AOSRuntime)** 是路由和编排中心。它知道流程的顺序，但不知道每个模块的内部实现。它自己几乎没有状态。

**领域模块** 按 AOSCP 操作域划分，每个域拥有自己的状态和逻辑：

- **SessionManager** — Session 的全生命周期：创建、lease、dispatch、compaction、归档
- **AgentManager** — Agent 的 CRUD、归档、配置继承
- **SkillManager** — Skill 发现、索引、加载、Plugin 生命周期
- **ContentManager** — 大内容的 blob 存取与 AOSCP 访问

**基础设施模块** 提供横切能力：

- **HookEngine** — 三类 Hook 的注册与分派（统一注册，内核按名字分类语义）
- **Store** — 持久化接口（按关注点拆分：ControlBlockStore、HistoryStore、ContentStore 等），后端可替换
- **ReActUnit** — 完整的 ReAct 循环（LLM 调用、tool 执行、重试、超时）
- **Transport** — HTTP/SSE server（FastAPI），daemon 生命周期

每个模块可以独立测试、独立替换。未来分布式时，SessionManager 可以变成独立服务，接口不变。

### 1.4 系统总览

| 维度     | 内容                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------ |
| 本体对象 | AOS、Agent、Session、Skill、ReActUnit                                                                              |
| 数据层   | SessionHistory、SessionContext、RuntimeLog                                                                         |
| 内核函数 | AOSCP 操作（命令 + 查询），完整清单见 [aos-aoscp.md](./specs/aos-aoscp.md)                                         |
| 扩展点   | Admission Hook、Transform Hook、Runtime Event，完整清单见 [aos-hooks.md](./specs/aos-hooks.md)                     |
| 存储     | ControlBlock（AOS 级 AOSCB、Agent 级 ACB、Session 级 SCB）、SessionHistory、RuntimeLog、ContentStore（后端可替换） |

---

## 第二章 世界模型

### 2.1 五个本体对象

**AOS** 是系统级治理内核，是整个体系的主权者。以 daemon 进程运行，是所有其他对象的运行时宿主。

**Agent** 是长期存在的认知主体，承载身份、责任边界与默认配置。对标操作系统中的用户。

**Session** 是具体事务单元，是认知推进的数据承载者。负责消息持久化与上下文调度，不负责执行。Session 是单写者 durable actor：通过 lease 保证任一时刻最多有一个活跃的 dispatch。

**Skill** 是统一能力抽象。一份说明书可被读入上下文（上下文面），一个插件可被启动并介入系统生命周期（插件面）。两面独立，可单独使用。

**ReActUnit** 是推理-行动单元——完整的 ReAct agent。接收 SessionContext，执行推理-行动完整循环，将结果写回 SessionHistory。由 `session.dispatch` 创建，循环结束后销毁。

### 2.2 对象关系

```
AOS (daemon)
 ├── 治理 → Agent
 │            └── 拥有 → Session
 │                         └── dispatch 创建 → ReActUnit (临时)
 │                                              读 SC / 写 SH
 └── 治理 → Skill
              ├── load → skillText 进入 SessionContext
              └── start → Plugin 子进程 (stdio JSON-RPC)
                           ├── 注册 Hook
                           ├── 监听 Event
                           └── 调用 AOSCP
```

### 2.3 三类状态

**会话可见状态 (SessionHistory)：** 这次事务中「人和模型共同看到并承认发生过的事实」。Append-only，持久化。大内容按引用存储在 ContentStore 中。

**运行时工作状态 (SessionContext)：** 下一次发送给 ReActUnit 的消息集合，从 SessionHistory 物化出的运行时 cache。关机即消失，随时可从 SessionHistory 重建。被折叠的内容以占位符而非空白的形式出现。

**系统执行状态 (RuntimeLog)：** AOS 内核做了什么的操作记录，全局 append-only 系统审计日志。仅命令路径产生条目。

---

## 第三章 ReActUnit

### 3.1 定义

ReActUnit 是完整的 ReAct agent。给 LLM 一个 bash，用 ReAct 循环武装起来，就是 ReActUnit。

它由 `session.dispatch` 创建，接收 SessionContext，执行推理-行动完整循环（LLM 调用 → 判断 tool_call → 执行 bash → 写结果 → 继续循环），直到终止条件满足后销毁。包含重试、超时和 max_turns 控制。

不是持久对象，不跨 Session 共享，不拥有独立生命周期状态。

### 3.2 Bash 唯一正式工具

AOS 不为 ReActUnit 提供除 bash 以外的其他 native tool。ReActUnit 通过 bash 调用 AOSCP CLI 访问内核功能（`aos call <op> --payload '{}'`）。交互完全经由正式的内核态/用户态边界。

AOSCP 响应 JSON-only，使 ReActUnit 可以用 jq 提取字段、用管道传给下一个命令、用条件分支做自动化决策。

### 3.3 循环中的 Hook 触发

ReActUnit 在循环的每个关键步骤触发 Hook，使内核和 Plugin 得以介入控制流。具体触发点见 [aos-hooks.md](./specs/aos-hooks.md) 和 [aos-lifecycle.md](./specs/aos-lifecycle.md)。

### 3.4 与 SessionContext 的关系

ReActUnit 直接消费 SessionContext。每条 ContextMessage 由 `wire`（LLM 兼容的 chat message）和 `aos`（provenance sidecar）两部分组成。ReActUnit 消费 `wire`，发给 LLM 之前剥离 `aos`。

---

## 第四章 Session

### 4.1 定义

Session 是具体事务单元。一次任务、一条工作线程、一笔业务处理，都属于一个 Session。Session 是 AOS 中事务的数据承载者：消息持久化、上下文投影、fold/unfold、compaction 与中断恢复，都属于 Session 的责任域。

**Session 不驱动执行。** 执行由 `session.dispatch` 触发，由临时创建的 ReActUnit 完成。Session 是磁盘和内存，不是 CPU。

**Session 是单写者 durable actor。** 通过 lease 机制保证任一时刻最多有一个 dispatch 持有 session 的写权限。lease 有 TTL，到期自动释放。

同一 Agent 下可以并发存在多个 Session，各自独立。

### 4.2 SessionHistory 与 SessionContext

SessionHistory 是 Session 的持久化历史——append-only，服务于人类回看和上下文重建。

SessionContext 是从 SessionHistory 物化出的运行时上下文。不持久化，关机即消失，随时可从 SessionHistory 重建。

SessionContext 之于 SessionHistory，正如内存之于磁盘：磁盘保存全量数据，内存保存当前工作集。fold/unfold 控制哪些页面在内存中，compact 回收已用空间。

大内容按引用存储在 ContentStore 中。AI 通过 AOSCP 操作（`content.read`、`content.search`）按需读取——不依赖本地文件系统，保持「AOSCP 是唯一边界」的一致性。

精确的物化规则见 [aos-hooks.md](./specs/aos-hooks.md) §3.5（Hook 接口契约）和 [aos-context Skill](./skills/aos-context.md)（参考实现）。

### 4.3 Fold / Unfold

Fold 是 AOS 的上下文换入换出机制。核心语义：**折叠不是跳过，而是降级为占位符。**

AI 从占位符中获得：存在性、规模感（字符数、行数）、预览文本、AOSCP 读取命令、unfold 命令。类比：操作系统的页表项——标记「已分配但不在内存」，而非删除。

三种触发机制：

- **Auto-fold：** bash 输出超过阈值时自动触发
- **AI 主动 fold：** AI 主动释放不再需要的工作内存
- **AI 主动 unfold：** AI 按需恢复完整内容

### 4.4 Compaction

Compaction 在 SH 追加一对摘要边界（CompactionMarker + CompactionSummary），之后 rebuild 从此处开始。Compact 只追加「摘要边界」，不删除既有历史。类比：Fold 是换页到 swap，Compact 是内存压缩 / GC。

### 4.5 上下文调度原语

- **fold / unfold：** 调整某条消息/part 在 SC 中的投影方式
- **compact：** 追加摘要边界，之后 rebuild 从此处开始
- **rebuild：** 从 SH 重新计算完整 SC
- **dispatch：** 追加用户消息、获取 lease、创建 ReActUnit——唯一触发执行的 AOSCP 命令

### 4.6 中断与恢复

中断事实首先写入 SH，然后在下一个检查点终止推进。首先是事实，其次才是运行时动作。

恢复只依赖三种静态真相：AOSCB、ACB/SCB、SessionHistory。SC 恢复 = 执行 rebuild。

---

## 第五章 Agent

### 5.1 定义

Agent 是长期存在的认知主体。持有身份、责任边界与默认配置，在多次事务之间保持稳定。同一 Agent 可以拥有多个 Session。

### 5.2 主体边界与配置继承

Agent 持有身份、责任边界与默认配置。Skill 默认配置按 system → agent → session 三层顺序覆盖。各级控制块预留 `permissions` 字段，正式授权策略语法在 v1 中未固定。

### 5.3 激活与归档

Agent 归档时，其所有 Plugin 随之停止。控制块与历史 SessionHistory 继续保留。

### 5.4 Agent 间交互

AOS 不内置 Agent 间通信机制。AOS 提供 AOSCP 操作作为通信可以依赖的原语（如 `session.dispatch`、`session.append`、Runtime Event），Agent 间的消息传递、协调、协商由专门的通信类 Skill 实现。

如同 UNIX 不内置邮件系统，但提供了 pipe、socket、signal——邮件系统是用户空间的程序。

---

## 第六章 Skill

### 6.1 定义

Skill 是统一能力抽象。领域知识、工作指南、可按需读入的说明书、带有运行入口的插件扩展——在 AOS 中都以 Skill 的形式存在。

一切可被 Agent 借来推进事务的能力，都表达为 Skill。包括人类交互的前端界面——前端不是 AOS 的内置功能，而是一个 Skill。

### 6.2 两个面

**上下文面 (skillText)：** SKILL.md 的正文，写给 ReActUnit 看的说明书。通过 `skill.load` 进入 SessionContext。

**插件面 (Plugin)：** SKILL.md frontmatter 中以 `plugin` 字段声明的可执行入口。通过 `skill.start` 产生 Plugin 子进程，可以注册 Hook、监听 Event、调用 AOSCP。

两个面相互独立，load 与 start 互不依赖。一个 Skill 可以只有上下文面（纯说明书），也可以只有插件面（纯后台服务），也可以兼有。

### 6.3 发现与加载

Skill 从一个 skillRoot 目录发现。Daemon 启动时扫描 skillRoot 下所有 SKILL.md，建立索引。file watcher 监听变化，自动热重载。

安装 = 把目录放进 skillRoot。更新 = 覆盖目录内容。卸载 = 删目录。AOS 不管 Skill 怎么到达 skillRoot——和 `/usr/local/bin` 一样。

所有 Skill 平等，不区分内建和外部。`aos` 是宿主内建 Skill，但它只是 skillRoot 下的一个普通目录。

发现策略 (SkillDiscoveryStrategy) 是可替换接口。默认文件系统扫描，未来可替换为云端存储、Git 仓库等。

### 6.4 discover / load / start

**discover：** 从已索引的 Skill 中选出当前可见的 SkillCatalog。

**load：** 把 skillText 写入 SH 并投影到 SC。bootstrap 和 compaction 后自动发生；ReActUnit 通过 bash 调用 `aos call skill.load` 显式触发。

**start：** 启动插件面，daemon spawn Plugin 子进程。Plugin 通过 stdio JSON-RPC 注册 Hook、监听 Event、调用 AOSCP。

---

## 第七章 Plugin

### 7.1 定义

Plugin 是由 daemon spawn 的子进程。通过 stdin/stdout JSON-RPC 双向通信，任何语言都可以编写。

Plugin 与 daemon 之间有两个方向的通信，复用同一条 stdio 通道：

- **AOSCP 方向（Plugin → Daemon）：** Plugin 主动调内核——「给我创建一个 session」
- **AOS Hook 方向（Daemon → Plugin）：** 内核主动调 Plugin——「有人要执行 rm -rf，你要拦吗？」

### 7.2 Hook 与生命周期

Plugin 启动时注册自己关心的 Hook 名称。内核根据名字自动判断语义分类（Admission / Transform / Event），开发者不需要声明类型。三类 Hook 的语义、完整扩展点清单和注册规则见 [aos-hooks.md](./specs/aos-hooks.md)。

Plugin 的启动、崩溃处理、停止和 Owner 归档联动见 [aos-lifecycle.md](./specs/aos-lifecycle.md) §6 和 [aos-plugin.md](./specs/aos-plugin.md) §3。

### 7.3 Plugin vs ReActUnit

ReActUnit 是基于概率的意图驱动行动——LLM 推理并决定下一步做什么。Plugin 是基于规则的条件触发与约束执行——代码逻辑决定响应。两者在决策性质上根本不同：ReActUnit 消费 SessionContext，Plugin 介入系统生命周期。

---

## 第八章 AOS 内核

### 8.1 Daemon

AOS 以持久守护进程运行，绑定 HTTP 端口，通过统一端点接受 AOSCP 请求，通过 SSE 推送 Runtime Event。

启动后，daemon：扫描 skillRoot → 启动 system 级 Plugin → 开始接受请求。支持前台运行和后台运行（`--detach`）。file watcher 监听 skillRoot 变化，自动热重载。

CLI、Python SDK、TypeScript SDK 都是 daemon 的 HTTP 客户端。三者对等，没有特权客户端。

### 8.2 AOSCP

AOSCP 是 AOS 的正式控制接口，内核态/用户态的唯一合法边界。

三种访问方式：

- **CLI** — `aos call <op> --payload '{}'`，给 LLM 用
- **SDK (HTTP)** — Python / TypeScript，给独立程序用
- **SDK (stdio)** — Python / TypeScript，给 Plugin 用

操作同一套语义，响应 JSON-only。

AOSCP 操作按领域分组：System、Skill、Agent、Session、Session Context、Session History、Plugin、Content。每个操作是命令或查询。完整操作表见 [aos-aoscp.md](./specs/aos-aoscp.md)。

### 8.3 RuntimeLog

RuntimeLog 是 AOS 的全局 append-only 系统日志。只记录命令路径的执行（查询不产生条目）。面向离线分析与审计，不通过 AOSCP 实时查询。

### 8.4 鉴权

daemon 通过 `AOS_API_TOKEN` 环境变量获取 token。所有请求必须携带 token。未设置 token 时 daemon 拒绝启动。

daemon 启动 Plugin 子进程时，自动注入 AOS_API_URL 和 AOS_API_TOKEN，Plugin 不需要操心连接细节。

---

## 第九章 系统边界

### 9.1 审计边界

SessionHistory 回答「会话层面发生了什么」，通过 AOSCP 查询实时可达。RuntimeLog 回答「系统层面做了什么（命令路径）」，面向离线分析，不暴露在 AOSCP 用户态。

### 9.2 内核态/用户态边界

```
用户态: ReActUnit (bash → CLI) / Plugin (stdio JSON-RPC) / 前端 (SDK → HTTP)
        ──────────────────── AOSCP ────────────────────
内核态: AOSRuntime → Managers → Store
                  ↕ HookEngine
```

跨越边界的每次访问都经过 AOSCP。内核模块之间可以直接调用，不经过 AOSCP 的 JSON 序列化开销。

### 9.3 组合边界

AOS 不提供 Plugin 之间的直接通信。能力的组合发生在：ReActUnit 在 bash 中的编排；AOSCP 的统一操作。

AOS 的边界：shell、数据库、文件系统、cron、容器编排、通用进程管理，以及 HTTP、stdio、消息总线等 transport，都可以与 AOS 协作，但不属于 AOS 的本体。

### 9.4 分布式预留

当前实现是单机 daemon + SQLite。但架构为分布式未来预留了约束：

1. **AOSCP 操作无隐含状态** — 每个请求携带完整上下文，可路由到任意节点
2. **Session 之间零共享可变状态** — 不同 Session 可以在不同节点上执行
3. **所有持久化存储可插拔** — SH、RL、ContentStore 均为接口，可替换为分布式后端
4. **Session lease 保证跨节点单写者** — Lease Manager 将来可基于分布式锁实现
5. **EventBus 可扩展为跨节点** — 当前内存 bus，接口允许替换为消息队列

---

_Agent OS Charter — AOS 是一个治理认知主体、会话运行历史、skill 上下文注入与 plugin 运行实例的认知控制内核。模块化架构（薄协调器 + 独立 Manager）构成其内部秩序。三种 Hook 语义（Admission / Transform / Event）以扁平注册方式提供扩展能力。AOSCP 作为内核态/用户态的唯一合法边界，提供按领域分组的内核函数。Daemon 是标准运行形态，CLI/SDK 是对等的 HTTP 客户端。Plugin 是任意语言的子进程，通过 stdio JSON-RPC 双向通信。session.dispatch 以异步内核语义触发 ReAct 循环，Session 通过 lease 保证单写者。_
