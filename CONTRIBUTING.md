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
- `src/s_q_ali_media_downloader/core/` — the parts that are not a feature: the secret store (API keys, sealed with DPAPI), the YouTube client, the exporter.
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
- Use the single dark ink-plum/cyan palette for any UI work — `theme.py` holds
  the palette and the one stylesheet, and it has a compact variant that the
  app switches to on a small screen. There is no second theme anymore.
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

Maintainers cut releases by tagging (`v2.6.1`, …). The tag triggers the CI
release pipeline: lint, tests, pip-audit, then a portable build published as a
GitHub Release asset, with the Inno installer built the same way. To build it
on your own machine instead, run `release\build.bat` — see `release/README.md`
for what it needs.
