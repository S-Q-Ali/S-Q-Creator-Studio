# Tasks: Best-quality downloads

Spec: `tasks/spec-download-quality.md` · Plan: `tasks/plan-download-quality.md`

## Task 1: measure the formats YouTube offers per player client

**Description:** Write `tasks/spike_video_quality.py` and run it once. For a
known 4K video it asks yt-dlp for the formats each player client exposes and
prints the heights and codecs - no download, no cookies in the output.

**Acceptance criteria:**
- [x] The script prints, per client, the highest height and the codecs offered
- [x] It states plainly whether 2160p is reachable from this machine
- [x] Its output is the evidence quoted in the changelog
      > Measured 2026-11-04: `web_embedded` - the app's first client - offers
      > 2160p in AV1 and VP9 on a 4K video. `tv` and `web` failed from this
      > machine, `mweb` and `android_vr` stopped at 360p. The client list
      > does not have to change: the app already talks to the client that
      > carries 4K.

**Verification:**
- [x] `./source/venv/Scripts/python.exe tasks/spike_video_quality.py`
- [x] The result decides whether the player-client list changes

**Dependencies:** None · **Files:** `tasks/spike_video_quality.py` (new, and
not committed - the repository ignores `tasks/spike_*`) ·
**Scope:** S

## Task 2: "Best up to 4K" as the default, and a kept user choice

**Description:** `DEFAULT_QUALITY` becomes the best-up-to-4K entry. The
settings page stops writing a quality over the user's own choice: a
`quality_set` marker records that the dropdown was changed, and only an
unset quality takes the new default.

**Acceptance criteria:**
- [x] A fresh install selects "Best up to 4K"
- [x] A quality the user chose survives a settings-version bump
- [x] A quality the user never chose follows the default

**Verification:**
- [x] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_settings_page.py tests/test_engine.py -q`

**Dependencies:** None · **Files:** `src/s_q_ali_media_downloader/engine.py`,
`src/s_q_ali_media_downloader/ui/settings_page.py` · **Scope:** S

## Task 3: the codec-aware format selector

**Description:** The container follows the codec: MKV for VP9/AV1, MP4 for
everything else. The format string cannot express that, so the format
option becomes a callable that selects, reads the video codec, sets
`merge_output_format` and selects again through yt-dlp's own selector.

**Acceptance criteria:**
- [x] VP9 and AV1 downloads are muxed into an MKV
- [x] h264 and HEVC downloads are muxed into an MP4
- [x] "Audio only" is unchanged
- [x] The selector still fails the way yt-dlp fails when nothing matches

**Verification:**
- [x] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_engine.py -q`

**Dependencies:** Task 2 · **Files:**
`src/s_q_ali_media_downloader/engine.py` · **Scope:** M

## Task 4: resolution, codec and size on the queue card

**Description:** The download reports the height and the video codec it
picked; the card shows them next to the size.

**Acceptance criteria:**
- [x] The card shows `2160p · VP9` and the size
- [x] Nothing is clipped at 1280x720 in either density
- [x] The engine reports the resolution it actually downloaded

**Verification:**
- [x] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_ui_layout.py tests/test_engine.py -q`

**Dependencies:** Task 3 · **Files:**
`src/s_q_ali_media_downloader/engine.py`, `src/s_q_ali_media_downloader/ui/widgets.py`,
`src/s_q_ali_media_downloader/ui/main_window.py` · **Scope:** M

## Task 5: the docs, the version bump and the release-name fix

**Description:** The README and the changelog say what the app now does, the
version moves, and the release workflow names its archives with the
platform again - the v2.11.0 release named every archive the same, and the
Linux build was overwritten by the macOS one.

**Acceptance criteria:**
- [x] The README describes the default and the container rule
- [x] The changelog has a dated heading for the new version
- [x] The workflow names each archive with its platform and fails if one is missing
- [x] Ruff is clean and the offline suite is green

**Verification:**
- [x] `./source/venv/Scripts/python.exe -m ruff check src tests --output-format concise`
- [x] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q`

**Dependencies:** Tasks 1-4 · **Files:** `README.md`, `CHANGELOG.md`,
`pyproject.toml`, `src/s_q_ali_media_downloader/__init__.py`,
`.github/workflows/release.yml` · **Scope:** M

### Checkpoint: done
- [x] Ruff clean, the offline suite green, the docs match the build
- [x] The release names its archives with the platform
