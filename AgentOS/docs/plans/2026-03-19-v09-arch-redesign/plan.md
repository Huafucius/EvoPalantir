# AgentOS v0.9 Architecture Redesign Plan

**Goal:** Deliver definitive v0.9 charter and implementation manual, incorporating six architectural decisions that elevate AgentOS from a prototype to a distribution-ready cognitive control kernel.

**Scope:**

- Included: ADR 0001, charter.md v0.9, impl-manual.md v0.9, docs/README.md
- Excluded: any code changes, implementation refactoring, test changes

**Success criteria:**

1. ADR 0001 accepted and committed
2. Charter v0.9 internally consistent — all section cross-references valid, all counts match
3. Impl-manual v0.9 internally consistent — all operation/hook/event counts match charter
4. 13 admission hooks + 6 transform hooks + 22 runtime events = 41 extension points (same total, reclassified)
5. 36 AOSCP operations classified as Command or Query
6. `session.dispatch` documented with async kernel semantics + client-side blocking/streaming adapters
7. Capability manifest formally separated from Skill
8. 5-layer architecture (Interface / Control / Execution / State / Extension) threaded through charter
9. `pixi run --manifest-path AgentOS/pyproject.toml quality` passes
10. `docs/README.md` updated

**Key decisions:**

- Hook system reclassified into 3 mechanisms (admission/transform/event) without renaming existing points
- `session.dispatch` becomes async at kernel level; CLI presents blocking+streaming facade
- AOSCP operations formally split into Commands (admission-gated) and Queries (lightweight)

---

## Docs Impact

| File                                               | Action  | What changes                                                                                                                   |
| -------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `AgentOS/docs/decisions/0001-v09-arch-redesign.md` | Create  | ADR: 6 architectural decisions with rationale                                                                                  |
| `AgentOS/docs/charter.md`                          | Rewrite | Full v0.9 charter with 5-layer architecture, 3-mechanism extension model, async dispatch, capability manifest                  |
| `AgentOS/docs/impl-manual.md`                      | Rewrite | Full v0.9 impl-manual with Command/Query tables, reclassified hook/event lists, dispatch spec, lease fields, capability schema |
| `AgentOS/docs/README.md`                           | Create  | Docs index and navigation                                                                                                      |

---

## Tasks

### Task 1: Write ADR 0001

**Files:**

- Create: `AgentOS/docs/decisions/0001-v09-arch-redesign.md`

**Steps:**

1. Write ADR covering all 6 decisions with context, alternatives, consequences
2. Commit: `docs(agentos): add ADR 0001 v0.9 architecture redesign`

---

### Task 2: Rewrite charter.md v0.9

**Files:**

- Rewrite: `AgentOS/docs/charter.md`

**Steps:**

1. Write complete charter incorporating all 6 architectural changes
2. Verify all section references, counts, and diagrams are internally consistent
3. Commit: `docs(agentos): rewrite charter v0.9 with 5-layer architecture`

---

### Task 3: Rewrite impl-manual.md v0.9

**Files:**

- Rewrite: `AgentOS/docs/impl-manual.md`

**Steps:**

1. Write complete impl-manual with Command/Query operation tables, reclassified extension points, async dispatch spec, lease fields, capability schema
2. Cross-check all counts against charter
3. Commit: `docs(agentos): rewrite impl-manual v0.9 with CQRS and extension reclassification`

---

### Task 4: Create docs/README.md

**Files:**

- Create: `AgentOS/docs/README.md`

**Steps:**

1. Write docs index with document descriptions and relationships
2. Commit: `docs(agentos): add docs README`

---

## Verification (Phase 4)

- [ ] `pixi run --manifest-path AgentOS/pyproject.toml quality` passes
- [ ] Charter extension point total = impl-manual extension point total = 41
- [ ] Charter AOSCP operation count = impl-manual operation count = 36
- [ ] Charter says "13 admission hooks, 6 transform hooks, 22 runtime events"
- [ ] Impl-manual lists exactly 13 + 6 + 22 extension points
- [ ] `session.dispatch` documented as async in both docs
- [ ] Capability manifest appears in both charter and impl-manual
- [ ] 5-layer architecture described in charter §1.2
- [ ] Docs Impact items verified: `git diff <plan-sha>..HEAD --name-only`
- [ ] `docs/README.md` exists and is current
- [ ] `git status` is clean
