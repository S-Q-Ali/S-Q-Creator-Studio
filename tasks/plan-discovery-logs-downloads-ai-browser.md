# Plan — four discovery/download improvements

## Increment 1 — CI artifact truth

- Upload `release\portable` as `portable-build`.
- Keep `if-no-files-found: error`; update the comment.

## Increment 2 — Gemini after Groq

- `social_judge`: add Gemini constants, `gemini_key()`, `_post_gemini()`,
  `_gemini_text()`, `test_gemini_key()`, and a `_propose_with_*` pair.
- `propose()` becomes the provider chain (Groq → Gemini).
- `Proposal.provider` / `model` / `tokens`.
- Settings: Gemini row + Test worker + unreadable warning.
- Tests first: chain order, fallback, no keys, response parsing.

## Increment 3 — Facebook / Instagram downloads

- `engine`: `is_facebook_url`, `is_instagram_url`, `platform_of`.
- `tidy_error`: login-gated messages.
- `main_window.add_links`: admit both; update hint/status.
- Tests first: accepted/rejected URL shapes, queue count, platform label.

## Increment 4 — Visible logs

- `ui/activity_log.py`: capped read-only panel with timestamps + Clear.
- `AgentTabWidget`: panel visible in all three modes; connect worker `log`.
- `AgentWorkerThread`: `log` signal; orchestrator `log_callback`.
- `AgentOrchestrator`: step logs for search, metadata, each platform probe,
  AI/browser use, completion.
- `SocialDiscoveryPage`: `log` signal; worker emits every progress line.
- `social_discovery` / `social_resolve` / `social_verify`: `logger.info` at
  each step; AI provider hand-off.
- Tests first: orchestrator emits mode/AI lines; page forwards worker lines.

## Increment 5 — Real browser accuracy

- `browser`: `profile_dir`, `headless`, `channel` options;
  `launch_persistent_context` when a profile is given; default profile path;
  channel order Chrome → Edge → shipped Chromium.
- `social_discovery_page`: pass persistent profile + show-browser setting.
- `settings_page`: "Show browser during discovery" checkbox.
- `social_verifier`: optional rendered-page fallback for INCONCLUSIVE
  probes, run in one dedicated executor thread.
- `orchestrator`: create/close the verifier browser; log browser fallback.
- Tests: persistent-context option wiring, fallback maps FOUND/NOT_FOUND,
  no browser when HTTP is decisive.

## Verification

1. `pytest -m "not live"` after every increment.
2. `ruff check src tests`.
3. `python -m pip_audit`.
4. Push; watch CI build and smoke test.
5. User rebuilds locally and signs in once in the shown browser.
