# EvoPalantir AgentOS 最简 PoC 设计 v0.1

日期：2026-03-19  
范围：仅【底层 LLM 内核】+ Bash +【1 Agent + 3 Skills】

## 1. 目标

验证 AOS 核心命题可运行：LLM 只能通过 Bash 调用 AOSCP，并在 AOS 内核调度下推进会话。  
不做大而全实现，只验证最小闭环与可恢复性。

## 2. 非目标

- 不实现完整 35 个 AOSCP 操作与 39 个 Hook 点。
- 不实现完整权限 DSL、Hook 超时沙箱、复杂资源配额。
- 不做多 Agent 并发与跨会话复杂协同。

## 3. 最小系统拓扑

### 3.1 内核组件

- Scheduler（票据调度）
- Session Engine（ReAct 循环）
- ReActUnit（LiteLLM 适配层）
- Bash Executor（唯一工具）
- AOSCP（JSON-only 控制面）
- Store（CB/SH/RL 持久化）

### 3.2 运行对象

- 1 个 Agent：`agent-001`
- 1 个 Session：`session-001`（后续可扩展）
- 3 个 Skills：`aos` / `docs-rag` / `bash-safe`

## 4. 三个 Skills 设计

### 4.1 `aos`（必须）

- 用途：向 LLM 注入 AOSCP 命令契约与 JSON 解析约定。
- 生命周期：`default load=enable`, `start=disable`。

### 4.2 `docs-rag`

- 用途：针对 `docs/` 的检索策略与引用规范（优先关键词检索，再按段读取）。
- 生命周期：`default load=enable`, `start=disable`。

### 4.3 `bash-safe`

- 用途：控制 Bash 执行边界，提供最小 `tool.before` / `tool.after` / `tool.env` Hook。
- 生命周期：`default load=enable`, `start=enable`。

## 5. 最小 AOSCP 操作集（PoC）

- `agent.create` / `agent.get`
- `session.create` / `session.get` / `session.append`
- `session.history.list`
- `session.context.get` / `session.context.rebuild`
- `skill.list` / `skill.load` / `skill.start`
- `plugin.list`

约束：CLI `stdout` 仅输出 JSON，不混入 prose。

## 6. 调度模型（类 OS 内核）

`ExecutionTicket.kind` 仅保留：`compute` / `tool`。  
同一 Session 同时只允许一条主执行链。

主循环：

1. enqueue `compute(session-001)`
2. compute -> 调用 ReActUnit
3. 若返回 `tool_call` -> enqueue `tool`
4. tool -> 执行 bash -> rawResult 写 RL -> visibleResult 写 SH
5. enqueue compute，直到 final answer
6. final answer 写 SH，phase 回到 `idle`

## 7. 持久化布局（最小）

```text
runtime/
  aoscb.json
  runtime-log.jsonl
  agents/agent-001/acb.json
  agents/agent-001/sessions/session-001/scb.json
  agents/agent-001/sessions/session-001/history.jsonl
```

说明：

- SH append-only，RL append-only。
- SC 为运行时缓存，可随时 rebuild。

## 8. 可行性验收（必须全部通过）

A. 启动后 `skill.list` 恰好返回 3 个 skills（含 `aos`）。  
B. bootstrap 后 SH 出现 begin/done marker + 3 条 skill-load 事实。  
C. LLM 发出 Bash tool_call 可成功调用 `aos ...` 命令并读取 JSON。  
D. tool rawResult 在 RL，visibleResult 在 SH。  
E. 进程重启后通过 `session.context.rebuild` 恢复并可继续对话。

## 9. 敏捷迭代（4 个小步）

- Sprint-1：数据模型 + JSON-only CLI 壳子（不接 LLM）。
- Sprint-2：ReActUnit + Bash + 单 Session 循环。
- Sprint-3：3 skills（discover/load/start）+ 最小 Hook runtime。
- Sprint-4：恢复与验收脚本（重启后 rebuild）。

## 10. 架构原则（高内聚、低耦合）

- LLM 内核只关心单次推理，不直接写持久化。
- Session Engine 只负责编排循环，不嵌入 skill 策略细节。
- AOSCP 作为唯一状态改写入口，统一审计写入。
- Skill 通过 Hook 介入，不与其他 skill 直接通信。
- Bash 执行与会话可见结果解耦：raw 进 RL，visible 进 SH。

## 11. 系统说明（操作-反应-内核类比）

### 11.1 对系统做什么操作，系统如何反应

1. 执行 `aos aos.init`：创建 `aoscb.json`，写入 system 默认 `defaultSkills`，并写一条 RL 审计。  
2. 执行 `aos agent.create`：创建 `acb.json`（agent 控制块），状态为 `active`。  
3. 执行 `aos session.create`：创建 `scb.json` 与 `context-meta.json`；在 SH 追加 bootstrap begin/done 与 3 条默认 skill-load；对 `start=enable` 的 `bash-safe` 自动启动 pluginInstance。  
4. 执行 `aos session.append`：把用户输入追加到 SH（append-only），同时更新 SCB revision。  
5. 执行 `aos session.run_turn`：Session Engine 驱动一次最小 ReAct 循环（`computing -> tooling -> computing -> idle`），若 ReActUnit 产出 tool_call，则交给 Bash 执行。  
6. 执行 `aos session.context.rebuild`：递增 `contextRevision` 并允许进程重启后继续对话推进。

### 11.2 为什么这能说明“底层 LLM 通过 Bash 操纵 agent”

