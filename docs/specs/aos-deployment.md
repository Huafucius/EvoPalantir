# AOS Deployment Spec

_部署模型。monorepo 结构、参考部署图、分布式预留、配置。_

_关联文档：[aos-charter.md](../aos-charter.md) · [aos-transport.md](./aos-transport.md) · [aos-lifecycle.md](./aos-lifecycle.md)_

---

## 1. Monorepo 结构

```
EvoPalantir/
├── AgentOS/                ← 纯内核 + daemon
│   ├── src/aos/
│   │   ├── runtime.py      ← AOSRuntime（薄协调器）
│   │   ├── session/        ← SessionManager
│   │   ├── agent/          ← AgentManager
│   │   ├── skill/          ← SkillManager
│   │   ├── content/        ← ContentManager
│   │   ├── hook/           ← HookEngine
│   │   ├── store/          ← Store 实现
│   │   ├── react/          ← ReActUnit
│   │   └── transport/      ← FastAPI HTTP/SSE
│   ├── tests/
│   └── pyproject.toml
├── cli/                    ← CLI（HTTP 客户端，给 LLM 用）
│   ├── src/
│   └── pyproject.toml
├── packages/
│   ├── sdk-ts/             ← TypeScript SDK
│   │   ├── src/
│   │   └── package.json
│   └── sdk-py/             ← Python SDK
│       ├── src/aos_sdk/
│       └── pyproject.toml
├── skills/                 ← skillRoot
│   ├── aos/                ← 内建 skill，纯 skillText
│   │   └── SKILL.md
│   ├── aos-context/        ← 内建 skill，上下文引擎
│   │   ├── SKILL.md
│   │   └── plugin.py
│   └── frontend/           ← 前端 skill（完整 Next.js）
│       ├── SKILL.md
│       ├── plugin.ts
│       └── app/
└── docs/                   ← 文档（唯一真相）
    ├── aos-charter.md
    ├── specs/
    ├── references/
    └── README.md
```

### 1.1 组件职责

| 组件    | 职责                                      | 语言       |
| ------- | ----------------------------------------- | ---------- |
| AgentOS | 内核 + daemon，所有核心逻辑               | Python     |
| cli     | `aos` 命令，HTTP 客户端封装               | Python     |
| sdk-py  | Python SDK，HTTP/stdio 两种 transport     | Python     |
| sdk-ts  | TypeScript SDK，HTTP/stdio 两种 transport | TypeScript |
| skills/ | 所有 skill 目录，daemon file watch 此路径 | 任意       |
| docs/   | 文档体系，唯一真相                        | Markdown   |

### 1.2 依赖关系

```
cli ──depends──▶ sdk-py ──http──▶ AgentOS (daemon)
                                      ▲
skills/frontend/plugin.ts ──stdio──┘  │
                                      │
sdk-ts ──────────────http─────────────┘
```

- cli 依赖 sdk-py（引用 `AosClient`）
- Plugin 子进程通过 stdio 与 daemon 通信
- 外部程序通过 SDK 的 HTTP 模式与 daemon 通信
- AgentOS 不依赖任何外部组件

---

## 2. 单机参考部署

```
┌───────────────────────────────────────────┐
│  Machine                                  │
│                                           │
│  ┌────────────────────────────────────┐   │
│  │ AgentOS Daemon (Python/FastAPI)    │   │
│  │  ├─ HTTP/SSE Server (:8420)        │   │
│  │  ├─ AOSCP Router                   │   │
│  │  ├─ Managers                       │   │
│  │  │   ├─ SessionManager             │   │
│  │  │   ├─ AgentManager               │   │
│  │  │   ├─ SkillManager               │   │
│  │  │   └─ ContentManager             │   │
│  │  ├─ HookEngine                     │   │
│  │  ├─ SQLite Store                   │   │
│  │  │                                 │   │
│  │  ├─ [plugin] aos-context (system)  │   │
│  │  └─ [plugin] frontend (system) ─┐  │   │
│  └─────────────────────────────────┼──┘   │
│                            spawn   │      │
│  ┌─────────────────────────────────▼──┐   │
│  │ Next.js (:3000)                    │   │
│  │  Uses TS SDK → HTTP → Daemon      │   │
│  └────────────────────────────────────┘   │
│                                           │
│  $ aos call skill.list ── HTTP ──▶ Daemon │
│  (CLI is also an HTTP client)             │
└───────────────────────────────────────────┘
```

### 2.1 启动顺序

1. 用户设置 `AOS_API_TOKEN`
2. `aos daemon start`（或 `--detach`）
3. daemon 初始化 Store、扫描 skillRoot、注册内建 skill（`aos` + `aos-context`）、启动 system 级 Plugin
4. 用户通过浏览器访问前端 skill，或通过 CLI 操作

### 2.2 数据存储

单机默认使用 SQLite，数据文件位于：

```
~/.aos/
├── aos.db          ← SQLite 主库（控制块、历史、内容）
└── aos.log         ← daemon 日志
```

可通过 `AOS_DB_PATH` 环境变量自定义路径。

---

## 3. 分布式预留

当前版本为单机部署。以下架构预留确保未来可水平扩展。

### 3.1 水平扩展架构

```
┌──────────────┐     ┌──────────────┐
│  Daemon #1   │     │  Daemon #2   │
│  (stateless) │     │  (stateless) │
└──────┬───────┘     └──────┬───────┘
       │                     │
       ▼                     ▼
┌──────────────────────────────────┐
│  Shared Store                    │
│  ├─ PostgreSQL (CB, SH, Content) │
│  ├─ Redis (Lease, EventBus)      │
│  └─ S3 (大内容存储)              │
└──────────────────────────────────┘
```

