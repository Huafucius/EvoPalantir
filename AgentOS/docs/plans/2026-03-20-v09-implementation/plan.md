# AgentOS v0.9 Implementation Plan

**Goal:** Implement the full AgentOS v0.9 kernel so the codebase matches the current charter and implementation manual, including all 36 AOSCP operations, the 13/6/22 extension system, async dispatch, lease semantics, Capability Manifest support, ContentStore, fold/unfold, and recovery behavior.

**Scope:**

- Included: Python code under `AgentOS/src/aos/`, Python tests under `AgentOS/tests/`, docs index updates in `AgentOS/docs/README.md`
- Explicitly excluded: `apps/web/`, new external services, distributed deployment implementation, permissions DSL beyond v0.9 warning-level capability validation

**Success criteria:**

1. The code exposes all **36** v0.9 AOSCP operations with explicit command/query split.
2. The code implements **13 Admission Hooks**, **6 Transform Hooks**, and **22 Runtime Events**, with the semantics defined in `AgentOS/docs/impl-manual.md`.
3. `session.dispatch` is async at kernel level, returns `dispatchId`, and supports blocking/streaming adapters at the interface layer.
4. `SessionControlBlock` includes `phase`, `leaseId`, `leaseHolder`, and `leaseExpiresAt`, and lease behavior is enforced.
5. ContentStore-backed large output flow works end-to-end: oversized tool result -> `contentId` -> materialized file -> folded placeholder -> unfold.
6. Capability Manifest is parsed from skills, represented in models, and used to constrain AosSDK access at warning/validation level consistent with v0.9.
7. Existing v0.81-only execution path (`AOSRuntime.run_session()`) is removed or reduced to an internal compatibility shim that no longer defines the main architecture.
8. New and updated tests cover async dispatch, lease, command/query split, extension classification, ContentStore, fold placeholders, capability manifest, and recovery.
9. `pixi run --manifest-path AgentOS/pyproject.toml quality` passes.
10. `pixi run --manifest-path AgentOS/pyproject.toml test` passes.

**Key decisions:**

- Keep and adapt the strongest existing modules (models, SQLite store, event bus, CLI, skill parsing) while rewriting the monolithic control plane and session loop around the v0.9 five-layer architecture.
- Implement v0.9 incrementally from the bottom up: state first, then extension system, then control plane, then execution/dispatch, then interface adapters and E2E verification.
- Use acceptance-driven development: each stage adds tests for newly introduced v0.9 behavior before the corresponding implementation is considered complete.

---

## Docs Impact

| File                                                       | Action | What changes                                                  |
| ---------------------------------------------------------- | ------ | ------------------------------------------------------------- |
| `AgentOS/docs/plans/2026-03-20-v09-implementation/plan.md` | Create | Implementation plan, acceptance criteria, phased verification |
| `AgentOS/docs/README.md`                                   | Update | Add v0.9 implementation plan to docs index                    |

---

## Tasks

### Task 1: Restructure Core Package Boundaries

**Files:**

- Modify: `AgentOS/src/aos/control/plane.py`
- Create/Modify: `AgentOS/src/aos/control/*.py`, `AgentOS/src/aos/execution/*.py`, `AgentOS/src/aos/state/*.py`, `AgentOS/src/aos/extension/*.py`

**Steps:**

1. Write acceptance criteria in control/execution integration tests for the new package boundaries.
2. Run narrow verification to confirm current `AOSRuntime.run_session()`-centric architecture does not satisfy v0.9 shape.
3. Implement minimal composition root plus separated managers/routers.
4. Run narrow verification again.
5. Commit: `refactor(agentos): split runtime into control execution state extension layers`

---

### Task 2: Implement v0.9 Data Models and Storage Schema

**Files:**

- Modify: `AgentOS/src/aos/model/control_block.py`
- Modify: `AgentOS/src/aos/model/history.py`
- Modify: `AgentOS/src/aos/model/runtime.py`
- Modify: `AgentOS/src/aos/store/sqlite.py`
- Add tests: `AgentOS/tests/model/*`, `AgentOS/tests/store/test_content_store.py`

**Steps:**

