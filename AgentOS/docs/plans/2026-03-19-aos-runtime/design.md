# AgentOS Runtime Design

## Goal

Implement the complete AgentOS v0.81 runtime described by the charter and implementation manual.
The runtime must cover all documented AOSCP operations, all 39 hook points, the skill/plugin model,
the Session execution engine, persistence, CLI, SDK, and end-to-end verification with a real LLM.

## Architectural Shape

The implementation follows the dependency graph discussed earlier:

- `model/` holds Pydantic contracts and enums
- `store/` persists control blocks, SessionHistory, RuntimeLog, and runtime metadata in SQLite
- `hook/`, `event/`, `log/`, and `resource/` form the kernel infrastructure
- `skill/`, `agent/`, `session/`, `compute/`, and `tool/` implement the domain runtime
- `control/` exposes the AOSCP surface
- `cli/` and `sdk/` provide external access paths

## Runtime Strategy

The runtime uses asyncio end-to-end. Session drives the ReAct loop; ReActUnit performs one LiteLLM
call at a time and exposes a single formal tool surface: bash. Skill discovery is filesystem-based in
v0.81, with frontmatter-parsed manifests and dynamic plugin loading. Hook dispatch remains synchronous
in semantics while implemented with awaited async call chains.

## Testing Strategy

- unit tests for models, store, hook registry, event bus, and materialization
- integration tests for control-plane flows, plugin lifecycle, and Session loop
- real-key e2e tests for LiteLLM + `gpt-4o-mini`, guarded by environment availability

## Non-goals

The charter's deferred items remain deferred in code too: full permission DSL, hook sandboxing,
full in-flight loop recovery, and RuntimeLog analytical query language.