### 3.2 无状态 daemon

daemon 不在内存中持有跨请求状态（SC 除外，但 SC 可从 SH rebuild）。每个 AOSCP 请求携带完整上下文（sessionId 等），daemon 从 Store 加载数据处理后返回。

### 3.3 Session 零共享

不同 Session 可在不同 daemon 实例执行。同一 Session 的 dispatch 通过 lease 机制保证单 writer（见 [aos-lifecycle.md](./aos-lifecycle.md) §8.2）。

### 3.4 可替换后端

| 基础设施          | 单机实现 | 分布式实现               |
| ----------------- | -------- | ------------------------ |
| ControlBlockStore | SQLite   | PostgreSQL               |
| HistoryStore      | SQLite   | PostgreSQL               |
| ContentStore      | SQLite   | S3 / 对象存储            |
| Lease             | 内存     | Redis / etcd             |
| EventBus          | 内存     | Redis Pub/Sub / 消息队列 |

所有基础设施通过接口抽象。替换后端只需提供新实现，不影响上层逻辑。

---

## 4. 配置

### 4.1 环境变量

| 变量             | 必填 | 默认值                  | 含义                                     |
| ---------------- | ---- | ----------------------- | ---------------------------------------- |
| `AOS_API_TOKEN`  | 是   | —                       | 鉴权 token，未设置拒绝启动               |
| `AOS_NAME`       | 否   | `"default"`             | AOS 实例名称，写入 AOSCB.name            |
| `AOS_PORT`       | 否   | `8420`                  | daemon 监听端口                          |
| `AOS_SKILL_ROOT` | 否   | `./skills`              | skill 扫描根目录，写入 AOSCB.skillRoot   |
| `AOS_DB_PATH`    | 否   | `~/.aos/aos.db`         | SQLite 数据库路径                        |
| `AOS_LOG_LEVEL`  | 否   | `info`                  | 日志级别：debug / info / warning / error |
| `AOS_API_URL`    | 否   | `http://127.0.0.1:8420` | 客户端连接 daemon 的地址                 |

### 4.2 AOSCB（系统控制块）

系统级配置存储在 AOSCB 中（见 [aos-data-model.md](./aos-data-model.md)）。AOSCB 的字段按来源分为两类：

**部署字段** — 每次 daemon 启动时从环境变量刷新，不通过 AOSCP 修改：

| 字段      | 环境变量         | 默认值      |
| --------- | ---------------- | ----------- |
| name      | `AOS_NAME`       | `"default"` |
| skillRoot | `AOS_SKILL_ROOT` | `./skills`  |

**业务配置字段** — 通过 `system.update` 命令修改，daemon 重启不影响：

| 字段                | 含义                                                      | 默认值 |
| ------------------- | --------------------------------------------------------- | ------ |
| defaultSkills       | system 级默认 skill 规则                                  | 空     |
| autoFoldThreshold   | 大内容折叠阈值（内核不消费，由 `aos-context` Skill 读取） | 16384  |
| compactionThreshold | 触发 compaction 的 token 阈值                             | —      |
| maxTurns            | ReActUnit 最大循环次数                                    | —      |

所有字段均可通过 `system.get` 查询（见 [aos-aoscp.md](./aos-aoscp.md) §2）。初始化规则见 [aos-lifecycle.md](./aos-lifecycle.md) §1.1。

### 4.3 SKILL.md 配置

每个 skill 通过目录下的 SKILL.md 声明元数据：

```yaml
---
name: my-skill
version: 1.0.0
description: A useful skill
plugin: ./plugin.py # 可选，声明 Plugin 可执行文件
---
# Skill 正文

这里是 skillText，会被注入到 Session 的上下文中。
```

---

## 5. skillRoot 约定

### 5.1 目录结构

```
skills/
├── aos/                    ← 内建，纯 skillText
│   └── SKILL.md
├── aos-context/            ← 内建，上下文引擎（system 级 Plugin）
│   ├── SKILL.md
│   └── plugin.py
├── frontend/               ← 前端 skill
│   ├── SKILL.md
│   ├── plugin.ts
│   ├── package.json
│   └── app/
├── security-guard/         ← 安全守卫 skill
│   ├── SKILL.md
│   └── plugin.py
└── my-workflow/            ← 自定义 skill（纯文本，无 Plugin）
    └── SKILL.md
```

### 5.2 扫描规则

- daemon 启动时扫描 `AOS_SKILL_ROOT` 下所有一级子目录
- 每个包含 `SKILL.md` 的子目录识别为一个 skill
- `SKILL.md` 的 YAML front matter 解析为 SkillManifest
- front matter 后的正文为 skillText

### 5.3 热重载

daemon 运行时通过 file watcher 监听 skillRoot 变化：

| 事件          | 动作                                    |
| ------------- | --------------------------------------- |
| SKILL.md 新增 | 索引新 skill，缓存 skillText            |
| SKILL.md 修改 | 刷新 SkillManifest，失效 skillText 缓存 |
| SKILL.md 删除 | 从索引移除                              |

运行中的 Plugin 不受热重载影响，继续使用启动时的版本。需要更新 Plugin 时，手动 stop + start。

### 5.4 安装/卸载

- 安装 skill = 将 skill 目录放入 skillRoot
- 卸载 skill = 从 skillRoot 删除 skill 目录
- 无包管理器、无注册表、无版本锁
- file watcher 自动检测变化
