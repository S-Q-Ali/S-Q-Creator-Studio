# Contributing

Thanks for helping out! This project is small but open to everyone. Here's how to get going.

## Setup

Needs Python 3.12 or newer — the versions CI runs are 3.12 and 3.14.

```powershell
git clone https://github.com/S-Q-Ali/S-Q-Creator-Studio.git
cd S-Q-Creator-Studio
python -m venv .venv
.\.venv\Scripts\activate      # Linux and macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Running checks

```powershell
pytest -m "not live"        # the offline suite, incl. the offscreen GUI smoke tests
ruff check src tests        # lint
```

Everything must pass before a PR is merged. Every push to `master` runs the full
matrix — lint and the offline suite on Windows, Ubuntu 24.04 and macOS 15, at
Python 3.12 and 3.14 — and on each OS's 3.14 cell also runs a `pip-audit`
dependency scan, builds the portable app and launches it. A pull request gets the
faster version: Ubuntu and Windows at 3.14. The `live` tests hit the video
platforms' servers, so they never run in CI; run them yourself with `pytest -m
live`.

## How the agent works here

`AGENTS.md` is the house style: the smallest change that fully solves the
task, and never a shortcut around validation, error handling, security or
accessibility. It is adapted from [Ponytail](https://github.com/DietrichGebert/ponytail)
(MIT), whose skills live in `.opencode/skills/ponytail*/` and whose
commands are in `.opencode/command/`:

| Command | What it does |
|---|---|
| `/ponytail lite\|full\|ultra\|off` | Set the intensity for the session. |
| `/ponytail-review` | Review a change like the senior dev who gets paged when it breaks. |
| `/ponytail-audit` | The same check for the whole repo, most important first. |
| `/ponytail-debt` | List the `shortcut:` comments you deferred, so "later" does not become "never". |

The same six are skills, so they can be invoked by name as well.

## Code layout

- `src/s_q_ali_media_downloader/engine.py` — download engine and URL helpers (no UI code).
- `src/s_q_ali_media_downloader/theme.py` — palette, density tokens, and stylesheet.
- `src/s_q_ali_media_downloader/app.py` — application entry point.
- `src/s_q_ali_media_downloader/ui/` — `main_window.py` (window + queue wiring), `music_page.py` (music workspace), `vertical_studio_page.py` (local 9:16 reframe + shorts splitter), `agent_tab.py` (AI Channel Finder container), `social_discovery_page.py` (cross-platform social account verifier), `settings_page.py` (preferences + sealed keys), and `widgets.py` (cards, chips, drawing helpers).
- `src/s_q_ali_media_downloader/agent/` — AI Channel Finder: discovery orchestrator, typed schemas, social verification tools.
- `src/s_q_ali_media_downloader/core/` — shared non-UI modules: `settings_store.py` (API keys sealed with DPAPI on Windows and OS keychains via `keyring` elsewhere), `music.py`, `reframe.py`, `shorts.py`, `studio.py`, `social_discovery.py`, `youtube_client.py`, and `exporter.py`.
- `tests/` — pytest suite. Keep it green; add tests alongside new behaviour.

## Guidelines

- Keep engine logic free of UI imports so it stays unit-testable.
- Keep `curl_cffi` in the `>=0.15,<0.16` range in `requirements.txt` /
  `pyproject.toml` — newer curl_cffi is not yet supported by yt-dlp's
  impersonation.
- Do not commit build artifacts (`dist/`, `_internal/`, `release/*`,
  installer outputs) or virtual environments — see `.gitignore`.
- Do not commit secrets, API keys, session exports, or personal `opencode.json`
  files (all ignored).
- Use the single dark glass palette (black, white, grey and one blue) in `theme.py`
  for any UI work — `theme.py` holds the palette and the one stylesheet, with
  `comfortable` and `compact` densities that scale from a shared token set.
- Any selector you add to the stylesheet must parse cleanly — that is
  covered by `tests/test_qss_parses.py`.

## Pull requests

1. Fork the repo and create a branch (`feature/…` or `fix/…`).
2. Make your change and add/update tests.
3. Run `pytest` and `ruff check src tests`.
4. Open a PR from the template. Reference the issue it fixes, if any.

## Releases

Everything about a release lives in `release/` — the build script, the
installer definition, and a README that says how to run it.

Maintainers cut releases by tagging (`v2.19.0`, …). The tag triggers the CI
release pipeline: lint, tests, pip-audit, then platform builds (`python release/build.py`)
published as GitHub Release assets across Windows (`.exe` installer + `.zip`),
Linux (`.tar.gz`), and macOS (`arm64` and `x64` `.dmg` + `.tar.gz`). To build it
on your own machine instead, run `python release/build.py` (or `release\build.bat`
on Windows) — see `release/README.md` for what it needs.
