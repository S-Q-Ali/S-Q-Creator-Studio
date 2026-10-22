# Agent Skills + Graphify + Ponytail

This project uses skills installed under `.opencode/skills/` and a knowledge graph at `graphify-out/`.

## Core Rules

- If a task matches a skill, invoke it with the `skill` tool before acting.
- Skills are located in `.opencode/skills/<skill-name>/SKILL.md`.
- Follow the skill workflow strictly; do not partially apply it.
- Never skip required steps such as spec, plan, or test when a skill demands them.
- Shared reference checklists live at `.opencode/references/` (skills reference them via `../../references/`).

## Working Style — Ponytail

Adapted from [Ponytail](https://github.com/DietrichGebert/ponytail) (MIT), vendored under
`.opencode/skills/ponytail*/` with the commands in `.opencode/command/`.

Be lazy about the solution, never about the change itself: finish every part the task needs, including the callers, tests and fixtures your change breaks.

Take the first option that fully works:

1. Does it need to exist? Skip features nobody asked for, and name them in one line.
2. Already in this codebase? Use it the way the surrounding code does.
3. Standard library or a platform feature? Use it, unless the project has its own.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise: the minimum code that works.

- No abstraction, wrapper, option, config or "for later" code nobody asked for. Deletion beats addition. Keep the structure the codebase already has.
- The shortest working diff wins, once you know everything it must touch. A one-liner that needs decoding is not short.
- Comment only the why the code cannot show, in one line.
- Bug fix: grep every caller of the function you touch, then fix the root cause once in the shared code.
- Code you move or merge keeps its error handling and validation.
- New non-trivial logic (a branch, a loop, a parser, money or security) leaves one small test behind. Trivial changes need none.
- A deliberate shortcut gets a comment in this form: `shortcut: <the limit>, <when to upgrade>`.

Never cut: validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs, anything the user asked for.

End a reply with one or two lines: what was skipped or not checked, and any risk the user must know.

## Intent to Skill Mapping

Map the user's intent to the matching skill automatically:

- Feature / new functionality: `spec-driven-development`, then `incremental-implementation` + `test-driven-development`
- Planning / breakdown: `planning-and-task-breakdown`
- Bug / failure / unexpected behavior: `debugging-and-error-recovery`
- Code review: `code-review-and-quality`, or `ponytail-review` for a change and `ponytail-audit` for the whole repo
- Refactoring / simplification: `ponytail` + `code-simplification`
- What can be deleted or merged: `ponytail-audit`
- Deliberate shortcuts taken and deferred: `ponytail-debt`
- API or interface design: `api-and-interface-design`
- UI work / design language: `frontend-design` (craft/anti-slop, Anthropic) + `frontend-ui-engineering` (component engineering, Addy pack)
- Design system / theme / tokens / brand: `theme-factory` (palette+type) + `brand-guidelines` (token-system pattern only — never Anthropic brand data)
- Visual craftsmanship audit: `canvas-design`
- Security concerns: `security-and-hardening`
- Performance issues: `performance-optimization`
- Claude API / LLM client code: `claude-api`
- MCP server / tool integration: `mcp-builder`
- Writing a new skill: `skill-creator`
- Web artifact / React-TS prototypes: `web-artifacts-builder` (web-only)
- Web app browser testing / Playwright: `webapp-testing` (web-only; for Qt GUIs use offscreen GUI smoke tests instead)
- Git / versioning: `git-workflow-and-versioning`
- CI/CD / automation: `ci-cd-and-automation`
- Deprecation / migration: `deprecation-and-migration`
- Documentation / ADRs: `documentation-and-adrs`
- Observability / telemetry: `observability-and-instrumentation`
- Shipping / launch: `shipping-and-launch`
- Codebase architecture questions: use `graphify query/path/explain` (see below)
- Web performance audit: `performance-optimization` or `/webperf`
- Requirements clarification: `interview-me` or `idea-refine`

## Execution Model

For every request:

1. Determine if any skill applies (even a small chance).
2. Load the skill with `skill({ name: "<skill-name>" })`.
3. Follow the skill workflow exactly.
4. Only proceed to implementation once required steps are complete.

## Graphify Knowledge Graph

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
