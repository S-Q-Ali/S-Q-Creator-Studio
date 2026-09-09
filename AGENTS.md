# Agent Skills + Graphify

This project uses skills installed under `.opencode/skills/` and a knowledge graph at `graphify-out/`.

## Core Rules

- If a task matches a skill, invoke it with the `skill` tool before acting.
- Skills are located in `.opencode/skills/<skill-name>/SKILL.md`.
- Follow the skill workflow strictly; do not partially apply it.
- Never skip required steps such as spec, plan, or test when a skill demands them.
- Shared reference checklists live at `.opencode/references/` (skills reference them via `../../references/`).

## Intent to Skill Mapping

Map the user's intent to the matching skill automatically:

- Feature / new functionality: `spec-driven-development`, then `incremental-implementation` + `test-driven-development`
- Planning / breakdown: `planning-and-task-breakdown`
- Bug / failure / unexpected behavior: `debugging-and-error-recovery`
- Code review: `code-review-and-quality`
- Refactoring / simplification: `code-simplification`
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
