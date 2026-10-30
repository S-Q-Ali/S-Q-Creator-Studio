# Plan — remove useless files from the repo

Audit date: 2026-10-30. Read-only audit; **nothing is deleted until this plan
is approved**. Deletions use `git rm`, so every file stays recoverable from
history.

## Findings

| # | What | Count | Size | Evidence | Action |
|---|---|---|---|---|---|
| 1 | Root session summaries: `ALL_FIXED_PUSHED.md`, `CI_FIX_FINAL.md`, `CI_FIX_SUMMARY.md`, `COMMIT_SUMMARY.md`, `FINAL_SUMMARY.md`, `FIXES_SUMMARY.md`, `PRODUCTION_READY_PLAN.md`, `RATE_LIMITING_FIX.md`, `SKILLS_READY.md`, `SOCIAL_DISCOVERY_FIXES.md`, `TEST_RESULTS.md`, `TEST_SUMMARY_HI.md` | 12 | 64 KB | last touched 2026-10-25/26; referenced only by each other and by generated graph reports; not by README, CONTRIBUTING, AGENTS or CI | delete |
| 2 | Root one-off scripts: `validate_fixes.py`, `validate_tests.py`, `run_comprehensive_tests.py` | 3 | 10 KB | no reference anywhere; `validate_fixes.py` writes a test row into the **real** settings store (`configure(None)`), which breaks the store-isolation rule; pytest covers all three | delete |
| 3 | `.github/ISSUE_TEMPLATE.md` | 1 | ~1 KB | legacy single-file template; GitHub uses `.github/ISSUE_TEMPLATE/*.md`, so this copy is ignored | delete |
| 4 | Unused screenshots: `main_window.png`, `queue_tab.png`, `settings_tab.png`, `portable_v270_queue.png`, `portable_v270_queue_card.png`, `real_*_zoom.png` (6) | 11 | 468 KB | README uses only `interface.png`, `settings.png`, `social-discovery.png`, `compact.png` | delete |
| 5 | `graphify-out/2026-*` timestamped backups | 11 dirs | 41 MB | each `graphify update` writes a backup; the live graph is `graphify-out/graph.json` + `GRAPH_REPORT.md` + `graph.html`, all still tracked | delete all dated dirs, ignore future ones |
| 6 | `.gitignore` gaps | — | — | `tasks/spike_*.py` misses `tasks/spike_*.png` (one is untracked today) and the planned spike JSON | ignore `tasks/spike_*` |

Total: **27 files + 11 directories, ~41.5 MB** removed from the working tree.

## Keep (deliberately)

- `.opencode/` (278 files): local skill packs referenced by `AGENTS.md`.
- `release/` (3 files): build script, installer script, README.
- Root `SPEC-*.md` (6): referenced by the completed plans in `tasks/`.
- `tasks/*.md` (27): project design history; the active one is
  `todo-tiktok-session-search.md`. No deletion proposed.
- `themes/*.html` (2, 56 KB): unreferenced, but the original neon-theme design
  mockups — ask before removing.
- The 4 screenshots README links to.

## Tasks

### Task 1: delete the stale documents and scripts
**Acceptance:** the 15 files in findings 1–2 are gone; `git grep` for each
name returns no hit outside generated `graphify-out` reports (refreshed in
Task 4).
**Verify:** `git grep -lE "ALL_FIXED_PUSHED|CI_FIX_FINAL|CI_FIX_SUMMARY|COMMIT_SUMMARY|FINAL_SUMMARY|FIXES_SUMMARY|PRODUCTION_READY_PLAN|RATE_LIMITING_FIX|SKILLS_READY|SOCIAL_DISCOVERY_FIXES|TEST_RESULTS|TEST_SUMMARY_HI|validate_fixes|validate_tests|run_comprehensive_tests"`.
**Files:** the 15 root files.

- [ ] 12 summaries deleted
- [ ] 3 scripts deleted
- [ ] No reference left

### Task 2: templates and screenshots
**Acceptance:** `.github/ISSUE_TEMPLATE.md` gone; the 11 unused screenshots
gone; the 4 README images and all three issue templates remain.
**Verify:** README image links resolve; `gh issue create --dry-run` not needed —
the template folder is untouched.
**Files:** `.github/ISSUE_TEMPLATE.md`, `screenshots/`.

- [ ] Legacy template deleted
- [ ] 11 screenshots deleted
- [ ] 4 README screenshots still present

### Task 3: graph history and ignore rules
**Acceptance:** `graphify-out/2026-*` removed from the tree and ignored;
`graphify-out/graph.json`, `graph.html`, `GRAPH_REPORT.md`, `manifest.json`
still tracked; `.gitignore` covers `tasks/spike_*` (all extensions) and
`graphify-out/20*/`.
**Verify:** `git ls-files graphify-out | head`; `graphify update .` still
writes locally without dirtying the tree.
**Files:** `graphify-out/`, `.gitignore`.

- [ ] Dated backups removed
- [ ] Live graph still tracked
- [ ] Ignore rules updated

### Task 4: verify and commit
**Acceptance:** ruff clean; offline suite green; README renders its four
images; graph refreshed; one atomic commit per task.
**Verify:** `./source/venv/Scripts/python.exe -m ruff check src tests`;
`QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"`;
`graphify update .`.

- [ ] Ruff
- [ ] Suite
- [ ] Graph refresh
- [ ] Commits

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A deleted summary held context not in git history | Low | `git rm` keeps every blob; `git show <sha>:<file>` restores |
| Graph reports still name deleted docs | Low | `graphify update .` regenerates them in Task 4 |
| Removing `.github/ISSUE_TEMPLATE.md` changes issue forms | None | the folder templates are what GitHub reads |
| Deleting graph backups loses a recovery point | Low | the live graph and its git history remain; backups are local convenience |
| Working tree shrinks but `.git` does not | None | pack size only drops after a history rewrite, which is **not** proposed |

## Ask first (not in scope)

- `themes/*.html` (2 mockups): delete or keep as design history?
- `tasks/*.md` (27): move completed plans/specs into `tasks/archive/`?
- `.opencode/` (69 MB): prune skill packs no longer used?
