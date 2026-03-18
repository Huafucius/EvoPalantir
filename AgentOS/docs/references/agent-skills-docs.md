# Agent Skills 官方文档

## 目录

1. [Overview](#overview)
2. [What are skills?](#what-are-skills)
3. [Specification](#specification)
4. [Adding skills support](#adding-skills-support)

---

## Overview

> A simple, open format for giving agents new capabilities and expertise.

Agent Skills are folders of instructions, scripts, and resources that agents can discover and use to do things more accurately and efficiently.

### Why Agent Skills?

Agents are increasingly capable, but often don't have the context they need to do real work reliably. Skills solve this by giving agents access to procedural knowledge and company-, team-, and user-specific context they can load on demand. Agents with access to a set of skills can extend their capabilities based on the task they're working on.

**For skill authors**: Build capabilities once and deploy them across multiple agent products.

**For compatible agents**: Support for skills lets end users give agents new capabilities out of the box.

**For teams and enterprises**: Capture organizational knowledge in portable, version-controlled packages.

### What can Agent Skills enable?

- **Domain expertise**: Package specialized knowledge into reusable instructions, from legal review processes to data analysis pipelines.
- **New capabilities**: Give agents new capabilities (e.g. creating presentations, building MCP servers, analyzing datasets).
- **Repeatable workflows**: Turn multi-step tasks into consistent and auditable workflows.
- **Interoperability**: Reuse the same skill across different skills-compatible agent products.

### Adoption

Agent Skills are supported by leading AI development tools including: Junie, Gemini CLI, Autohand Code CLI, OpenCode, OpenHands, Mux, Cursor, Amp, Letta, Firebender, Goose, GitHub, VS Code, Claude Code, Claude, OpenAI Codex, Piebald, Factory, pi, Databricks, Agentman, TRAE, Spring AI, Roo Code, Mistral AI Vibe, Command Code, Ona, VT Code, Qodo, Laravel Boost, Emdash, Snowflake.

### Open development

The Agent Skills format was originally developed by [Anthropic](https://www.anthropic.com/), released as an open standard, and has been adopted by a growing number of agent products. The standard is open to contributions from the broader ecosystem.

[View on GitHub](https://github.com/agentskills/agentskills)

### Get started

- **What are skills?**: Learn about skills, how they work, and why they matter.
- **Specification**: The complete format specification for SKILL.md files.
- **Add skills support**: Add skills support to your agent or tool.
- **Example skills**: Browse example skills on GitHub.
- **Reference library**: Validate skills and generate prompt XML.

---

## What are skills?

> Agent Skills are a lightweight, open format for extending AI agent capabilities with specialized knowledge and workflows.

At its core, a skill is a folder containing a `SKILL.md` file. This file includes metadata (`name` and `description`, at minimum) and instructions that tell an agent how to perform a specific task. Skills can also bundle scripts, templates, and reference materials.

```
my-skill/
├── SKILL.md          # Required: instructions + metadata
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

### How skills work

Skills use **progressive disclosure** to manage context efficiently:

1. **Discovery**: At startup, agents load only the name and description of each available skill, just enough to know when it might be relevant.
2. **Activation**: When a task matches a skill's description, the agent reads the full `SKILL.md` instructions into context.
3. **Execution**: The agent follows the instructions, optionally loading referenced files or executing bundled code as needed.

This approach keeps agents fast while giving them access to more context on demand.

### The SKILL.md file

Every skill starts with a `SKILL.md` file containing YAML frontmatter and Markdown instructions:

```md
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
---

# PDF Processing

## When to use this skill

Use this skill when the user needs to work with PDF files...

## How to extract text

1. Use pdfplumber for text extraction...

## How to fill forms

...
```

The following frontmatter is required at the top of `SKILL.md`:

- `name`: A short identifier
- `description`: When to use this skill

The Markdown body contains the actual instructions and has no specific restrictions on structure or content.

This simple format has some key advantages:

- **Self-documenting**: A skill author or user can read a `SKILL.md` and understand what it does, making skills easy to audit and improve.
- **Extensible**: Skills can range in complexity from just text instructions to executable code, assets, and templates.
- **Portable**: Skills are just files, so they're easy to edit, version, and share.

### Next steps

- [View the specification](/specification) to understand the full format.
- [Add skills support to your agent](/client-implementation/adding-skills-support) to build a compatible client.
- [See example skills](https://github.com/anthropics/skills) on GitHub.
- [Read authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) for writing effective skills.
- [Use the reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref) to validate skills and generate prompt XML.

---

## Specification

> The complete format specification for Agent Skills.

### Directory structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

### `SKILL.md` format

The `SKILL.md` file must contain YAML frontmatter followed by Markdown content.

#### Frontmatter

| Field           | Required | Constraints                                                                                                       |
| --------------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `name`          | Yes      | Max 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.             |
| `description`   | Yes      | Max 1024 characters. Non-empty. Describes what the skill does and when to use it.                                 |
| `license`       | No       | License name or reference to a bundled license file.                                                              |
| `compatibility` | No       | Max 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.). |
| `metadata`      | No       | Arbitrary key-value mapping for additional metadata.                                                              |
| `allowed-tools` | No       | Space-delimited list of pre-approved tools the skill may use. (Experimental)                                      |

**Minimal example:**

```markdown
---
name: skill-name
description: A description of what this skill does and when to use it.
---
```

**Example with optional fields:**

```markdown
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
license: Apache-2.0
metadata:
  author: example-org
  version: '1.0'
---
```

##### `name` field

The required `name` field:

- Must be 1-64 characters
- May only contain unicode lowercase alphanumeric characters (`a-z`) and hyphens (`-`)
- Must not start or end with a hyphen (`-`)
- Must not contain consecutive hyphens (`--`)
- Must match the parent directory name

**Valid examples:**

```yaml
name: pdf-processing
name: data-analysis
name: code-review
```

**Invalid examples:**

```yaml
name: PDF-Processing  # uppercase not allowed
name: -pdf  # cannot start with hyphen
name: pdf--processing  # consecutive hyphens not allowed
```

##### `description` field

The required `description` field:

- Must be 1-1024 characters
- Should describe both what the skill does and when to use it
- Should include specific keywords that help agents identify relevant tasks

**Good example:**

```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

**Poor example:**

```yaml
description: Helps with PDFs.
```

##### `license` field

The optional `license` field:

- Specifies the license applied to the skill
- We recommend keeping it short (either the name of a license or the name of a bundled license file)

**Example:**

```yaml
license: Proprietary. LICENSE.txt has complete terms
```

##### `compatibility` field

The optional `compatibility` field:

- Must be 1-500 characters if provided
- Should only be included if your skill has specific environment requirements
- Can indicate intended product, required system packages, network access needs, etc.

**Examples:**

```yaml
compatibility: Designed for Claude Code (or similar products)
compatibility: Requires git, docker, jq, and access to the internet
```

> Most skills do not need the `compatibility` field.

##### `metadata` field

The optional `metadata` field:

- A map from string keys to string values
- Clients can use this to store additional properties not defined by the Agent Skills spec
- We recommend making your key names reasonably unique to avoid accidental conflicts

**Example:**

```yaml
metadata:
  author: example-org
  version: '1.0'
```

##### `allowed-tools` field

The optional `allowed-tools` field:

- A space-delimited list of tools that are pre-approved to run
- Experimental. Support for this field may vary between agent implementations

**Example:**

```yaml
allowed-tools: Bash(git:*) Bash(jq:*) Read
```

#### Body content

The Markdown body after the frontmatter contains the skill instructions. There are no format restrictions. Write whatever helps agents perform the task effectively.

Recommended sections:

- Step-by-step instructions
- Examples of inputs and outputs
- Common edge cases

Note that the agent will load this entire file once it's decided to activate a skill. Consider splitting longer `SKILL.md` content into referenced files.

### Optional directories

#### `scripts/`

Contains executable code that agents can run. Scripts should:

- Be self-contained or clearly document dependencies
- Include helpful error messages
- Handle edge cases gracefully

Supported languages depend on the agent implementation. Common options include Python, Bash, and JavaScript.

#### `references/`

Contains additional documentation that agents can read when needed:

- `REFERENCE.md` - Detailed technical reference
- `FORMS.md` - Form templates or structured data formats
- Domain-specific files (`finance.md`, `legal.md`, etc.)

Keep individual reference files focused. Agents load these on demand, so smaller files mean less use of context.

#### `assets/`

Contains static resources:

- Templates (document templates, configuration templates)
- Images (diagrams, examples)
- Data files (lookup tables, schemas)

### Progressive disclosure

Skills should be structured for efficient use of context:

1. **Metadata** (\~100 tokens): The `name` and `description` fields are loaded at startup for all skills
2. **Instructions** (\< 5000 tokens recommended): The full `SKILL.md` body is loaded when the skill is activated
3. **Resources** (as needed): Files (e.g. those in `scripts/`, `references/`, or `assets/`) are loaded only when required

Keep your main `SKILL.md` under 500 lines. Move detailed reference material to separate files.

### File references

When referencing other files in your skill, use relative paths from the skill root:

```markdown
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

Keep file references one level deep from `SKILL.md`. Avoid deeply nested reference chains.

### Validation

Use the [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) reference library to validate your skills:

```bash
skills-ref validate ./my-skill
```

This checks that your `SKILL.md` frontmatter is valid and follows all naming conventions.

---

## Adding skills support

> A guide for adding Agent Skills support to an AI agent or development tool.

This guide walks through how to add Agent Skills support to an AI agent or development tool. It covers the full lifecycle: discovering skills, telling the model about them, loading their content into context, and keeping that content effective over time.

The core integration is the same regardless of your agent's architecture. The implementation details vary based on two factors:

- **Where do skills live?** A locally-running agent can scan the user's filesystem for skill directories. A cloud-hosted or sandboxed agent will need an alternative discovery mechanism — an API, a remote registry, or bundled assets.
- **How does the model access skill content?** If the model has file-reading capabilities, it can read `SKILL.md` files directly. Otherwise, you'll provide a dedicated tool or inject skill content into the prompt programmatically.

The guide notes where these differences matter. You don't need to support every scenario — follow the path that fits your agent.

**Prerequisites**: Familiarity with the [Agent Skills specification](/specification), which defines the `SKILL.md` file format, frontmatter fields, and directory conventions.

### The core principle: progressive disclosure

Every skills-compatible agent follows the same three-tier loading strategy:

| Tier            | What's loaded               | When                                 | Token cost                 |
| --------------- | --------------------------- | ------------------------------------ | -------------------------- |
| 1. Catalog      | Name + description          | Session start                        | ~50-100 tokens per skill   |
| 2. Instructions | Full `SKILL.md` body        | When the skill is activated          | <5000 tokens (recommended) |
| 3. Resources    | Scripts, references, assets | When the instructions reference them | Varies                     |

The model sees the catalog from the start, so it knows what skills are available. When it decides a skill is relevant, it loads the full instructions. If those instructions reference supporting files, the model loads them individually as needed.

This keeps the base context small while giving the model access to specialized knowledge on demand. An agent with 20 installed skills doesn't pay the token cost of 20 full instruction sets upfront — only the ones actually used in a given conversation.

### Step 1: Discover skills

At session startup, find all available skills and load their metadata.

#### Where to scan

Which directories you scan depends on your agent's environment. Most locally-running agents scan at least two scopes:

- **Project-level** (relative to the working directory): Skills specific to a project or repository.
- **User-level** (relative to the home directory): Skills available across all projects for a given user.

Other scopes are possible too — for example, organization-wide skills deployed by an admin, or skills bundled with the agent itself. The right set of scopes depends on your agent's deployment model.

Within each scope, consider scanning both a **client-specific directory** and the **`.agents/skills/` convention**:

| Scope   | Path                               | Purpose                       |
| ------- | ---------------------------------- | ----------------------------- |
| Project | `<project>/.<your-client>/skills/` | Your client's native location |
| Project | `<project>/.agents/skills/`        | Cross-client interoperability |
| User    | `~/.<your-client>/skills/`         | Your client's native location |
| User    | `~/.agents/skills/`                | Cross-client interoperability |

The `.agents/skills/` paths have emerged as a widely-adopted convention for cross-client skill sharing. While the Agent Skills specification does not mandate where skill directories live (it only defines what goes inside them), scanning `.agents/skills/` means skills installed by other compliant clients are automatically visible to yours, and vice versa.

> Some implementations also scan `.claude/skills/` (both project-level and user-level) for pragmatic compatibility, since many existing skills are installed there. Other additional locations include ancestor directories up to the git root (useful for monorepos), [XDG](https://specifications.freedesktop.org/basedir-spec/latest/) config directories, and user-configured paths.

#### What to scan for

Within each skills directory, look for **subdirectories containing a file named exactly `SKILL.md`**:

```
~/.agents/skills/
├── pdf-processing/
│   ├── SKILL.md          ← discovered
│   └── scripts/
│       └── extract.py
├── data-analysis/
│   └── SKILL.md          ← discovered
└── README.md             ← ignored (not a skill directory)
```

Practical scanning rules:

- Skip directories that won't contain skills, such as `.git/` and `node_modules/`
- Optionally respect `.gitignore` to avoid scanning build artifacts
- Set reasonable bounds (e.g., max depth of 4-6 levels, max 2000 directories) to prevent runaway scanning in large directory trees

#### Handling name collisions

When two skills share the same `name`, apply a deterministic precedence rule.

The universal convention across existing implementations: **project-level skills override user-level skills.**

Within the same scope (e.g., two skills named `code-review` found under both `<project>/.agents/skills/` and `<project>/.<your-client>/skills/`), either first-found or last-found is acceptable — pick one and be consistent. Log a warning when a collision occurs so the user knows a skill was shadowed.

#### Trust considerations

Project-level skills come from the repository being worked on, which may be untrusted (e.g., a freshly cloned open-source project). Consider gating project-level skill loading on a trust check — only load them if the user has marked the project folder as trusted. This prevents untrusted repositories from silently injecting instructions into the agent's context.

#### Cloud-hosted and sandboxed agents

If your agent runs in a container or on a remote server, it won't have access to the user's local filesystem. Discovery needs to work differently depending on the skill scope:

- **Project-level skills** are often the easiest case. If the agent operates on a cloned repository (even inside a sandbox), project-level skills travel with the code and can be scanned from the repo's directory tree.
- **User-level and organization-level skills** don't exist in the sandbox. You'll need to provision them from an external source — for example, cloning a configuration repository, accepting skill URLs or packages through your agent's settings, or letting users upload skill directories through a web UI.
- **Built-in skills** can be packaged as static assets within the agent's deployment artifact, making them available in every session without external fetching.

Once skills are available to the agent, the rest of the lifecycle — parsing, disclosure, activation — works the same.

### Step 2: Parse `SKILL.md` files

For each discovered `SKILL.md`, extract the metadata and body content.

#### Frontmatter extraction

A `SKILL.md` file has two parts: YAML frontmatter between `---` delimiters, and a markdown body after the closing delimiter. To parse:

1. Find the opening `---` at the start of the file and the closing `---` after it.
2. Parse the YAML block between them. Extract `name` and `description` (required), plus any optional fields.
3. Everything after the closing `---`, trimmed, is the skill's body content.

See the [specification](/specification) for the full set of frontmatter fields and their constraints.

#### Handling malformed YAML

Skill files authored for other clients may contain technically invalid YAML that their parsers happen to accept. The most common issue is unquoted values containing colons:

```yaml
# Technically invalid YAML — the colon breaks parsing
description: Use this skill when: the user asks about PDFs
```

Consider a fallback that wraps such values in quotes or converts them to YAML block scalars before retrying. This improves cross-client compatibility at minimal cost.

#### Lenient validation

Warn on issues but still load the skill when possible:

- Name doesn't match the parent directory name → warn, load anyway
- Name exceeds 64 characters → warn, load anyway
- Description is missing or empty → skip the skill (a description is essential for disclosure), log the error
- YAML is completely unparseable → skip the skill, log the error

Record diagnostics so they can be surfaced to the user (in a debug command, log file, or UI), but don't block skill loading on cosmetic issues.

> The [specification](/specification) defines strict constraints on the `name` field (matching the parent directory, character set, max length). The lenient approach above deliberately relaxes these to improve compatibility with skills authored for other clients.

#### What to store

At minimum, each skill record needs three fields:

| Field         | Description                          |
| ------------- | ------------------------------------ |
| `name`        | From frontmatter                     |
| `description` | From frontmatter                     |
| `location`    | Absolute path to the `SKILL.md` file |

Store these in an in-memory map keyed by `name` for fast lookup during activation.

You can also store the **body** (the markdown content after the frontmatter) at discovery time, or read it from `location` at activation time. Storing it makes activation faster; reading it at activation time uses less memory in aggregate and picks up changes to skill files between activations.

The skill's **base directory** (the parent directory of `location`) is needed later to resolve relative paths and enumerate bundled resources — derive it from `location` when needed.

### Step 3: Disclose available skills to the model

Tell the model what skills exist without loading their full content. This is [tier 1 of progressive disclosure](#the-core-principle-progressive-disclosure).

#### Building the skill catalog

For each discovered skill, include `name`, `description`, and optionally `location` (the path to the `SKILL.md` file) in whatever structured format suits your stack — XML, JSON, or a bulleted list all work:

```xml
<available_skills>
  <skill>
    <name>pdf-processing</name>
    <description>Extract PDF text, fill forms, merge files. Use when handling PDFs.</description>
    <location>/home/user/.agents/skills/pdf-processing/SKILL.md</location>
  </skill>
  <skill>
    <name>data-analysis</name>
    <description>Analyze datasets, generate charts, and create summary reports.</description>
    <location>/home/user/project/.agents/skills/data-analysis/SKILL.md</location>
  </skill>
</available_skills>
```

The `location` field serves two purposes: it enables file-read activation (see [Step 4](#step-4-activate-skills)), and it gives the model a base path for resolving relative references in the skill body (like `scripts/evaluate.py`). If your dedicated activation tool provides the skill directory path in its result (see [Structured wrapping](#structured-wrapping) in Step 4), you can omit `location` from the catalog. Otherwise, include it.

Each skill adds roughly 50-100 tokens to the catalog. Even with dozens of skills installed, the catalog remains compact.

#### Where to place the catalog

Two approaches are common:
**System prompt section**: Add the catalog as a labeled section in the system prompt, preceded by brief instructions on how to use skills. This is the simplest approach and works with any model that has access to a file-reading tool.
**Tool description**: Embed the catalog in the description of a dedicated skill-activation tool (see [Step 4](#step-4-activate-skills)). This keeps the system prompt clean and naturally couples discovery with activation.

Both work. System prompt placement is simpler and more broadly compatible; tool description embedding is cleaner when you have a dedicated activation tool.

#### Behavioral instructions

Include a short instruction block alongside the catalog telling the model how and when to use skills. The wording depends on which activation mechanism you support (see [Step 4](#step-4-activate-skills)):

**If the model activates skills by reading files:**

```
The following skills provide specialized instructions for specific tasks.
When a task matches a skill's description, use your file-read tool to load
the SKILL.md at the listed location before proceeding.
When a skill references relative paths, resolve them against the skill's
directory (the parent of SKILL.md) and use absolute paths in tool calls.
```

**If the model activates skills via a dedicated tool:**

```
The following skills provide specialized instructions for specific tasks.
When a task matches a skill's description, call the activate_skill tool
with the skill's name to load its full instructions.
```

Keep these instructions concise. The goal is to tell the model that skills exist and how to load them — the skill content itself provides the detailed instructions once loaded.

#### Filtering

Some skills should be excluded from the catalog. Common reasons:

- The user has disabled the skill in settings
- A permission system denies access to the skill
- The skill has opted out of model-driven activation (e.g., via a `disable-model-invocation` flag)

**Hide filtered skills entirely** from the catalog rather than listing them and blocking at activation time. This prevents the model from wasting turns attempting to load skills it can't use.

#### When no skills are available

If no skills are discovered, omit the catalog and behavioral instructions entirely. Don't show an empty `<available_skills/>` block or register a skill tool with no valid options — this would confuse the model.

### Step 4: Activate skills

When the model or user selects a skill, deliver the full instructions into the conversation context. This is [tier 2 of progressive disclosure](#the-core-principle-progressive-disclosure).

#### Model-driven activation

Most implementations rely on the model's own judgment as the activation mechanism, rather than implementing harness-side trigger matching or keyword detection. The model reads the catalog (from [Step 3](#step-3-disclose-available-skills-to-the-model)), decides a skill is relevant to the current task, and loads it.

Two implementation patterns:
**File-read activation**: The model calls its standard file-read tool with the `SKILL.md` path from the catalog. No special infrastructure needed — the agent's existing file-reading capability is sufficient. The model receives the file content as a tool result. This is the simplest approach when the model has file access.
**Dedicated tool activation**: Register a tool (e.g., `activate_skill`) that takes a skill name and returns the content. This is required when the model can't read files directly, and optional (but useful) even when it can. Advantages over raw file reads:

- Control what content is returned — e.g., strip YAML frontmatter or preserve it (see [What the model receives](#what-the-model-receives) below)
- Wrap content in structured tags for identification during context management
- List bundled resources (e.g., `references/*`) alongside the instructions
- Enforce permissions or prompt for user consent
- Track activation for analytics

> If you use a dedicated activation tool, constrain the `name` parameter to the set of valid skill names (e.g., as an enum in the tool schema). This prevents the model from hallucinating nonexistent skill names. If no skills are available, don't register the tool at all.

#### User-explicit activation

Users should also be able to activate skills directly, without waiting for the model to decide. The most common pattern is a **slash command or mention syntax** (`/skill-name` or `$skill-name`) that the harness intercepts. The specific syntax is up to you — the key idea is that the harness handles the lookup and injection, so the model receives skill content without needing to take an activation action itself.

An autocomplete widget (listing available skills as the user types) can also make this discoverable.

#### What the model receives

When a skill is activated, the model receives the skill's instructions. Two options for what exactly that content looks like:
**Full file**: The model sees the entire `SKILL.md` including YAML frontmatter. This is the natural outcome with file-read activation, where the model reads the raw file. It's also a valid choice for dedicated tools. The frontmatter may contain fields useful at activation time — for example, [`compatibility`](/specification#compatibility-field) notes environment requirements that could inform how the model executes the skill's instructions.
**Body only (frontmatter stripped)**: The harness parses and removes the YAML frontmatter, returning only the markdown instructions. Among existing implementations with dedicated activation tools, most take this approach — stripping the frontmatter after extracting `name` and `description` during discovery.

Both approaches work in practice.

#### Structured wrapping

If you use a dedicated activation tool, consider wrapping skill content in identifying tags. For example:

```xml
<skill_content name="pdf-processing">
# PDF Processing

## When to use this skill
Use this skill when the user needs to work with PDF files...

[rest of SKILL.md body]

Skill directory: /home/user/.agents/skills/pdf-processing
Relative paths in this skill are relative to the skill directory.

<skill_resources>
  <file>scripts/extract.py</file>
  <file>scripts/merge.py</file>
  <file>references/pdf-spec-summary.md</file>
</skill_resources>
</skill_content>
```

This has practical benefits:

- The model can clearly distinguish skill instructions from other conversation content
- The harness can identify skill content during context compaction ([Step 5](#step-5-manage-skill-context-over-time))
- Bundled resources are surfaced to the model without being eagerly loaded

#### Listing bundled resources

When a dedicated activation tool returns skill content, it can also enumerate supporting files (scripts, references, assets) in the skill directory — but it should **not eagerly read them**. The model loads specific files on demand using its file-read tools when the skill's instructions reference them.

For large skill directories, consider capping the listing and noting that it may be incomplete.

#### Permission allowlisting

If your agent has a permission system that gates file access, **allowlist skill directories** so the model can read bundled resources without triggering user confirmation prompts. Without this, every reference to a bundled script or reference file results in a permission dialog, breaking the flow for skills that include resources beyond the `SKILL.md` itself.

### Step 5: Manage skill context over time

Once skill instructions are in the conversation context, keep them effective for the duration of the session.

#### Protect skill content from context compaction

If your agent truncates or summarizes older messages when the context window fills up, **exempt skill content from pruning**. Skill instructions are durable behavioral guidance — losing them mid-conversation silently degrades the agent's performance without any visible error. The model continues operating but without the specialized instructions the skill provided.

Common approaches:

- Flag skill tool outputs as protected so the pruning algorithm skips them
- Use the [structured tags](#structured-wrapping) from Step 4 to identify skill content and preserve it during compaction

#### Deduplicate activations

Consider tracking which skills have been activated in the current session. If the model (or user) attempts to load a skill that's already in context, you can skip the re-injection to avoid the same instructions appearing multiple times in the conversation.

#### Subagent delegation (optional)

This is an advanced pattern only supported by some clients. Instead of injecting skill instructions into the main conversation, the skill is run in a **separate subagent session**. The subagent receives the skill instructions, performs the task, and returns a summary of its work to the main conversation.

This pattern is useful when a skill's workflow is complex enough to benefit from a dedicated, focused session.