1. Add acceptance criteria for schema version, lease fields, ContentStore blobs table, ToolBashOutput metadata.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/model tests/store` — confirm v0.9 cases fail.
3. Implement v0.9 schema/models/storage minimally.
4. Run the same command — confirm it passes.
5. Commit: `feat(agentos): add v0.9 state models and content store`

---

### Task 3: Implement Extension System (AH / TH / RE)

**Files:**

- Modify/Create: `AgentOS/src/aos/hook/*.py`, `AgentOS/src/aos/event/*.py`, `AgentOS/src/aos/sdk/*.py`, `AgentOS/src/aos/skill/*.py`
- Add tests: `AgentOS/tests/hook/test_admission_hooks.py`, `AgentOS/tests/hook/test_transform_hooks.py`, `AgentOS/tests/event/test_runtime_events.py`, `AgentOS/tests/skill/test_capability_manifest.py`

**Steps:**

1. Add acceptance criteria for 13 AH, 6 TH, 22 RE and capability parsing.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/hook tests/event tests/skill` — confirm new categories fail.
3. Implement explicit registries/dispatch/subscription paths.
4. Run the same command — confirm it passes.
5. Commit: `feat(agentos): implement v0.9 extension system and capability manifests`

---

### Task 4: Implement Command/Query Split and Full AOSCP Surface

**Files:**

- Modify/Create: `AgentOS/src/aos/control/*.py`, `AgentOS/src/aos/sdk/*.py`, `AgentOS/src/aos/cli.py`
- Add tests: `AgentOS/tests/control/test_command_query_split.py`, update `AgentOS/tests/control/test_aoscp_surface.py`

**Steps:**

1. Add acceptance criteria for 20 commands, 16 queries, RL behavior, and AOSCP routing.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/control` — confirm v0.9 expectations fail.
3. Implement the explicit command/query surface minimally.
4. Run the same command — confirm it passes.
5. Commit: `feat(agentos): implement v0.9 aoscp command query split`

---

### Task 5: Implement Async Dispatch, Lease, and ReAct Loop

**Files:**

- Modify/Create: `AgentOS/src/aos/execution/*.py`, `AgentOS/src/aos/compute/react_unit.py`, `AgentOS/src/aos/tool/executor.py`
- Add tests: `AgentOS/tests/session/test_dispatch_async.py`, `AgentOS/tests/session/test_lease.py`, update `AgentOS/tests/session/test_loop.py`

**Steps:**

1. Add acceptance criteria for async `session.dispatch`, `dispatchId`, lease acquisition/release, and `session.busy`.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/session/test_dispatch_async.py tests/session/test_lease.py tests/session/test_loop.py` — confirm failures.
3. Implement the async kernel dispatch path and lease manager.
4. Run the same command — confirm it passes.
5. Commit: `feat(agentos): implement async dispatch and session lease`

---

### Task 6: Implement Fold/Unfold, Placeholders, and Recovery

**Files:**

- Modify: `AgentOS/src/aos/model/context.py`, storage/control/execution modules as needed
- Add tests: `AgentOS/tests/session/test_fold_placeholder.py`, update `AgentOS/tests/session/test_materialize.py`

**Steps:**

1. Add acceptance criteria for auto-fold, placeholder format, materialized files, unfold, and rebuild/recovery behavior.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/session/test_materialize.py tests/session/test_fold_placeholder.py` — confirm failures.
3. Implement minimally.
4. Run the same command — confirm it passes.
5. Commit: `feat(agentos): implement fold placeholders and recovery semantics`

---

### Task 7: Full Integration and E2E Validation

**Files:**

- Modify: `AgentOS/tests/e2e/test_real_llm.py`, integration/control tests as needed
- Verify docs index: `AgentOS/docs/README.md`

**Steps:**

1. Add acceptance criteria for end-to-end v0.9 flow.
2. Run `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/integration tests/e2e` — confirm remaining failures.
3. Complete minimal fixes.
4. Run full verification commands.
5. Commit: `test(agentos): validate end-to-end v0.9 runtime`

---

## Verification (Phase 4)

- [ ] `pixi run --manifest-path AgentOS/pyproject.toml quality` passes
- [ ] `pixi run --manifest-path AgentOS/pyproject.toml test` passes
- [ ] `AgentOS/docs/README.md` updated
- [ ] All 36 AOSCP operations exist in code with explicit command/query routing
- [ ] All 13 Admission Hooks, 6 Transform Hooks, and 22 Runtime Events exist in code
- [ ] `session.dispatch` is async in the kernel and returns `dispatchId`
- [ ] `SessionControlBlock` contains `phase`, `leaseId`, `leaseHolder`, `leaseExpiresAt`
- [ ] ContentStore-backed fold/unfold flow works in tests
- [ ] Capability Manifest parsing and enforcement path exist in code
- [ ] `git diff <plan-sha>..HEAD --name-only` covers planned docs impact
- [ ] `git status` is clean
