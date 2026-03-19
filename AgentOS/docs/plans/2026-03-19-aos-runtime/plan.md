# AgentOS Runtime Implementation Plan

> **For OpenCode:** REQUIRED EXECUTION SKILL: Use superpowers-implement-plan.

**Goal:** Implement the full AgentOS v0.81 runtime, including AOSCP, hook surface, skills/plugins, Session execution, persistence, CLI, SDK, and real-key e2e verification.

**Architecture:** Build bottom-up from typed models and SQLite persistence into runtime infrastructure, then implement skill/plugin lifecycle, Session execution, and the control plane. Keep ReActUnit single-step only and let Session own the full loop.

**Tech Stack:** Python 3.11, asyncio, Pydantic v2, Click, aiosqlite, LiteLLM, pytest, pytest-asyncio

**feature:**

---

## Docs Impact (Required)

No Memory Bank changes required -- implementation is intended to realize the existing charter and manual without changing their published contract.

### Task 1: Finish package bootstrap and typed contracts

**Files:**

- Modify: `AgentOS/pyproject.toml`
- Create/Modify: `AgentOS/src/aos/model/*.py`
- Test: `AgentOS/tests/model/**/*.py`

Write failing tests first, then implement full control-block, history, context, response, hook, resource, and plugin models.

### Task 2: Implement SQLite persistence and runtime registries

**Files:**

- Create/Modify: `AgentOS/src/aos/store/*.py`
- Create/Modify: `AgentOS/src/aos/log/*.py`
- Test: `AgentOS/tests/store/**/*.py`

Write failing tests for append-only persistence and retrieval, then implement SQLite-backed stores and in-memory runtime registries.

### Task 3: Implement hook engine, event bus, resources, and plugin runtime

**Files:**

- Create: `AgentOS/src/aos/hook/*.py`
- Create: `AgentOS/src/aos/event/*.py`
- Create: `AgentOS/src/aos/resource/*.py`
- Create/Modify: `AgentOS/src/aos/skill/plugin.py`
- Test: `AgentOS/tests/hook/**/*.py`
- Test: `AgentOS/tests/resource/**/*.py`

Write failing tests for registration permissions, dispatch order, shared mutable output, and owner-scoped lifecycle handling. Then implement the kernel extension path.

### Task 4: Implement skill indexing, discovery, load/start/stop, and hot refresh

**Files:**

- Create: `AgentOS/src/aos/skill/*.py`
- Test: `AgentOS/tests/skill/**/*.py`

Write failing tests for SKILL.md parsing, catalog generation, default-skill resolution, Session injection, and plugin startup. Then implement filesystem-based discovery and lifecycle management.

### Task 5: Implement SessionHistory, SessionContext, materialization, bootstrap, reinject, compaction, and recovery

**Files:**

- Create: `AgentOS/src/aos/session/*.py`
- Test: `AgentOS/tests/session/**/*.py`

Write failing tests for append-only history, materialization rules, fold/unfold, compaction pairs, reinject, and bootstrap markers. Then implement the session runtime.

### Task 6: Implement ReActUnit and bash tool execution

**Files:**

- Create: `AgentOS/src/aos/compute/*.py`
- Create: `AgentOS/src/aos/tool/*.py`
- Test: `AgentOS/tests/compute/**/*.py`
- Test: `AgentOS/tests/tool/**/*.py`

Write failing tests for single-step LiteLLM calls, streamed chunk aggregation, tool-call parsing, and raw/visible bash result separation. Then implement the execution primitives.

### Task 7: Implement Agent runtime and the full Session loop

**Files:**

- Create: `AgentOS/src/aos/agent/*.py`
- Modify: `AgentOS/src/aos/session/*.py`
- Test: `AgentOS/tests/agent/**/*.py`
- Test: `AgentOS/tests/session/test_loop.py`

Write failing tests for Agent lifecycle, multi-session ownership, transform hooks, compute/tool progression, interrupts, and completion. Then implement orchestration.

### Task 8: Implement the complete AOSCP surface, CLI, and SDK

**Files:**

- Create: `AgentOS/src/aos/control/*.py`
- Modify: `AgentOS/src/aos/cli.py`
- Create: `AgentOS/src/aos/sdk/*.py`
- Test: `AgentOS/tests/control/**/*.py`
- Test: `AgentOS/tests/test_cli.py`

Write failing tests for all 35 operations, JSON-only responses, environment-default owner resolution, and SDK parity. Then implement the control plane.

### Task 9: Add integration and e2e verification

**Files:**

- Create: `AgentOS/tests/integration/**/*.py`
- Create: `AgentOS/tests/e2e/**/*.py`

Write failing tests for end-to-end skill loading, plugin hooks, real bash tool flow, and real LiteLLM execution with `gpt-4o-mini` when credentials are present.

### Task 10: Final verification

**Files:**

- Verify only

Run targeted tests, `pixi run --manifest-path AgentOS/pyproject.toml quality`, and the strongest relevant repo-wide verification commands. Then review the resulting diff against the charter/manual contract.
