# EvoPalantir

EvoPalantir is initialized as a monorepo for a future opinion intelligence platform built around the idea `Agent = LLM + Skills`.

At this stage, the repository contains project structure, workspace configuration, scaffold code, and code quality tooling. No real product implementation has been added yet.

## Architecture Direction

- `AgentOS/`: Pixi-managed Python workspace for the cognitive operating system core.
- `apps/web/`: pnpm-managed Next.js web app using the App Router.
- Other app, package, and infrastructure directories will be created only when real implementation starts.

## Monorepo Layout

```text
.
|-- AgentOS/
|   |-- pyproject.toml
|   `-- pixi.lock
|-- apps/
|   `-- web/
|-- .github/
|-- package.json
|-- pnpm-workspace.yaml
|-- README.md
`-- tsconfig.base.json
```

## Tooling Choices

- TypeScript workspace: `pnpm` workspaces
- Future frontend baseline: `Next.js 16 App Router`
- TypeScript quality: `eslint`, `typescript-eslint`, `eslint-plugin-simple-import-sort`, `prettier`, `prettier-plugin-tailwindcss`
- Git hooks for JS/TS: tracked `husky` hook scaffold, intentionally not auto-enabled
- Python environment: `pixi`
- Python quality: `ruff`, `pyright`, `pytest`
- Python hooks: `pre-commit`

## AgentOS Notes

`AgentOS/` is prepared as a Python-first workspace aligned with the Agent OS charter, but intentionally kept minimal for now:

- Pixi manages the Python environment and quality tasks.
- The deeper `Agent`, `Session`, `Skill`, `trace`, and package directories are deferred until real implementation starts.

## Quality Gates

- Root JS/TS config is ready through `eslint.config.mjs`, `.prettierrc.json`, `pnpm-workspace.yaml`, and `package.json`.
- Python quality is configured in `AgentOS/pyproject.toml` via Pixi tasks.
- CI skeleton lives in `.github/workflows/quality.yml`.
- Local hook scaffolds live in `.husky/pre-commit` and `.pre-commit-config.yaml`; they stay opt-in so the repo does not mutate local git config during initialization.

## Roadmap Context

The repository layout reflects the current project framing:

1. Phase 1: simulation and sandbox validation.
2. Phase 2: real-world data integration and shadow-system operation.
3. Phase 3: larger decision-support and intelligence integration.

## Next Setup Commands

When you want to activate the toolchain locally:

```bash
pnpm install
pixi run --manifest-path AgentOS/pyproject.toml quality
```

If you want local hooks later, enable them explicitly in your own environment.
