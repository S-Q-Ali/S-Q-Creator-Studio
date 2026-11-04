# Implementation Plan: Best-quality downloads

**Spec:** `tasks/spec-download-quality.md`
**Task list:** `tasks/todo-download-quality.md`

## Overview

The app already has the whole quality ladder; what it does not have is a
default the user would call "the best the source offers". A fresh install
downloads 1080p because the settings default says so, the settings
migration overwrites that choice on every version bump, the merged file is
forced into MP4 whatever codec came down, and the queue card never says
which resolution arrived.

Four pieces of work, in this order:

1. **Measure** what YouTube offers through each player client, once, live.
   The ladder can only pick a 4K stream if the extractor is offered one.
2. **Default** to the best up to 4K, and stop the migration from
   overwriting a quality the user chose.
3. **Container** that follows the codec: MKV for VP9/AV1, MP4 otherwise.
4. **Say** what came down: resolution, codec and size on the card.

The release-naming defect found while verifying v2.11.0 (every archive was
named without its platform, so the Linux build was overwritten by the macOS
one) is fixed in the same release as this work.

## Architecture decisions

- **The ladder stays a plain dict.** `QUALITY_OPTIONS` already maps a label
  to a yt-dlp format string; the cap is in the string, not in code.
- **The default is a constant, and the user's choice is marked.** A new
  setting key `quality_set` is written when the user picks a quality that
  is not the default. Without it, "never chosen" and "chosen 1080p" are the
  same stored value, and any migration would have to guess.
- **The container comes from a callable format selector, not from the
  format string.** `merge_output_format` is a fixed preference list and
  `mkv` is compatible with every codec, so no string can say "MKV for
  VP9/AV1, MP4 otherwise". The callable selects once to learn the codec,
  sets the container, and selects again - yt-dlp's own merge code then
  builds the file with it.
- **The card reads the codec from the download's own info dict**, in the
  progress hook, where the height and the video codec are already known.

## Task list

### Phase 1 — evidence
- [x] Task 1: measure the formats YouTube offers per player client - `web_embedded` reaches 2160p, so the client list stays as it is

### Checkpoint: evidence
- [x] The measurement script runs and prints the heights per client

### Phase 2 — the default
- [x] Task 2: "Best up to 4K" as the default, and a kept user choice

### Checkpoint: default
- [x] A fresh install selects "Best up to 4K"; a chosen quality survives

### Phase 3 — the container
- [x] Task 3: the codec-aware format selector

### Checkpoint: container
- [x] VP9/AV1 downloads land in an MKV, h264 in an MP4

### Phase 4 — the card
- [x] Task 4: resolution, codec and size on the queue card

### Checkpoint: card
- [x] The card shows `2160p · VP9 · 412 MB` and nothing is clipped

### Phase 5 — the release
- [x] Task 5: the docs, the version bump, the release name fix

### Checkpoint: done
- [x] Ruff clean, the offline suite green, the docs match the build

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The measurement shows no client reaches 2160p here | High | Ship the ladder and say so in the docs; do not claim 4K |
| The callable format selector replaces yt-dlp's own selection | High | The callable calls yt-dlp's selector twice - it delegates, it does not reimplement it |
| A longer meta line clips the card at 1280px | Medium | The layout suite renders every card size and fails on a clipped label |
| A 4K download is 5-20x the data | Low | The user decided: no guard, the card shows the size |

## Open questions

- None open. The measurement decided the player-client question: the
  client the app already uses offers 2160p, so the list stays as it is.
