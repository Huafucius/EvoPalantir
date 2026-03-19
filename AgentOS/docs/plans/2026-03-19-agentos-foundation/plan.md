# AgentOS Foundation Implementation Plan

> **For OpenCode:** REQUIRED EXECUTION SKILL: Use superpowers-implement-plan.

**Goal:** Bootstrap the AgentOS Python runtime with package layout, typed core models, async SQLite initialization, and a JSON-only CLI entrypoint.

**Architecture:** Build from the bottom of the dependency graph. Define shared contracts first with Pydantic v2, add a minimal async SQLite store without ORM abstraction leakage, then expose a Click CLI that already honors the JSON-only control-plane contract.

**Tech Stack:** Python 3.11, Pydantic v2, Click, aiosqlite, pytest, pytest-asyncio

**feature:**

---

## Docs Impact (Required)

No Memory Bank changes required -- this slice bootstraps implementation scaffolding without changing the published AgentOS charter or implementation manual.

### Task 1: Bootstrap package and dependencies

**Files:**

- Create: `AgentOS/src/aos/__init__.py`
- Create: `AgentOS/src/aos/__main__.py`
- Create: `AgentOS/src/aos/cli.py`
- Modify: `AgentOS/pyproject.toml`
- Test: `AgentOS/tests/test_cli.py`

**Step 1:** Write a failing CLI test for JSON output.

**Step 2:** Run the CLI test and verify it fails for the expected missing-package reason.

**Step 3:** Add runtime/test dependencies and create the package skeleton.

**Step 4:** Implement the minimal Click CLI entrypoint to make the test pass.

**Step 5:** Re-run the CLI test and confirm it passes.

### Task 2: Add foundational core models

**Files:**

- Create: `AgentOS/src/aos/model/__init__.py`
- Create: `AgentOS/src/aos/model/common.py`
- Create: `AgentOS/src/aos/model/control_block.py`
- Create: `AgentOS/src/aos/model/response.py`
- Test: `AgentOS/tests/model/test_control_blocks.py`
- Test: `AgentOS/tests/model/test_response.py`

**Step 1:** Write failing tests for schema version enforcement, default-skill validation, and JSON response dumping.

**Step 2:** Run those tests and verify they fail.

**Step 3:** Implement the minimal Pydantic models needed to satisfy the tests.

**Step 4:** Re-run the targeted model tests and confirm they pass.

### Task 3: Add async SQLite bootstrap store

**Files:**

- Create: `AgentOS/src/aos/store/__init__.py`
- Create: `AgentOS/src/aos/store/sqlite.py`
- Test: `AgentOS/tests/store/test_sqlite_store.py`

**Step 1:** Write a failing async test for initializing the SQLite schema.

**Step 2:** Run the test and verify it fails for the expected missing-module reason.

**Step 3:** Implement a minimal async SQLite store that creates the initial tables.

**Step 4:** Re-run the store test and confirm it passes.

### Task 4: Verify the bootstrap slice

**Files:**

- Verify only

**Step 1:** Run `pytest` for the targeted AgentOS test set.

**Step 2:** Run `pixi run --manifest-path AgentOS/pyproject.toml quality`.

**Step 3:** Review the diff and confirm the package skeleton and tests match the design.
