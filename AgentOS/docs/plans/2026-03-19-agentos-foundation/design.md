# AgentOS Foundation Design

## Scope

This first implementation slice bootstraps the Python runtime for AgentOS v0.81.
It does not attempt to implement the full control plane yet.
Instead, it establishes the package layout, runtime dependencies, core data models,
the first async SQLite persistence primitive, and a JSON-only CLI entrypoint.

## Approach

The code starts from the bottom of the dependency graph:

- `model/` defines shared contracts with Pydantic v2
- `store/` provides an async SQLite bootstrap layer without ORM indirection
- `cli/` exposes a minimal Click-based entrypoint that already obeys JSON-only output

This keeps the first checkpoint small, testable, and aligned with the architecture:
strong contracts first, orchestration later.

## Non-goals

- No full AOSCP implementation yet
- No Session loop yet
- No plugin runtime yet
- No PostgreSQL backend yet

## Why This Slice

Without package structure, typed models, and a concrete persistence boundary,
all later modules would be forced to guess their shared contracts.
This slice creates those contracts early and keeps future modules highly cohesive.
