# 0001: AgentOS v0.9 Architecture Redesign

**Status:** Accepted
**Date:** 2026-03-19

---

## Context

AgentOS v0.81 delivered a working prototype with 35 AOSCP operations, 39 hook points, and a monolithic `AOSRuntime` that intermixed control plane, execution loop, and storage concerns. The v0.81 charter defined "三个正式表面" (AOSCP, Hook, Skill) and a `run_session()` method that bypassed the formal AOSCP operation surface.

Iterative design review identified six structural weaknesses that would compound as the system grows toward distributed multi-agent deployment:

1. **Hook overloading.** The single "hook" concept covered three fundamentally different execution semantics: blocking admission control, pure data transformation, and async lifecycle notification. Slow lifecycle handlers blocked the main execution path.

2. **Blocking dispatch.** `session.dispatch` was defined as a synchronous blocking kernel operation. In a distributed setting, the node accepting the command may not be the node executing the ReAct loop.

3. **Implicit Command/Query mixing.** All 35 AOSCP operations shared the same routing path regardless of whether they mutated state. Read-heavy operations ran the same admission pipeline as writes.

4. **Missing execution isolation.** Session had a single-writer constraint but no formal lease mechanism to enforce it across restarts or distributed nodes.

5. **Flat architecture.** No formal layering separated interface, control, execution, state, and extension concerns. Module boundaries were implicit.

6. **Security/packaging conflation.** Skill was simultaneously the packaging unit and the security boundary. A skill's permissions were determined by its name, not by a declared capability set.

These six issues are independent but mutually reinforcing: fixing one without the others leaves structural debt. This ADR addresses all six as a cohesive redesign.

---

## Decision

Adopt six architectural changes for AgentOS v0.9:

### D1. Extension Model: Admission Hooks + Transform Hooks + Runtime Events

Replace the single "hook" abstraction with three formally distinct mechanisms:

- **Admission Hooks** (13): synchronous, blocking, can reject or modify the operation. Run only on the command path. Analogous to Kubernetes admission controllers.
- **Transform Hooks** (6): synchronous, pure data rewrite at specific pipeline positions. Cannot reject the operation, only reshape data flowing through.
- **Runtime Events** (22): asynchronous, read-only, fire-and-forget. Absorb all lifecycle notifications (started, archived, after, error). Analogous to Kubernetes informer events.

Total extension points remain 41 (same as v0.81 provisional count), but semantics are now formally differentiated. The key operational consequence: lifecycle notifications no longer block the main execution path.

### D2. Async Dispatch

`session.dispatch` becomes an asynchronous kernel command:

- Kernel immediately returns `{ dispatchId }` after admission and message append.
- Execution proceeds on an internal worker (local or remote).
- Client-side adapters provide blocking wait, SSE streaming, or polling.
- CLI defaults to blocking+streaming facade for UX continuity.

This decouples "accepting the command" from "executing the loop", which is the fundamental prerequisite for distributed dispatch.

### D3. AOSCP Command/Query Separation

Formally partition all 36 AOSCP operations into two classes:

- **Commands** (20): mutate state, go through admission hooks, produce RuntimeLog entries, return revision numbers.
- **Queries** (16): read-only, bypass admission hooks, lightweight, cacheable.

Queries never trigger admission hooks. This reduces latency for read-heavy paths (history listing, context inspection, catalog browsing) and prevents a crashing admission hook from blocking reads.

### D4. Session Lease

Add lease semantics to Session to enforce single-writer invariant across restarts and distributed nodes:

- `session.dispatch` acquires a time-bounded lease (default TTL 30 minutes, configurable).
- While a lease is held, subsequent dispatches return `session.busy`.
- If the worker crashes, the lease expires and the session becomes available.
- Lease is renewed implicitly during active execution.
- Lease fields are stored in SCB: `leaseId`, `leaseHolder`, `leaseExpiresAt`.

This is the minimum mechanism needed to safely distribute session execution across nodes.

### D5. Five-Layer Architecture