- ReActUnit 的职责是“决策下一步”，当读到 `bash: ...` 输入时返回 `tool_call`，代表“模型决定调用工具”。  
- Session Engine 不直接替模型做业务决策，只负责编排：拿到 `tool_call` 后执行 Bash，再把结果回灌给下一轮推理。  
- `tool.before/tool.env/tool.after` 三段 Hook 证明 skill 可以在不破坏内核边界的前提下塑造 Bash 行为（命令改写、环境注入、可见结果改写）。  
- 结果分流符合文档契约：`rawResult` 写 RL（系统审计），`visibleResult` 写 SH（会话可见）。这正是“模型通过 Bash 影响世界，再回到会话事实”的闭环。

### 11.3 如何对应“像操作系统内核调度进程”

- `AOSCP` 对应 syscall/control plane：所有状态改写从这里进入。  
- `Session` 对应进程：每个 session 拥有独立控制块、历史与上下文版本。  
- `SessionEngine.run_turn` 对应调度器：管理 phase 切换与 compute/tool 交替执行。  
- `BashExecutor` 对应统一 I/O 执行层：内核把外部动作收敛到单一世界接口。  
- `HookRuntime` 对应内核扩展点：pluginInstance 在固定时序点介入，不绕过控制面直接改真相。  
- `SessionHistory + RuntimeLog` 对应用户态事实流 + 内核态审计流：一个用于会话继续，一个用于系统追责与诊断。

### 11.4 版本维护规则（系统说明）

- 本节作为 v0.1 系统说明，随模拟架构迭代同步更新。  
- 当出现重大结构变化（例如动态插件加载器、多 Session 并发调度、真实 LiteLLM 接入）时，与设计文档共同升级为新版本（如 `poc-min-kernel-v0.2.md`），并先与你确认范围与迁移策略。

## 12. 进展日志（持续追加）

追加规则：仅追加，不覆盖历史；每条记录使用 `YYYY-MM-DD | 状态 | 说明`。

- 2026-03-19 | done | 完成 docs 全量 RAG 阅读与最简 PoC v0.1 架构定稿。
- 2026-03-19 | next | 开始 Sprint-1：落地最小数据模型与 JSON-only CLI 骨架。
- 2026-03-19 | doing | 已创建 `agentos` 包结构、控制面与文件存储骨架。
- 2026-03-19 | done | Sprint-1 第一版完成：最小数据模型 + JSON-only CLI 可运行。
- 2026-03-19 | done | 完成 CLI 冒烟验证：`aos.init`、`skill.list`、`agent.create`、`session.*`、`context.rebuild`。
- 2026-03-19 | note | 当前环境缺少 `pixi/ruff/pyright`，已用 `python -m compileall src` 做语法级校验。
- 2026-03-19 | doing | 进入 Sprint-2：实现最小 ReActUnit + Bash Executor + 单 Session run_turn。
- 2026-03-19 | done | `session.create` 已满足 begin/done marker + 3 条默认 skill-load 注入事实。
- 2026-03-19 | done | 新增 `session.run_turn`：compute -> tool(bash) -> compute 到 final answer 闭环。
- 2026-03-19 | done | 验证 rawResult 写 RL、visibleResult 写 SH（`tool-bash` part）。
- 2026-03-19 | done | 在 `evopalantir` 环境跑通 `ruff check` 与 `ruff format --check`。
- 2026-03-19 | note | `pixi` 命令在当前环境映射为非 Pixi 包管理器（命令集不含 `run`）。
- 2026-03-19 | note | `pyright` 受 Node 运行时 `libatomic.so.1` 动态库加载问题阻塞，待修复后补跑。
- 2026-03-19 | doing | 进入 Sprint-3：实现最小 Hook Runtime（`tool.before/tool.env/tool.after`）。
- 2026-03-19 | done | `bash-safe` 通过 `skill.start`/默认 start 绑定 3 个 tool hooks。
- 2026-03-19 | done | `session.run_turn` 已接入 hook 链：前置改写命令、注入环境变量、后置改写 visible result。
- 2026-03-19 | done | 增加 phase 审计：`session.phase` 记录 `computing/tooling/idle`。
- 2026-03-19 | note | 为保持最简 PoC，Hook Runtime 采用内建静态映射（未引入动态插件加载器）。
- 2026-03-19 | done | 冒烟验证通过：`bash-safe` 自动启动并注入 `AOS_AGENT_ID/AOS_SESSION_ID`。
- 2026-03-19 | done | 冒烟验证通过：危险命令被 `tool.before` 改写为阻断提示。
- 2026-03-19 | note | 结构优化：将 Hook 逻辑从 SessionEngine 抽到 `hook_runtime.py`，降低耦合。
- 2026-03-19 | doing | 进入 Sprint-4：补齐恢复验收脚本与自动化验证。
- 2026-03-19 | done | 新增 `scripts/acceptance_sprint4.py`，覆盖“重启后 context.rebuild + 继续对话”验收。
- 2026-03-19 | done | 新增 `tests/test_sprint4_recovery.py`，覆盖恢复与 raw/visible 分流断言。
- 2026-03-19 | done | 在 `evopalantir` 环境通过：`ruff check`、`ruff format --check`、`pyright src`。
- 2026-03-19 | done | 验收脚本输出 `ok: true`，核心检查全部通过。
- 2026-03-19 | note | `evopalantir` 环境未内置 `pytest`，测试文件已添加，待安装后可直接执行。
- 2026-03-19 | done | 新增“系统说明（操作-反应-内核类比）”章节，作为后续版本演进基线。
- 2026-03-19 | done | 完成路径依赖排查：根质量门禁、CI 与开发指引统一改为 `AgentOS_Test/pyproject.toml`。
- 2026-03-19 | done | 迁移后验收复测通过：`scripts/acceptance_sprint4.py --runtime-root runtime_acceptance_pathcheck` 输出 `ok: true`。
