# Spec — TikTok mode: pasted creators, checked on YouTube + Instagram + Facebook

## Objective

The TikTok mode must stop turning the logged-in session account into a
"discovered creator", and must check the creators the user names on all three
platforms. The user pastes `@handles` / profile URLs (one per line or comma).
For each creator the app proposes Facebook / Instagram / YouTube accounts with
one budgeted AI ask and falls back to the same handle on each platform; every
candidate is verified live. A bare word is tried as a hashtag. When TikTok
blocks listing — measured as always — the app says so and asks for handles.

**User story.** As a creator-researcher I paste `@ishowspeed, @khaby.lame` and
the app lists each creator with their YouTube, Instagram and Facebook status,
and never shows my own TikTok account unless I pasted it.

**Success looks like:** a seed run shows one row per pasted handle, with the
FB / IG / YT columns filled or marked not found, and the log never mentions the
logged-in account.

### Measured evidence — 2026-10-30, the user's own cookies.txt (36 cookies)

| Route | Result |
|---|---|
| `tiktok.com/tag/ishowspeedlive` HTML | 200, ~392 KB shell, exactly **1** `uniqueId` = the session user |
| `tiktok.com/search?q=ishowspeedlive` HTML | 200, ~392 KB shell, same single `uniqueId` |
| `/api/challenge/item_list/` (X-Bogus + cookies) | 200, **0 bytes** |
| `/api/search/item/full/`, `general/full/`, `user/full/` | 200, **0 bytes** (with and without X-Bogus) |
| `yt-dlp` tag / search with cookies | 1 `None` entry / unsupported URL |
| Playwright render with the same cookies | 463 KB, **0** profile links |
| `tiktok.com/@ishowspeed` | 200, 1,462-char challenge page — no bio |
| Bing and DuckDuckGo | 0 `tiktok.com/@` handles |

**Conclusion:** TikTok serves no listing and no profile data to this client,
even logged in. The page shell's only `uniqueId` is the session user, so the
HTML harvest is the bug, not a fallback. The app can only act on handles the
user supplies, plus web search for those handles.

## Decisions (user, 2026-10-30)

1. **Platforms:** YouTube + Instagram + Facebook.
2. **Creator source:** the user pastes `@handles` / profile URLs; no automatic
   creator discovery.
3. **Bare words:** treated as hashtags (`ishowspeedlive` → `#ishowspeedlive`).
4. **Link discovery:** web proposal first, same-handle guess as fallback.

## Assumptions

1. The cookies file stays optional and read-only; values are never logged.
2. One plain AI ask per creator, capped by the existing 15-proposal budget;
   the grounded YouTube second check stays capped by the 5-search budget.
3. With no AI key the run still works from handle guesses alone.
4. The mode keeps its "creators without YouTube" flag and filter.
5. No TikTok login or session is stored by the app; no Google/Bing scraping.
6. TikTok bios stay unreadable, so "bio investigation" means a web ask plus
   live verification, never a claim that a bio was read.

## Tech stack

Python 3.10+, PySide6, httpx, yt-dlp, existing `social_judge` /
`SocialVerifierTool` / `YouTubeExistenceTool`. Tests run offline.

## Acceptance criteria

- [ ] A page shell whose only `uniqueId` is the session user yields **0**
      profiles (regression test based on the real shell).
- [ ] `@ishowspeed, @khaby.lame` produces two profiles with no listing call.
- [ ] `IShowSpeed edits, ishowspeedlive` parses to tag `ishowspeedlive` and
      keywords `IShowSpeed edits`; when listing is blocked the note asks for
      handles and names the platform wall.
- [ ] Every seed gets `facebook`, `instagram` and `youtube` presences; sources
      are `model` or `handle_guess`, and the status comes from a live probe.
- [ ] With no AI key, all three checks still run from handle guesses.
- [ ] At most 15 plain AI proposals and at most 5 grounded YouTube checks per
      run; spending one budget does not break the other.
- [ ] The TikTok table and CSV carry FB / IG status and URL; the copy FB /
      copy IG buttons work in this mode.
- [ ] No cookie value and no key material appears in any log or ops line.
- [ ] Offline suite and ruff green; a live seed run with the user's cookies;
      the shipped EXE rebuilt and verified.

## Out of scope

- Reading TikTok bios (walled).
- Restoring the 2.9.1 AI listing proposer (removed by decision 2).
- Scraping search engines.