Formalize the internal structure into five layers:

| Layer     | Responsibility                                    | Key Components                                                                  |
| --------- | ------------------------------------------------- | ------------------------------------------------------------------------------- |
| Interface | Protocol adaptation                               | CLI, Python SDK, TypeScript SDK, HTTP/SSE                                       |
| Control   | Command/Query routing, admission, permissions     | AOSCP router, admission hooks, auth                                             |
| Execution | ReAct loop, tool execution, dispatch coordination | ReActUnit, BashExecutor, Scheduler                                              |
| State     | Persistence, projection, content management       | SH Store, RL Store, CB Store, ContentStore, SC Projector                        |
| Extension | Capability delivery, lifecycle reactions          | Skill Manager, Plugin Runtime, Transform Hooks, Runtime Events, ManagedResource |

Each layer depends only on layers below it. The Interface layer never reaches past Control to touch State directly.

### D6. Capability Manifest

Separate the security boundary from the packaging boundary:

- **Skill** remains the packaging and distribution unit (SKILL.md, skillText, plugin entry).
- **CapabilityManifest** is a new declaration within SKILL.md frontmatter that enumerates what the skill needs from the kernel.

Example capabilities: `session.read`, `session.write`, `tool.execute`, `resource.manage`, `agent.read`, `filesystem.read`, `network.egress`.

The permission system evaluates capability requests, not skill names. This enables:

- Least-privilege enforcement per skill.
- Capability auditing independent of skill identity.
- Future capability-based access control without redesigning the skill model.

---

## Alternatives Considered

| Alternative                                                                | Why rejected                                                                                                                                                          |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Keep unified hook model, add `async: true` flag                            | Conflates two execution models in one registry; every hook handler must check mode; lifecycle hooks still registered in the blocking pipeline by default              |
| Keep `session.dispatch` synchronous, add separate `session.dispatch.async` | Two operations for the same concept; callers must choose correctly; sync version still blocks the accepting node                                                      |
| Implicit Command/Query detection from operation signatures                 | Fragile; adding a side-effect to a "read" silently changes its classification; explicit is safer                                                                      |
| Full RBAC instead of capability manifest                                   | RBAC is a policy enforcement model, not a declaration model; capabilities declare what a skill needs, RBAC decides what it gets; both are needed, at different layers |
| Merge all lifecycle hooks into a single `events.subscribe` API             | Loses the named, typed nature of each event; harder to document and discover; existing naming convention is good                                                      |
| 3-layer architecture (Interface / Core / Storage)                          | Too coarse; conflates control and execution, making it hard to isolate scheduling from admission                                                                      |

---

## Consequences

**Positive:**

- Lifecycle events can never block or crash the main execution path.
- Read-heavy operations (history listing, context inspection) skip admission overhead.
- Distributed dispatch is architecturally natural: accept on any node, execute on the leased node.
- Capability manifest enables least-privilege analysis before a skill is started.
- 5-layer model gives clear module boundary guidance for implementation.

**Negative / trade-offs:**

- Three extension mechanisms instead of one increases conceptual surface for plugin authors.
- Async dispatch adds a `dispatchId` indirection that simple CLI use cases don't need (mitigated by blocking adapter).
- Lease TTL introduces a new failure mode (lease expiry during long execution) that must be handled.
- Capability manifest is a new concept that existing skills must adopt (mitigated by graceful degradation: skills without manifest get default capabilities).

**Neutral:**

- Total extension point count (41) unchanged; this is a reclassification, not an expansion.
- AOSCP operation count (36) unchanged; this is a categorization, not an addition.
- SessionHistory, SessionContext, and RuntimeLog data models are unaffected.

---

## Notes

- This ADR supersedes the provisional v0.81 hook and dispatch design.
- Charter v0.9 and impl-manual v0.9 are the authoritative documents that implement this ADR.
- Code refactoring to align with this architecture is tracked separately.
- Lease TTL default (30 minutes) is provisional and should be tuned based on observed ReAct loop durations.
