# AGENTS.md

This file is for coding agents operating in `/Users/zhangtianhua/Desktop/EvoPalantir`.
Follow repository config over generic framework defaults.

## Repo Shape

- Monorepo root uses `pnpm` for JavaScript and TypeScript.
- `AgentOS/` is a separate Pixi-managed Python workspace.
- `apps/web/` is the only pnpm workspace app today.
- Root git hooks use `husky`.
- Commit messages are enforced with `commitlint` and Conventional Commits.

## Key Files

- `package.json` - root scripts, quality gate, husky bootstrap
- `pnpm-workspace.yaml` - workspace members (`apps/*`)
- `apps/web/` - Next.js 16 App Router app
- `AgentOS/pyproject.toml` - Python tooling and Pixi tasks
- `.github/workflows/quality.yml` - CI checks
- `.husky/pre-commit` - local quality gate
- `.husky/commit-msg` - local commit message gate

## Working Directory

- Run commands from `/Users/zhangtianhua/Desktop/EvoPalantir` unless a task is clearly package-local.

## Commands

### Full gate

- `pnpm quality`
  - Runs ESLint, Prettier check, TypeScript typecheck, `apps/web` build, and AgentOS Python quality.
  - This is the command used by local `pre-commit`.
  - Use this before claiming work is complete.

### Root JS / TS

- `pnpm lint`
- `pnpm lint:fix`
- `pnpm format`
- `pnpm format:check`
- `pnpm typecheck`

### Web app

- `pnpm --filter web dev`
- `pnpm --filter web build`
- `pnpm --filter web start`
- `pnpm --filter web typecheck`

### AgentOS

- `pixi run --manifest-path AgentOS/pyproject.toml lint`
- `pixi run --manifest-path AgentOS/pyproject.toml format`
- `pixi run --manifest-path AgentOS/pyproject.toml format-check`
- `pixi run --manifest-path AgentOS/pyproject.toml typecheck`
- `pixi run --manifest-path AgentOS/pyproject.toml test`
- `pixi run --manifest-path AgentOS/pyproject.toml quality`

## Narrowest Useful Checks

- TS typing/config-only change: `pnpm --filter web typecheck`
- Next.js runtime/build-sensitive change: `pnpm --filter web build`
- Root lint-only change: `pnpm lint`
- Root formatting-only change: `pnpm format:check`
- Python typing change: `pixi run --manifest-path AgentOS/pyproject.toml typecheck`
- Python lint/format change: `pixi run --manifest-path AgentOS/pyproject.toml lint`

## Test Guidance

- `apps/web/` has no JavaScript test framework configured yet.
- `AgentOS/` has `pytest` configured but currently has no test files.
- Do not invent `vitest`, `jest`, or `playwright` commands unless you add them in the same change.
- When Python tests exist, run a single test like this:
  - `pixi run --manifest-path AgentOS/pyproject.toml test -- tests/test_file.py::test_name`
- If you add a JS/TS test runner, also add scripts for full test run, single test file, and single test case if supported.

## Git Hooks and CI

### Local hooks

- `pre-commit` runs `pnpm quality`.
- `commit-msg` runs `pnpm exec commitlint --edit "$1"`.
- Hooks are installed by `pnpm install` through `prepare: husky`.

### Commit messages

- Use Conventional Commits.
- Good: `feat(web): add dashboard shell`
- Good: `fix(agentos): handle empty config`
- Good: `docs: update setup guide`
- Bad: `update stuff`
- Bad: `bad message`
- Bad: `fix`

### CI

- GitHub Actions currently runs commit message linting, TypeScript quality, and Python quality.
- If you change local quality gates, update CI in the same change.

## Formatting Rules

- Formatting is not optional.
- From `.prettierrc.json`: semicolons required, single quotes required, trailing commas where Prettier applies them.
- Tailwind classes are normalized by `prettier-plugin-tailwindcss`.
- From `.editorconfig`: JS/TS/JSON/YAML/Markdown/TOML/Shell use 2 spaces; Python uses 4 spaces.
- Line endings are LF, final newline required, trailing whitespace trimmed.

## TypeScript and React Conventions

- Use TypeScript, not plain JavaScript, for app code.
- `allowJs` is false.
- Keep strict typing compatible with `tsconfig.base.json`.
- Respect `noUncheckedIndexedAccess`; handle possibly undefined values deliberately.
- Use `@/*` inside `apps/web/` when it improves clarity.
- Use App Router patterns in `apps/web/src/app/`.
- Keep components small and composable.
- Default export page/layout components are acceptable where Next.js expects them.

## Python Conventions for AgentOS

- Target Python 3.11.
- Ruff line length is 100.
- Ruff rules include `E`, `F`, `I`, `B`, `UP`.
- Pyright runs in `basic` mode.
- Favor standard library and minimal dependencies unless clearly needed.
- Keep Pixi as the environment and task runner.

## Imports, Naming, Errors

### Imports

- Imports must be sorted; `simple-import-sort/imports` and `simple-import-sort/exports` are enforced as errors.
- Keep type-only imports as type-only.
- Remove unused imports instead of suppressing lint.
- Do not rely on transitive dependencies.

### Naming

- React components: `PascalCase`
- functions and variables: `camelCase`
- constants: `UPPER_SNAKE_CASE` only for real constants
- Next.js route files: follow framework conventions (`page.tsx`, `layout.tsx`)
- Python files and modules: `snake_case`

### Error handling

- Do not swallow errors silently.
- Fail with actionable messages in scripts and config code.
- Handle `undefined`, `null`, and missing config explicitly.
- Prefer early returns over deep nesting.
- Avoid broad catch blocks unless you can recover or improve the error.

## Scope and Hygiene

- Keep changes minimal and relevant.
- Update docs when workflow or commands change.
- If you add a new tool, wire it into scripts and CI in the same change.
- If you add tests, add an explicit single-test command path.
- Do not leave partially configured tooling behind.

## Cursor / Copilot Rules

- No `.cursor/rules/` directory was present when this file was written.
- No `.cursorrules` file was present when this file was written.
- No `.github/copilot-instructions.md` file was present when this file was written.
- If any of those files are added later, update this file to incorporate them.

## Agent Workflow

- Start with the narrowest relevant check.
- End with the strongest relevant check.
- For broad changes, run `pnpm quality`.
- For web changes affecting runtime behavior, also run `pnpm --filter web build`.
- For AgentOS changes, escalate from the relevant Pixi task to `quality` before finishing.
- Before committing, expect local hooks to run and commit messages to be linted.

## Default Safe Finish

- If you changed multiple areas and are unsure what to run, use:
  - `pnpm format`
  - `pnpm quality`
