# Contributing

Thanks for helping out! This project is small but open to everyone. Here's how to get going.

## Setup

```powershell
git clone https://github.com/S-Q-Ali/S-Q-Creator-Studio.git
cd S-Q-Creator-Studio
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Running checks

```powershell
pytest                # 390+ tests incl. full offscreen GUI smoke suite
ruff check src tests  # lint
```

Everything must pass before a PR is merged. CI runs lint, tests, and a
`pip-audit` dependency scan on Windows.

## Code layout

- `src/s_q_ali_media_downloader/engine.py` — download engine and URL helpers (no UI code).
- `src/s_q_ali_media_downloader/theme.py` — palette and stylesheet.
- `src/s_q_ali_media_downloader/app.py` — application entry point.
- `src/s_q_ali_media_downloader/ui/` — `main_window.py` (window + wiring) and `widgets.py` (cards, chips, drawing helpers).
- `src/s_q_ali_media_downloader/agent/` — AI Channel Finder: discovery orchestrator, typed schemas, social verification tools.
- `src/s_q_ali_media_downloader/niche_research/` — Research suite (keyword/trending/scorecard pages, engines, storage); themes under `ui/theme.py`.
- `tests/` — pytest suite. Keep it green; add tests alongside new behaviour.

## Guidelines

- Keep engine logic free of UI imports so it stays unit-testable.
- Keep `curl_cffi` in the `>=0.15.0,<0.18` range in `requirements.txt` /
  `pyproject.toml` — newer curl_cffi is not yet supported by yt-dlp's
  impersonation.
- Do not commit build artifacts (`dist/`, `_internal/`, `release/*`,
  installer outputs) or virtual environments — see `.gitignore`.
- Do not commit secrets, API keys, session exports, or personal `opencode.json`
  files (all ignored).
- Use the single dark ink-plum/cyan palette for any UI work — `theme.py` for
  the downloader, `niche_research/ui/theme.py` for the research suite. There is
  no second light/research theme anymore.
- Research QSS: any selector you add must render inside
  `research_style()` and is covered by `tests/test_qss_parses.py`.

## Pull requests

1. Fork the repo and create a branch (`feature/…` or `fix/…`).
2. Make your change and add/update tests.
3. Run `pytest` and `ruff check src tests`.
4. Open a PR from the template. Reference the issue it fixes, if any.

## Releases

Maintainers cut releases by tagging (`v2.1.0`, …). The tag triggers the CI
release pipeline: lint, tests, pip-audit, then a portable build published as a
GitHub Release asset. The Inno installer is produced locally with
`build_release.bat` (PyInstaller + Inno Setup) and uploaded alongside it.
