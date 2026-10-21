# Security Policy

## Reporting a vulnerability

Please report security issues privately instead of opening a public issue.

Use GitHub's **private vulnerability reporting**:

1. Go to https://github.com/S-Q-Ali/Bulk-Video-Downloader/security/advisories
2. Click **New draft security advisory**
3. Describe the issue, the affected version, and a minimal reproduction.

You'll get an acknowledgment within a few days. Please do not disclose the
issue publicly until it has been addressed.

## Scope

In scope:

- Remote code execution or arbitrary file write from a crafted URL or filename.
- Credential/key leakage in the shipped application or repository.
- Unexpected network behaviour that exposes user data.

Out of scope:

- Downloading copyrighted content (this tool is a download client; users are
  responsible for respecting platform terms and copyright).
- Design choices about retry pacing or worker count.

## How the app handles your data

- **API keys** (YouTube Data API, Groq, aiHubMix, OpenRouter, Google AI) are
  stored in the local SQLite database, encrypted with **Windows DPAPI** under
  your user account — another account on the same machine cannot decrypt them.
  If Windows refuses to encrypt a key, the key is **not stored at all** and
  the app says so; it is never written in plain text as a fallback.
- **The `cookies.txt` path** you point the app at is the only thing that is
  stored (the path, not the file). The file is read at request time and is
  never copied into the database, never written to a log and never sent
  anywhere except to the platform it belongs to.
- **Your cookies never leave for another host.** A `cookies.txt` holds a
  logged-in YouTube session, so the app refuses to fetch a URL that is not
  actually on `youtube.com` — the host is compared exactly, not by a
  substring.
- **The log file** (`%LOCALAPPDATA%\S-Q-Ali Media Downloader\app.log`) is
  where the app writes diagnostics. It is scrubbed of key and token patterns,
  because that is the file people attach to bug reports.
- **Nothing is uploaded anywhere** by the app itself: there is no telemetry,
  no analytics and no crash reporting. The only outbound traffic is to the
  platform you asked about (YouTube, TikTok, Facebook, Instagram), Google's
  autocomplete/suggest endpoint, and the AI provider you configured a key
  for. The AI analysis sends the channel title, subscriber and view counts, a
  300-character excerpt of the description and the titles of the five
  newest videos to that provider.

## Notes for maintainers

- The legacy activation secret (`legacy/licensing.py`) is gitignored and must
  never be re-added to the repository or the installer.
- Do not commit secrets, tokens, or the GitHub credential material to the repo.
- The YouTube Data API key must travel in the `X-Goog-Api-Key` header, never
  in a query string: httpx logs every request URL at INFO, and the app writes
  that log to disk.
- `niche_research/storage/db.py` opens the SQLite connection under the
  module lock. Two worker threads reaching the database at once used to open
  two connections and run the migrations twice.
- `ctypes.WinError` is a **function** on Python 3.14, not an exception class
  — `except (OSError, ctypes.WinError)` raises `TypeError` instead of
  catching anything. Use `except OSError`.
- The `_SEAL_ENTROPY` constant in `niche_research/storage/db.py` must never
  change: every stored key would become undecryptable.
