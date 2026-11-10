# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.20.0] — 2026-11-10

### Added

- **Multi-aspect ratio reframing in Vertical Studio (`9:16`, `1:1`, `4:5`).**
  - Added aspect ratio selector dropdown (`9:16 (Vertical)`, `1:1 (Square)`, `4:5 (Portrait)`) beside the reframe checkbox in Vertical Studio.
  - Crop window and output dimensions scale smoothly to target ratios with exact macroblock alignment (zero distortion).
  - AI subject tracking (YuNet + NanoDet) smoothly frames the subject across all three aspect ratios.
- **YouTube Shorts sorting & Video Type filtering for channel scraping.**
  - Added `Video Type` filter: `All Videos` (both), `Shorts only` (`/@handle/shorts`), and `Long-form only` (`/@handle/videos`).
  - Added `Shorts Sort` control: `Latest (Default)`, `Popular` (view count first), and `Oldest` using InnerTube continuation tokens without API keys.
  - Automatic URL sanitization: pasting `/@handle/shorts` or `/@handle/videos` cleanly targets the requested feed.

### Changed

- **Cleaned up Paste links tab interface.**
  - Removed redundant channel filtering dropdowns from `Paste links` tab; scraping controls are now cleanly centralized in `Account based` tab.
- **Regenerated all repository proof screenshots.**
  - Added `studio.png` to automated tracking and updated all screenshots in `screenshots/` with the latest dark glass interface.

### Fixed

- **Release build wrapper virtualenv detection.**
  - Updated `release/build.bat` to detect and run `.venv\Scripts\python.exe` before falling back to `source\venv` or system `python`.

## [2.19.0] — 2026-11-08

### Changed

- **Unified theme rules, keyboard focus rings, and workspace headers across all 5 tabs.**
  - Added `QSpinBox`, `QPushButton[kind="github"]`, and `QPushButton[kind="linkedin"]` rules (with `:focus` rings) to `theme.py`; moved social buttons and `MusicPage._say()` off inline `setStyleSheet()` onto dynamic properties; gave `QPushButton[kind="danger"]` a distinct resting border (`C["faint"]`); scaled `QLabel[role="pageTitle"]` from the density token (`16px` comfortable, `14px` compact).
  - Added `#WorkHeader` (`⚙️ Settings`) to `SettingsPage`, removed the duplicate `🔎 SOCIAL DISCOVERY` header inside `SocialDiscoveryPage`, and matched `AgentTabWidget`'s header to Title Case (`🤖 AI Channel Finder & Social Inspector`).
  - Added an `#EmptyState` stack, alternating row fills, and hidden gridlines to `MusicPage`, reordered `VerticalStudioPage` action buttons so the primary CTA (`Run`, `Stop`) leads the row, capped `MusicPage` and `VerticalStudioPage` activity logs at 500 blocks, and standardized `"Browse…"` labels and inline status messages across `SettingsPage` and `AgentTabWidget`.

### Fixed

- **Packaged-build file pickers, running-state locks, and full keyboard accessibility.**
  - Passed `QFileDialog.Option.DontUseNativeDialog` to all 6 remaining file/folder pickers across `MusicPage`, `SettingsPage`, `AgentTabWidget`, and `SocialDiscoveryPage`.
  - Disabled `MusicPage.btn_browse` during active music downloads, added cooperative `Stop` cancellation to `AgentTabWidget` (`AgentWorkerThread.cancel()`), and included `agent_tab.worker` in `MainWindow` close-event guards.
  - Replaced `MainWindow.folder_label` with a keyboard-focusable `QPushButton` (`kind="ghost"`), underlined link cells in `SocialDiscoveryPage`, wired keyboard arrow navigation and `Return`/`Enter` link activation on `SocialDiscoveryPage` and `AgentTabWidget` tables, and set `accessibleName` and `setBuddy()` across form controls and checkboxes.

## [2.18.0] — 2026-11-08

### Changed

- **The Studio's drop well is a door you can click.** The dashed well now
  carries a **Choose video files** button that opens the same picker the
  row's **Browse…** used to open, and the row's Browse is gone — one door
  by pointer, one by drag, the same files-in either way. The button is a
  real button: `Tab` reaches it, `Space` and `Enter` press it, and a screen
  reader announces it; the old well offered a keyboard user nothing.
  Dropping files anywhere on the page works exactly as before, and the
  hint now names the click instead of a button that no longer exists.

## [2.17.0] — 2026-11-07

### Changed

- **Nothing the Studio makes writes over a file that was already there.** Each
  pass used to derive one fixed name from the film — `<name>_9x16.mp4`,
  `<name>_short01.mp4` — and ffmpeg was told to replace whatever stood at that
  path: a 53-byte `Film_9x16.mp4` in the results folder came back as a 306 KB
  render, unasked and unsaid. The names now come from one place, so shorts
  land as `<name> Part 1.mp4`, `Part 2` and on, a second run of the same film
  continues at `Part 4` with every earlier part untouched, and a vertical
  whose name is taken lands as `<name>_9x16 Part 2.mp4`. The shorts leg's old
  answer to a taken name — refuse the cut and say "nothing was overwritten" —
  went with it, and it was hiding the worse half of the same bug: after
  refusing, the vertical pass went on to render the **whole film**, so a
  request for two shorts was answered with one vertical feature.
  **The cost of the rule:** running one film twice leaves two sets of parts in
  the folder instead of replacing the first. That is what never-overwriting
  buys, and the staged copy follows the same law (`Film (2).mp4`).
- **The log says what the run wrote.** "N shorts saved beside the original"
  and "The vertical version is beside the original" were true of the copy in
  the results folder and misleading about everything else. The lines now name
  the files: `2 shorts made.` · `Made Film Part 2_9x16.mp4.`

### Fixed

- **A vertical render that fails takes its own file back out.** The truncated
  mp4 it left on disk was counted as a result by the next run, which then
  stepped aside for it.
- **Run with nothing chosen no longer promises versions.** With the vertical
  box off and Shorts on Off — the state a fresh settings store starts in — the
  Studio started a worker, logged a run, and closed with "Done. The versions
  are in X." over a folder nothing had been written into. It now says which
  box to tick and starts nothing.
- **One file the copy could not make no longer ends the queue.** The copy into
  the results folder answered only for `OSError`; anything else it raised — a
  permissions surprise, a name lookup that failed — stopped the run and the
  remaining files were never mentioned. It is guarded the way the two passes
  are: the file is named, the reason given, the next one runs.
- **Stop interrupts a copy.** A whole-film copy had no cancel in it, so after
  the button — which says "Stopping after the file in hand" — a 6 GB film on a
  slow disk kept coming for minutes. The copy now goes in 4 MB bites and asks
  the stop flag between them, and what it managed is removed: half a film is
  not a result.
- **"Working:" names the file the writes go into**, not the one that was
  dropped while every output landed in its staged copy.
- **A folder that holds its own probe is not refused.** The Studio tests a
  chosen folder by writing a file into it; an indexer or antivirus holding
  that probe for a moment was enough to answer "Nothing could be written to X"
  about a folder it can write. Only creating the probe decides the answer.
- **The results field is reachable by its name.** Its label had no buddy, and
  the error line was painted by a stylesheet of its own; the colour now comes
  from the theme's `role="error"` like everywhere else in the app.

## [2.16.0] — 2026-11-07

### Added

- **The Studio can put everything in one folder.** "Save results to" under the
  options: name a folder and each file is copied into it first, then the 9:16
  version and the shorts are made beside that copy — so the folder ends up
  holding the film, its parts and their verticals, while the file you pointed
  at stays exactly where it was. The choice is remembered between runs,
  **Beside each file** puts it back, and the closing line names the folder the
  run used.

### Fixed

- **A long job no longer fills the desktop with blank terminals.** The
  packaged build is windowed, so Windows gave every ffmpeg child a console of
  its own; one helper spawns ffmpeg and hides that window, and all four passes
  go through it.
- **The progress bar moves inside one file.** It counted files, so a single
  30-minute film sat at zero through minutes of ffmpeg. Each pass now asks
  ffmpeg for its own counters, and the bar is priced up front in reads of the
  film so the work a split only finds later fills the bar instead of pushing
  it back. The status line names the file in hand, its place in the list and
  the pass running on it.
- **Browse opens a picker you can see.** On the packaged build the native
  Windows dialog is a separate top-level window that can come up behind the
  app, which made the button look dead. The page's own picker is a child of
  this window, lands in front of it, and opens at the folder of the last file
  in the list — or the downloads folder when the list is empty.
- **The clip count the app works out for itself has a floor and a ceiling.**
  **Auto** on a long video cut at every scene change and returned 29 clips
  between 2 seconds and 9 minutes: fragments at one end, nothing a Short can
  be at the other. A number you typed is still honoured exactly.

## [2.15.0] — 2026-11-06

### Added

- **The Vertical Studio.** A fifth section, between Music and the AI channel,
  for the two passes over videos the app never downloaded: drop the files or
  press Browse, tick the vertical box, pick a shorts length, or both, and press
  Run. Until now the only way to reframe a file you already had was to
  re-download it. One file at a time on purpose — a reframe costs about four
  seconds of work per second of film, so two at once only make both slower —
  and a run counts as work under way, so closing asks instead of abandoning a
  file mid-write. A file that cannot be read says so in one sentence and lets
  the rest of the list run; Stop ends the run after the file in hand.
- **The length of a file with no site behind it.** The split plans its cuts
  from a duration, and until now the only duration the app knew was the one a
  website reported with its download. A dropped file has none, so the
  container is asked instead — the frame count over the frame rate, off the
  same decoder the subject tracker already opens.

### Fixed

- **The release workflow names a runner that exists.** GitHub retired the
  `macos-14` image on 2 November 2026 and the Apple Silicon job was cancelled
  the second it was queued — no runner, no log, nothing published — which
  reads as a deliberately cancelled release rather than as a dead label, and
  re-running it reads the workflow from the tag, which still names that label.
- **The drop zone is aimable.** A thin strip of dashed frame is hard to hit,
  while three or four named files need far less than the whole panel: the zone
  takes the stretch and the list is capped, the way the other pages cap their
  panels.

## [2.14.0] — 2026-11-06

### Added

- **A vertical 9:16 version of any download.** Tick **Also make a vertical
  9:16 version** in Settings and each video also lands as `<name>_9x16.mp4`
  beside the original, filled edge to edge: the crop window is cut out of the
  picture itself, so the black bands of a widescreen film do not travel into
  the vertical file, and it follows the person in the frame — a face where
  there is one, a full body where there is not, and the position it had where
  neither answers. The camera sits still while the subject does and glides
  when it moves, and a change of scene takes the new framing at once instead
  of panning across it. The audio is copied and not re-encoded, and the file
  is at most 1080×1920: a 4K film's picture is about
  a thousand pixels wide, so a taller output is the same picture in four times
  the bytes for rows no phone shows. It is off by default and it is two extra
  passes over the video, so a long one takes its time — measured on a 4K
  download, a 37-minute film lands in about 2½ hours. A failure there leaves
  the download exactly as it was.
- **Long videos split into shorts.** **Split into shorts** in Settings: **Auto**
  cuts at the changes of scene; a fixed length — 30, 45, 60 or 90 seconds —
  cuts at the nearest pause in the speech to it; **N clips** divides the length
  by the number you pick, from 2 to 30, and the app names the length each clip
  gets before it starts cutting. Each clip lands as `<name>_short01.mp4` and,
  with the vertical version ticked, gets its own `<name>_short01_9x16.mp4`.
- **The build is about 110 MB larger.** The two extra passes need OpenCV for
  the face and body detectors — the models themselves are 1.3 MB; the runtime
  is the rest.

## [2.13.0] — 2026-11-05

### Added

- **A build for Intel Macs.** The release shipped only the Apple Silicon
  build, and Rosetta 2 translates x86 to arm and not the other way round, so
  an Intel Mac had nothing to download. There is now an Intel build
  (`macos-x64`), built and smoke-tested on an Intel runner, and the offline
  suite runs there at Python 3.12 and 3.14.
- **A disk image for each Mac.** `macos-arm64.dmg` and `macos-x64.dmg` join
  the portable archives. Open the image and drag the app onto the
  `Applications` shortcut — the way software arrives on a Mac. The `.tar.gz`
  files stay published, so existing download links keep working.

### Changed

- **The macOS version claim is checked, not assumed.** The build now measures
  the Mach-O version of every binary in the bundle and fails the release if
  one needs a newer macOS than the claim. The measurement found the app needs
  **macOS 15** — PySide6 6.11's wheel is tagged `macosx_13_0`, but the Qt
  binaries inside it declare macOS 15 — so the claim moved from macOS 13 to
  macOS 15, in this file and in the README, together.

### Fixed

- **The macOS build is a real app bundle now.** It used to ship the executable
  with its files beside it — no `Info.plist`, so no bundle identifier, which is
  what the login keychain needs to keep the API keys — and there was no bundle
  to put in a disk image. The macOS archives now contain
  `S-Q Creator Studio.app`, the same bundle the disk image carries.

## [2.12.0] — 2026-11-04

### Added

- **A download comes down at the best the source really offers, up to 4K.** The
  default used to be 1080p — a cap nobody chose — so a 4K video arrived as
  1080p. The default is now **Best up to 4K**: the highest resolution the
  source has, capped at 2160p, with **Best available** (no cap) still one
  dropdown away for the 8K streams. A video that has no 4K stream comes down at
  the best it does have. Measured on YouTube through the client the app already
  uses, a 4K video offers 2160p in AV1 and VP9, and the app now takes it.
- **The queue card says what came down** — `2160p · VP9`, next to the size, so
  "4K ho gaya" is visible instead of a guess.

### Changed

- **The container follows the codec.** A 4K stream is VP9 or AV1, and an MP4
  that carries them is refused by half the players, so those downloads are muxed
  into an **MKV**; H.264 and HEVC stay in an **MP4** as before. The container is
  decided from the codec the download actually picked.
- **A quality you chose survives an upgrade.** The settings used to write
  1080p over the dropdown on every settings-version bump, so a chosen quality
  was replaced by the old default. A quality is now marked as yours when you
  pick it, and only a quality you never chose follows the default.

### Fixed

- **The release named its archives without the platform.** PowerShell reads an
  environment variable as `$env:NAME`, not as a bare `$NAME` — so every archive
  was named `S-Q-Creator-Studio-2.11.0-.tar.gz`, and the Linux build was
  overwritten by the macOS one when the artifacts were merged. The v2.11.0
  release therefore has no Linux archive. Each archive now carries its platform
  again, and the publish step refuses to release when one of the three is
  missing.

## [2.11.0] — 2026-11-04

### Added

- **Your API keys are sealed on Linux and macOS as well as Windows.** The store
  now uses the machine's own keychain (the login keychain, GNOME Keyring or
  KWallet) through `keyring`, and the settings database keeps only the name of
  the item — never the key. A system with no secret store reachable marks those
  rows `plain:`, states it on the Settings page, and logs a warning that names
  the key but never its value. Windows keeps using DPAPI exactly as before.
- **The app's folder is the one this OS uses for app data.** Linux keeps it in
  `~/.local/share/S-Q-Ali Media Downloader`, macOS in
  `~/Library/Application Support/S-Q-Ali Media Downloader`, Windows in the
  `%LOCALAPPDATA%` folder it has always used. A data folder an early Linux or
  macOS run left in the home directory is moved into place on the next start,
  so the keys already entered are not lost.

### Changed

- **The interface is on one glass sheet.** Black, white, grey and one blue:
  every colour the app paints comes from a single token module, and the pages
  that carried their own hardcoded colours — the queue cards, Music, Social
  Discovery, Settings — read from it now. Panels are opaque and the light comes
  from the backdrop behind them, because text over a translucent panel is text
  that has to be read twice.
- **A download's state is not one colour.** Each queue card has a spine on its
  left edge that says where the job is (queued, moving, retrying, waiting,
  paused, completed, failed), a finished bar is chalk instead of the blue that
  means still running, and a failed row carries its error in a loud chip. The
  pairs are measured, not eyeballed: body text on a panel is 15.5:1 and the
  selected tab 4.7:1.
- **Keyboard focus is visible on every control.** Tabbing paints a blue ring
  that changes colour and never size, so nothing shifts as you move about.
- **The wordmark is drawn rather than typed,** at the size the current density
  asks for, and the font stack names the system face on Windows, macOS and
  Linux instead of assuming Segoe UI everywhere.
- **The README shows the current build.** Six renders, one per workspace page
  plus the compact layout, written by `tests/render_glass_screenshots.py` —
  which keeps this machine's download folder out of them.
- **The declared Python floor is 3.12, up from 3.10.** Nothing ever ran on 3.10:
  the agent extra cannot resolve below 3.11 (`browser-use` needs it), and the CI
  matrix starts at 3.12. Installing the app on 3.10 or 3.11 is now refused by the
  metadata instead of promised by it; 3.12 and 3.14 are what CI tests, and 3.13
  is allowed but untested.

### Fixed

- **The settings store no longer needs Windows to import.** It read
  `ctypes.wintypes` at module import, which raises on Linux and macOS, so the
  whole Settings page could not load off Windows.
- A key that was saved unencrypted on a machine without a keychain is moved into
  the keychain automatically the first time it is read on a machine that has one.
- **The docs claim the platforms the app delivers, and stop where CI's evidence
  stops.** The README and SECURITY.md name the three OSes and the two Python
  versions the matrix runs, the four files a release carries, the glibc and macOS
  floors the bundled Qt wheels need, and the fact that the builds are unsigned —
  and they no longer imply that a CI runner proves what a desktop keychain does.
- **The secret store's promise is scoped to the platform that keeps it.** The
  README and SECURITY.md name DPAPI on Windows (user scope, so tied to your
  account rather than the machine), the machine's keychain on Linux and macOS,
  and the `plain:`-marked fallback where no secret store answers.
- **The build-from-source instructions no longer build a broken app.** A
  hand-written `pyinstaller` command misses the `--collect-all` flags the real
  build carries, which produces an app that starts and then cannot import
  `mutagen`, `SpotipyFree`, `browser_use` and friends. The README now points at
  `release\build.bat`, the script CI runs.
- Smaller wording: the installer bundles the **full** Chromium build rather than
  the headless shell, `browser-use` runs its own browser session on the app's
  profile instead of "attached over CDP" to the hardened one, the tested Python
  version is named, and `curl_cffi`'s documented range matches the real pin.
- **`pip install .` no longer installs an app that cannot open a browser.**
  Playwright was listed in the runtime requirements but only as an optional
  extra in the package metadata, so an install from `pyproject.toml` produced an
  app whose Social Discovery could not verify any account. It is a real
  dependency now, and a test keeps the requirements files and the package
  metadata from drifting apart again.
- **The support log is filed with the data it describes.** `app.log` resolved
  its own folder and landed somewhere else than the settings, the saved queue
  and the downloads — so a bug report asking for "the folder with your data"
  found a folder without the log. One location now decides all four; on Windows
  the log moves into the storage folder the rest of the app already used.
- **A bundled ffmpeg is recognised on every platform.** The app looked for
  `ffmpeg.exe` only, so a Linux or macOS bundle that ships its own ffmpeg beside
  the app reported none, and the formats that merge video and audio failed with
  nothing to point at. The name now follows the platform it is running on.
- **Social Discovery finds a browser on Linux and macOS.** Three Windows-only
  assumptions were fixed at once: Microsoft Edge is asked for only where it comes
  preinstalled, Playwright's own browser cache is read from the folder this OS
  uses (`~/.cache/ms-playwright`, `~/Library/Caches/ms-playwright`, or
  `%LOCALAPPDATA%\ms-playwright`), and the current Chromium folder layouts are
  recognised — Linux installs `chrome-linux64`/`chrome-linux-arm64`, macOS a
  "Google Chrome for Testing" bundle. Chromium is also started without its own
  sandbox when the app runs as root, which is the only way it will launch in a CI
  container or a headless box.
- **A macOS bundle keeps its extras where macOS looks for them.** `--windowed`
  builds a `.app` there, and inside it only the executable may sit in
  `Contents/MacOS` — everything else belongs in `Contents/Resources`. ffmpeg and
  Chromium were staged beside the launcher, the folder Windows and Linux use, so
  a macOS build would have started and then found no ffmpeg and no browser: every
  merged download and Social Discovery broken, on one platform only. The build
  stages them into `Contents/Resources` and the app resolves both from there.
- **Contributors: a test run keeps to itself and stops its own workers.** The
  suite points the app's data folder at a temporary one for the whole run, so
  opening a window in a test no longer writes a queue, a downloads folder, a
  browser profile or a log into the folder your own app uses. The interface is
  measured with the fonts this OS actually keeps rather than the Windows font
  folder, and a worker thread that outlives its test is named in a failure
  instead of being killed with `QThread.terminate()` — which Linux and macOS do
  not offer, and which stopped a thread mid-call when it worked.
- **Contributors: one build script, on any platform.** The release build lived
  entirely in a Windows batch file, so there was nothing to run on Linux or
  macOS — and keeping the same steps in two places is how three platforms end up
  shipping three different apps. `release/build.py` builds the bundle on all
  three: the `--add-data` separator, the ffmpeg file name, the Playwright cache
  folder, the launcher name and the keyring collection follow the OS that is
  doing the build, and Inno Setup is tried only where it exists.
  `release\build.bat` is now the Windows entry point that starts it. The Windows
  artifact did not move: the rebuilt bundle carries the same files with the same
  `--collect-all` and `--hidden-import` set, and the rebuilt app still runs — the
  only additions were two OpenSSL DLLs the build machine's PATH offered, which
  PyInstaller picks up wherever the build happens to run.
- **Contributors: CI and a tag now build on all three platforms.** The test
  workflow runs the suite on Linux, macOS and Windows at Python 3.12 and 3.14,
  and on each one builds the portable app and launches it for 30 seconds before
  uploading the artifact. A tag runs the same build as a three-way matrix and
  publishes one archive per platform in a single release, with the SHA-256 of
  each file and the installer kept Windows-only because Inno Setup is a Windows
  program. Both have now run: every cell of the six-cell matrix passes the
  offline suite (841-842 tests), and on each OS the frozen app builds and stays
  alive through its 30-second smoke test. That run is what the README's platform
  claims rest on.
- **Contributors: two tests stopped assuming the runner is Windows.** The secret
  store's backend tests asked a Linux or macOS machine to answer as if it were
  Windows, and one of them read the runner's own keychain into the answer; the
  browser-stealth test opened a window on a Linux runner that has no display.
  Each now names the condition it is about, so the suite asks the same question
  on every OS.
- **A wide platform font no longer clips the left rail.** The rail was exactly as
  wide as its density token, which the Windows font fits inside — on Linux the
  same rows needed more, and "Account based" and "Add to queue" lost their last
  letters. The token is the floor now: the rail grows to whatever its content
  needs and Windows keeps the width it had.

## [2.10.0] — 2026-11-02

### Added

- **Music workspace.** A separate tab for audio. Paste YouTube, YouTube Music,
  SoundCloud or Spotify links — one per line — and the app resolves them into a
  queue and downloads the audio. A playlist or an album becomes its tracks in
  one click. Formats: FLAC (default), MP3 320, M4A, Opus and WAV; each file is
  tagged, and a quality report shows what the source stream really was.
- **Files land where the link pointed.** A collection link — album, playlist or
  YouTube set — puts all of its tracks in that collection's folder as
  `Collection/NN - Title`, so one download no longer scatters across a dozen
  `Artist/Album/` folders. A single track link still files `Artist/Album/NN - Title`.
- **Spotify links resolve without an account.** Their metadata is read
  anonymously with `spotipyFree` and every title is matched to its YouTube
  version by yt-dlp's own search, so no Spotify login, password or client ID
  is needed anywhere in the app.
- **Known limit:** a Spotify *playlist* row carries no album and no cover in the
  free metadata endpoint, so those tracks are tagged by artist and title only —
  they still file into the playlist's folder. Track and album links keep the
  album and its artwork, as do YouTube and SoundCloud links (their own thumbnail).

## [2.9.2] — 2026-10-30

### Fixed

- **The TikTok mode no longer shows the logged-in account as a creator.** With
  a cookies file, the tag page's HTML was read for creators, and the only
  account in that page is the one that owns the cookies — so a `#tag` run
  returned that single bogus profile and ran the YouTube check on it. That
  harvest is gone. The mode now works from creators you paste (`@handles`,
  profile URLs, comma- or newline-separated; a bare word is read as a
  `#hashtag`, and the hashtag/keyword tiers still run as a best effort), and
  when TikTok lists nobody the note says so and asks for handles.

### Added

- **Each TikTok creator is checked on YouTube, Instagram and Facebook.** One
  AI ask per creator proposes all three accounts, the YouTube candidate goes
  through the existing channel check, and the Facebook and Instagram
  candidates are opened and verified in the browser. When the AI is silent or
  has no key, the creator's own handle is tried on each platform. The results
  table and the CSV export carry Facebook and Instagram status and links, and
  the copy buttons work in this mode.

### Removed

- **The AI listing leg for TikTok (2.9.1).** Asking the web for a niche's
  creators is gone: it could not be confirmed against TikTok, and the pasted
  creator list is the path that actually works.

## [2.9.1] — 2026-10-29

### Added

- **A `#tag` query in the TikTok mode finds creators again.** TikTok no longer
  lists a tag or a keyword for an anonymous visitor (measured 2026-10-29: the
  tag page is a 390 KB shell with zero creators, the signed listing API
  answers with an empty body, and a rendered page is blank too), so the mode
  only worked for `@handle` seeds. When the listing is empty, the app now asks
  the search-grounded AI for public TikTok profiles that match the niche and
  runs them through the same YouTube check. The handles are proposals, not
  findings — TikTok walls the profile reads that would confirm them — and the
  run says so. Costs one search call per run, from the existing per-run
  budget; without an AI key the mode says why it has nothing.

## [2.9.0] — 2026-10-29

### Added

- **An Instagram profile expands into its videos.** Paste a profile link the
  way a YouTube channel works, and the app lists the profile's video posts and
  reels and drops them into the queue for review. Only public profiles are
  read: there is no sign-in, and no Instagram account is ever stored.
  yt-dlp cannot do this — its own Instagram profile extractor is broken
  upstream — so the listing is done with instaloader, and the app keeps the
  pause between two listings that keeps Instagram from answering 429.

- **A Facebook page expands into its videos** — *experimental*. The page's
  Videos tab is read in the app's own browser, the same hardened one Social
  Discovery uses. The tab itself shows a visitor only its first screen
  (measured: 21 videos for `nasa`, 9 for `natgeo`), but the page pages the
  rest of its own list behind that tab, and that query answers a visitor
  without a sign-in. The app reads both halves: measured 61 videos for `nasa`
  and 60+ for `natgeo`, against the first screen's 21 and 9. Nothing is
  stored — no Facebook session, no cookie, no sign-in.

- **An Instagram listing stops where it should.** Instagram paces itself, so
  walking a busy profile for the full 200-video limit would run for a long
  time. The walk now stops after three minutes and says how far it got, so a
  partial list never reads like a complete one. A listing that Instagram cuts
  off with a rate limit keeps the videos it already found instead of throwing
  them away.

### Changed

- **A Facebook page lists its whole video list, not its first screen.** The
  app now asks the page for the videos behind the tab, the way the page asks
  for them itself, and hands both halves on. Measured: `nasa` went from 21 to
  61 videos, `natgeo` from 9 to 60+. The query's id is read from the page's
  own JavaScript, so a Meta rename does not break it. When Facebook refuses
  to page, the app says the listing stopped at the first screen rather than
  handing back a short list quietly.

- **An Instagram profile lists three times faster.** The listing fetched every
  post's full metadata one post at a time, and that was most of the time a
  walk spent. It now reads the timeline's own entry for each post, and asks
  for a post's metadata only when it has to — for a carousel, whose children
  the timeline does not describe. Measured on the same profile and the same
  20-video limit: 165 seconds became 55 seconds. A 30-video listing now
  finishes inside the three-minute budget instead of being cut off by it.

- **Version** bumped to 2.9.0.

### Fixed

- **A Facebook listing that fails says so.** A paging step Facebook refused
  mid-way could end the listing without a word: the error escaped the
  background thread, and a windowed build has no console to print it to. The
  videos already found are now kept, the listing says where it stopped, and
  anything else that goes wrong is reported instead of swallowed.

- **The YouTube channel progress never showed a total.** The signal was
  declared as a text field and fed a number, so the count read
  "Expanding channel: 120/ videos found" — the total was silently empty.


## [2.8.0] — 2026-10-29

### Added

- **A second opinion from the web.** Where a bio says nothing about the
  creator's social accounts, Gemini is now asked with Google Search turned on,
  so the answer comes from a real search result instead of the model's memory.
  If Gemini cannot answer, Groq is asked with a model that can browse the web
  itself. The ask only happens when it is needed, and a per-run budget of five
  searches keeps it from running away.

- **A browser that does not look like a bot.** The pages the app opens now hide
  the two tells a platform can read without guessing: `navigator.webdriver` and
  a one-language `navigator.languages`. Chrome starts with the automation flag
  off, so a first run does not open a welcome tab over the page. Playwright
  itself does not leak the debugger, so no patched browser is needed.

- **A log of every operation.** Each step writes one line: the stage, the
  engine that did it (AI or browser), the target it touched, the detail and
  how long it took. The search budget is in there too, so a run that stopped
  asking is visible.

### Changed

- **The AI proposes, the browser confirms.** In all three discovery modes the
  two answers are now reconciled: a URL the web names is opened in the browser
  and the readings are compared. Where one of them cannot answer, the other's
  reading stands — with the reason in the log.

- **Version** bumped to 2.8.0.

### Fixed

- **A TikTok profile could be read as somebody else's.** The page's footer
  ("© 2026 TikTok") sits above the profile line and was read as part of the
  display name, so "MrBeast" became "2026 MrBeast" and the account was
  reported as not matching. The name is now taken from the line above the
  handle only.


## [2.7.0] — 2026-10-26

### Added

- **The neon theme is the default look.** Electric cyan (`#00d4ff`) on a
  near-black surface, with a real cyan drop shadow on the primary actions
  (Start, Add to queue, Get URLs) instead of a painted border.

- **Theme roles for the agent and Social Discovery pages**, so their cards,
  tables and buttons follow the same palette as the rest of the app.

### Changed

- **One stylesheet.** `NeonTheme.get_stylesheet()` is the single source of
  truth; the separate `neon.qss` file and its loader are gone. Qt's QSS has
  no `box-shadow`, `text-shadow` or animations, so the glow is a real
  `QGraphicsDropShadowEffect` and the gradients are `qlineargradient`.

- **Version** bumped to 2.7.0.

### Fixed

- **The saved queue could be lost on Windows.** The writer opened
  `queue.json` itself as its lock, so the atomic replace was refused and the
  JSON stayed in `queue.json.tmp` while the live file was left at 0 bytes.
  The lock file is now separate, and the write is serialized with
  `msvcrt.locking` / `fcntl.flock`.

- **A density change replaced the neon theme.** The settings pass re-applied
  the old stylesheet on top of the neon one; the active theme is now marked
  on the application and survives the density switch.

- **The AI workspace tab clipped its last letter** when it was selected: the
  checked style switched to a heavier weight than the width was measured
  at. The selected tab is distinguished by its gradient and white text.

- **"Account based" was clipped in the source tabs** at 125% display
  scaling. The tab padding now fits both labels in the rail.

- **Checkboxes had an 18px click target.** They keep the 16px box but the
  row is 24px tall.


## [2.6.0] — 2026-10-22

### Fixed

- **A channel title could run as a formula in your spreadsheet.** The AI
  Finder's CSV export wrote the cells by hand and skipped the guard the
  exporter has, so a title beginning with `=` or `+` was evaluated when the
  file was opened in Excel. It goes through the exporter now, like the
  Social Discovery export always did.

### Changed

- **The release lives in one folder.** `release/` holds the build script,
  the installer definition, a README that says what a local build needs,
  and everything the build produces. `build_release.bat` was at the root.

## [2.6.0] — 2026-10-22

### Removed

- **Niche Research left the desktop app.** It was ported from the web tool
  and brought a second design system, a second navigation and a second
  brand lockup into an app with one job. The research package (9,352 lines)
  and its eighteen test files are gone from the repository.

  It could not simply be deleted: the Social Discovery feature reads the
  Groq key from the research database, resolves channels through the
  research YouTube client and exports through the research exporter. Those
  three modules moved up into `core/` instead. The database file, the
  table and the key names are unchanged, so a key entered before the move
  still reads back — the sealing entropy must never change.

### Added

- **A Settings tab.** Every setting of the app is in one place now: the
  Groq key, the YouTube key, the cookies file, the download preferences and
  the layout preference. The desktop app had nowhere to enter the Groq key
  once the research module left it.

- **A compact layout.** The interface tightens itself below 1500×850, and
  the Settings page lets the choice be made by hand. The same rules are
  rendered from one token set, so the two densities cannot drift apart.

### Fixed

- **The interface was clipped on a small laptop.** At 1366×768 the AI
  Finder cut its own controls in half ("50 chann", "Facebook Pag") and the
  cookies row fell off the panel; at 1280×720 it was worse. The cause was
  measured, not guessed: the window's minimum width was 1479px, so a 1366px
  screen could not show the window at all and the layout was squeezed
  instead. Seven controls in one row were the reason. The filters, the API
  key and the cookies file now sit behind an Options disclosure, each group
  on its own row, and the minimum width is 1110px.

- **The active workspace tab was invisible.** Dark text on a dark
  background, 1.02 to 1: the frame around the tabs set a bare
  `background:` rule that reached the buttons and overrode their checked
  background, while their checked text colour stayed dark. The user could
  not tell which of the workspaces they were in.

- **The left rail carried twelve controls** and a quarter of the width on a
  small screen. It carries the input and one action now; the rest moved to
  the Settings tab.

- **Three rows of chrome became one.** The notice, the status line and the
  footer were separate rows; they share one row now, and the social buttons
  moved into the rail.

- **Both result tables showed seven hundred pixels of nothing.** They show
  an empty state now, with the action that fills them.

- **The secondary text failed contrast.** `#5A5370` on the panel is 2.44
  to 1; the muted tone is used for the text now.

### Tests

- `tests/test_ui_layout.py` renders the window at 1280×720, 1366×768,
  1440×900 and 1680×1000 and fails if anything is clipped, if a control is
  smaller than 24px, or if a stylesheet cascades onto the tabs.

## [2.5.1] — 2026-10-21

### Fixed

- **Pasting a YouTube channel queued nothing that could be downloaded.**
  A channel URL does not list the channel's videos — yt-dlp returns the
  channel's *tabs* (Videos, Live, Shorts), and every entry carries the
  24-character channel id. The app turned those into `watch?v=UC...`
  links, which are not videos. The expansion now visits the channel's
  Videos tab, and the Shorts tab as well.

  Verified live on 2026-10-21: @mkbhd, @MrBeast and @veritasium each
  returned two or three tab entries and no video; the Videos tab returns
  the real videos.

### Added

- **A channel's Shorts are fetched too.** A Shorts link downloads on its
  own (verified live: a 59-second Short came through as a 2.6 MB mp4 with
  its audio), and "Also fetch a YouTube channel's Shorts" — on by
  default — adds the channel's Shorts tab to the expansion. Each tab gets
  its own budget, so the videos no longer eat the Shorts' share.

## [2.5.0] — 2026-10-21

### Social Discovery — find a creator's other accounts

Paste a YouTube channel URL, an `@handle` or a channel name (one per line
for a batch) and get the creator's Facebook, Instagram and TikTok accounts
— with the evidence for each answer, and without a single wrong "found".

**How it works**

1. **The channel's own page** is read in a real browser: the display name,
   the handle and the social links the channel lists.
2. **The links the page lists are candidates, not answers.** On MrBeast's
   About page his own accounts and his sponsors' accounts sit in the same
   description element — only the account itself can tell them apart.
3. **When the channel lists nothing, the AI agent proposes** the handles it
   knows (Groq, `openai/gpt-oss-120b`, structured output, ~700 tokens). The
   model may only propose: it never decides a fact, and a channel it does
   not know comes back with no candidates at all.
4. **Every candidate is opened in a real browser** and read: does the
   account exist, and does it say it belongs to this creator (the display
   name, the handle, the links it lists)?

**Why a browser is required**

A plain HTTP request cannot tell a real profile from a made-up one.
Verified on 2026-10-21: Instagram answered both with the same 590 KB page,
TikTok with the same 1.4 KB script shell, and Facebook with the same login
wall. A rendered page answers it — and the previous verifier, which called
any 200 response "verified", was reporting made-up accounts as confirmed.

**The verdicts**

| Verdict | Meaning |
|---|---|
| Found | the account exists and it belongs to this creator |
| Not this creator | the account exists, but it belongs to somebody else |
| Not found | the account does not exist |
| Unknown | we could not check (login wall, rate limit, timeout) — never "missing" |

**Verified live**: Marques Brownlee and MrBeast — the four sponsor accounts
on MrBeast's page (a fitness channel, a car dealership and two more) were
rejected, and only his own accounts were reported. Veritasium, whose
channel page lists nothing, was answered by the agent and confirmed in the
browser on all three platforms.

### Added

- **Chromium ships with the app** (~277 MB, the headless shell). The
  feature works on a machine that has neither Edge nor Chrome; the app
  points Playwright at the shipped copy. Playwright itself stays an
  optional dependency — the app starts without it and the feature says
  what to install.
- The Social Discovery mode in the AI Finder: its own input, its own
  table, its own export, a progress line instead of a dialog, and a cancel
  button.
- `GROQ_API_KEY` in the environment is a local override for the key in
  Settings.

### Security

- A `.env` file is never committed: `.env`, `.env.*` and `.env.local` are
  ignored now. A local key file was untracked but not ignored, and the
  next `git add -A` would have published it.
- The channel description is untrusted text. It is cut to 600 characters,
  passed to the model inside a delimited block, and the model is told to
  ignore instructions inside it.

## [2.4.2] — 2026-10-20

### Niche Research completed

The research suite had working engines but unreliable numbers, several crash
paths and only one of ~16 page-to-page handoffs. This release finishes it.

**Fixed (data was wrong by construction)**
- Keyword demand was overwritten with a constant `100` on every ranking run.
- Ranked-video lists repeated the same video once per run.
- A keyword scored in an earlier run was reset to "unscored" by an unrelated
  research run.
- Re-discovery wiped the "already analysed" marker of a channel.
- The keyword-placement half of the SEO score (34 of 100 points) could never
  fire — no caller ever passed a focus keyword. The Scorecard now has a
  **Focus keyword** field.
- The channel score treated subscribers as views, so engagement was always 0
  and a small channel scored 100 on "growth velocity". Channels are now scored
  on reach (views per subscriber) and output (average views per video).
- Tracked items showed a channel id instead of the channel title, and channel
  uploads always showed `0 views` (flat extraction drops the count).
- "Last discovered" showed an arbitrary niche, not the newest one.

**Fixed (crashes)**
- The Agent tab's **Queue** button called a method that did not exist — every
  click raised `AttributeError`.
- The Scorecard crashed on the *second* failed lookup (deleted empty-state
  widget re-added).
- Closing the AI Analysis modal mid-analysis aborted the process
  (`QDialog.reject()` bypassed `closeEvent`, so the workers were never joined).
- Closing the app left the research poller and its workers running.
- The Niche Discovery niche filter was empty until the format filter was
  touched.
- Two worker threads reaching the database at the same time both opened a
  connection and ran the migrations twice — "duplicate column name" and
  "database is locked". The connection is now opened under the lock.

**Security**
- **The YouTube cookie jar could be sent to any host the user pasted in.**
  The research client attached the configured `cookies.txt` to every yt-dlp
  request, and the channel lookup accepted any input *containing* the text
  `youtube.com` — so `https://attacker.tld/?youtube.com` produced an outbound
  request from the user's machine with their logged-in YouTube session
  attached. The host is now matched exactly, and a non-YouTube target is
  refused before any request is made.
- **The Data API key was written to the log file in cleartext.** It travelled
  as `?key=` in the query string, and httpx logs every request URL at INFO
  into the rotating `app.log` that sits next to the user's data. The key now
  travels in a header, the httpx logger is quietened, and a filter scrubs
  key/token patterns from every log record.
- **A key that could not be encrypted was stored in plain text** — and the
  fallback could never run anyway, because `ctypes.WinError` is a function on
  Python 3.14, so `except (OSError, ctypes.WinError)` raised `TypeError`
  instead of catching. Sealing now fails closed: if Windows refuses to
  protect the key, nothing is stored and the user is told.
- **A database copied to another Windows account could not start the app.**
  DPAPI is user-scoped, and the Settings page reads every key while the
  window is being built; the unseal call was unguarded, so that one case
  made the app fail to start with nothing but a traceback. The key is now
  reported as "needs re-entering" instead.
- **One click could buy several paid AI analyses.** The "Analyze this
  channel" button was a local variable, so it was never disabled: every
  click started another provider call while the first was still running.
  The button is now disabled while the analysis runs, a second click is
  ignored, and a **Cancel** button stops it — the analysis checks the flag
  between providers, so a cancelled analysis never falls through to the next
  paid call.

**Added**
- **Cross-page handoffs:** Niche Discovery → queue / Scorecard / Track / Open,
  Scorecard → AI Analysis / queue / YouTube, Keyword Research → Scorecard,
  Competitors → Scorecard / keyword detail / AI Analysis / queue, AI Analysis →
  Scorecard / queue / Competitors. All eighteen handoffs now exist — six of them
  were listed as done before they had been built. One shared
  `send_to_queue_requested` bridge feeds the download queue; there is no
  second path, and every button is disabled with a reason when it cannot run.
- **A real Dashboard** — metric tiles, top channels, top keywords, a recent
  activity feed and working quick actions (it was a static intro card).
- **Export** on every data page: CSV (Excel-ready), JSON (full data) and
  Markdown (report) for Niche Discovery, Scorecard, Competitors, Keyword
  Research and AI Analysis. Every group of a page survives the export — the
  Competitors CSV and JSON used to keep one group of three. A cell whose
  value starts with `=`, `+`, `-` or `@` is neutralised, so a channel title
  cannot execute a formula when the export is opened in a spreadsheet.
- **A cookies.txt setting** (Settings → YouTube cookies.txt). YouTube's bot
  check blocked the research pages; this is the escape hatch, and it now
  reaches every engine.
- **An app-wide hourly poller** — snapshots are recorded even when the
  Competitors page is not open (VPH and 7-day growth need two snapshots), with
  a configurable interval (30/60/180 min) and failure counts in the summary.
- **Thumbnail generator without an AI analysis** — it was gated behind a
  full chat analysis.
- **A real "Create Similar Channel"** — a nearest-neighbour search over the
  discovered channels with a 0-100 similarity score. It used to compare the
  channel with itself and report 100.
- **An "AI only" filter** in Niche Discovery (the engine supported it, nothing
  could switch it on) and the niche **competition / difficulty** badges. The
  filter now applies to the count as well, so the header does not claim more
  channels than the grid shows.
- The **niche filter** is usable at startup: with "All Formats" selected it
  offers every niche instead of only "All Niches".
- **Analysis progress** — the modal shows which provider is being tried, and
  a **Cancel** button stops the run before the next provider is called.
- **The full analysis is stored, not just the strategy** — `analysis_json`
  now holds the strategy, the ideas, the scripts and the blueprint (rows
  written by the previous release still read back correctly), and each script
  is linked to the content idea it came from.
- **The Data API path carries the same data as the yt-dlp path** — a tracked
  video shows the channel title instead of the channel id, and a channel
  lookup includes the newest uploads with their real view counts.
- **Closing the app while a thumbnail was loading could crash it.** The
  thumbnail loader fetches in a daemon thread, and a request that is still
  inside the socket read when the process goes away takes it down with a
  native access violation in the SSL layer. The loader is now stopped — and
  waited for — when the app closes.
- **PySide6 is pinned to the verified 6.11.x line.** 6.12 aborts during
  teardown in some conditions. `curl_cffi` is pinned to `<0.16` as well:
  0.16 and newer silently break yt-dlp's request handler, which disables the
  TLS impersonation the TikTok fetches need.

**Polish**
- The Competitors sparklines were flat lines for every series above 100
  (view and subscriber counts) — they now scale to their own range.
- The untrack button said "Tracking" while it deleted the item.
- Dead code removed: `trending_engine.get_format_niche_counts`,
  `keyword_engine.decode_term`, `keyword_engine.get_cached_keywords`,
  `scorecard_engine.score_label`, `autocomplete.expand_seed`, `db.vacuum`,
  plus six dead QSS rules.

### Download engine (same release)

### Fixed
- **YouTube downloads failing everywhere** — every YouTube download died with
  "Sign in to confirm you're not a bot". Root cause: yt-dlp 2026.x asks
  YouTube's default `web` player client for a PO token, and only a real browser
  can mint one, so the request is bot-checked. Every yt-dlp options builder
  (downloads, TikTok account fetch, YouTube playlist/channel expansion,
  research client, agent search) now passes `js_runtimes` for
  deno/node/bun/quickjs so the EJS challenges have a runtime, **and** YouTube
  downloads now request the PO-token-free `web_embedded` / `mweb` clients
  first, with `web` kept as the cookie-friendly fallback. Guarded by
  regression tests.
- **TikTok profile fetch produced undownloadable links** — expanding a
  TikTok profile queued the signed CDN media URL that TikTok puts in each
  listing entry. Those links answer `HTTP 403 Forbidden`, so every video
  failed. The queue now gets the stable page URL
  (`tiktok.com/@user/video/<id>`), and CDN media links are no longer
  accepted as queueable TikTok links.
- **Download failures showed a useless message** — the extractor error was
  discarded and every failure surfaced as "Download finished but the file is
  missing". The real reason (bot check, 403, missing ffmpeg) now reaches the
  queue row and is written to the app log.
- **Portable builds shipped without ffmpeg** — "Best available" downloads
  video and audio as separate streams and yt-dlp needs ffmpeg to merge them.
  `build_release.bat` now stages `ffmpeg.exe` into `release\portable\bin\`
  (the engine already looks there), so the portable build works on machines
  that have no ffmpeg installed.
- Friendlier, actionable messages for the two flaky upstream failures:
  YouTube's bot check (wait / Chrome cookies) and TikTok's intermittent
  "Unable to extract secondary user ID" profile fetch (retry in a few
  minutes — TikTok-side flakiness that persists on latest yt-dlp 2026.8.19).


## [2.4.1] — 2026-09-11

### Fixed
- **TikTok account (profile) fetch regression** — "Couldn't fetch that account"
  in the Account tab. Root cause: bundled yt-dlp was too old to parse TikTok's
  current profile pages ("Unable to extract secondary user ID"). Bundled
  yt-dlp is now **2026.8.19+**; `yt-dlp>=2026.8.19` is pinned in
  `requirements.txt` / `pyproject.toml`, and the floor is guarded by a
  regression test so it can't silently drop again.

## [2.4.0] — 2026-09-10

### Added
- **AI thumbnail generation in Niche Research** — channel analyses can now
  generate a thumbnail from any AI provider with an auto fallback chain
  (aihubmix → Google AI → OpenRouter). A clear "No AI image provider
  configured" error guides you to Settings instead of silently failing.
  The **Google AI key** now actually reaches channel analysis (Settings key
  `google_ai_api_key` was being read under the wrong name).
- **Paste a TikTok profile URL and it auto-expands** into its videos in the
  downloader — profile links are routed into the expand queue via the
  account-based fetch thread.
- **Clickable verified badges & channel links** in the AI Channel Finder
  results (channel titles, verified FB/IG/TikTok badges, TikTok YouTube
  channel + URL cells) — one click opens the link.
- **Selectable text everywhere in Niche Research** — channel names, stats,
  strategy rows, ideas, scripts, and trending card values can be copied,
  and long trend-card titles now word-wrap instead of getting clipped.
- A single analysis modal per session (no stacking when clicking
  "Create Similar Channel" repeatedly).

### Fixed
- **Trending card crash on re-render** — the Analyze → reload path crashed
  when `_clear_layout` hit the trailing stretch spacer; the rebuild no longer
  dies on non-widget layout items.
- **Empty / blocked profile pictures** no longer break avatar thumbnails —
  they fall back to the clean initials treatment.
- **Stacked confirm dialogs** in the AI Channel Finder replaced with inline
  status messages (send-to-queue, copy FB/IG/TikTok links, CSV/JSON export);
  only genuine errors still pop a dialog.

### Changed
- **UI tightness pass**: trending cards are a uniform 300px with wrapped
  titles; the agent results table is read-only with no grid lines, hidden
  row numbers, and extended row selection; the research dashboard spacing
  is tightened (no more floating gap between the intro card and the
  quick-start hints).

## [2.3.0] — 2026-09-10

### Fixed
- **Channel video counts were always "0"** in Niche Discovery / Scorecard /
  AI Analysis: `channel_video_count` does not exist in yt-dlp; the pipeline now
  falls back to `playlist_count`, so totals like "1.2K videos" match the web tool.
- **Channel stat downloads blocked the UI** — avatars and video thumbs now load
  asynchronously off the GUI thread with a disk cache, a `maxres→hq→mq` fallback
  chain, and a smooth crop instead of a stretch.
- **Avatar placeholders were broken**: a channel with no real profile picture
  showed a red "error" gradient instead of a clean initials avatar; it now falls
  back to the "S-Q" cyan→teal initials treatment.
- Scorecard/AI Analysis no longer show a fabricated `0` for stats that keyless
  research couldn't measure — unknown counts display a neutral `—`; the DB stores
  NULL instead of zero for unknown totals.

### Added
- **YouTube Data API key field in Settings** (optional): unlocks exact channel
  stats — total uploads, total views, join date — matching the web tool. Search &
  discovery stay keyless (yt-dlp). The "Default AI provider" dropdown is now
  visible (it was silently hidden on small windows).
- Research UI now renders with the app's font family (`Segoe UI Variable
  Display` → `Segoe UI` → `Inter`) so the whole suite reads as one brand.

### Changed
- Keyword detail metrics and analysis-modal stat tiles start at `—` instead of `0`
  until real data arrives.

## [2.2.0] — 2026-09-10

### Changed
- **Rebranded to S-Q Creator Studio** — the downloader, AI Channel Finder, and Niche Research suites now ship under one creator-brand. Window title, installer (per-user), portable build, and release artifacts are named `S-Q Creator Studio`.
- On-disk identity (`%LOCALAPPDATA%\S-Q-Ali Media Downloader`) is intentionally unchanged so settings, the saved queue, and the sealed research DB survive the update untouched.

## [2.1.0] — 2026-08-28

### Added
- **Cross-platform Social Matrix (AI Finder):** new *Discovery Mode* selector —
  "YouTube → Socials (FB/IG/TikTok)" and "TikTok → YouTube (Creators Without YT)".
- TikTok-first discovery: finds TikTok creator profiles by keyword/tag
  (yt-dlp flat extraction with HTML `uniqueId` harvest fallback), enriches
  follower counts/bio, then detects YouTube presence via bio links and
  bidirectional name-similarity + backlink confirmation.
- Creators **without a YouTube channel** are flagged `TARGET_NO_YOUTUBE`
  (with `NEEDS_REVIEW` for inconclusive probes) and can be exported to
  CSV/JSON, copied, or queued directly.
- TikTok presence probing for YouTube channels (`TARGET_NO_SOCIALS` matrix
  now covers Facebook, Instagram, and TikTok).
- **TikTok mode input flexibility:** paste `@handles` / `tiktok.com/@…` URLs
  directly (always works — no listing scraping needed), `#tag` queries now
  hit TikTok tag pages (yt-dlp does not support search URLs), and an optional
  **cookies.txt** file (TikTok mode "Browse…") unlocks tag/keyword listing
  data where TikTok allows it.
- New `INCONCLUSIVE` social status surfaced in the UI (yellow "? Unconfirmed")
  so network/rate-limit failures are never mistaken for "missing".

### Fixed
- Network errors and rate-limits no longer report socials as NOT_FOUND
  (they are INCONCLUSIVE) — target lists stop inflating with false positives.
- Facebook login-wall responses no longer mark real pages as missing
  (one mobile-UA retry; ambiguous bodies are inconclusive).
- Removed dead Instagram oEmbed fallback (endpoint deprecated by Meta).
- Explicit bio links found in a channel's own description can no longer be
  downgraded to NOT_FOUND by a failed probe (worst case: UNVERIFIED_HANDLE).
- `profile.php?id=` Facebook links keep their numeric id (no more
  query-string stripping); dead `FB_HANDLE_PATTERN` logic replaced with
  priority-ranked matching (vanity page > profile id > people > pages > groups).
- IG text-handle regex now word-boundary anchored with a mandatory separator
  ("config: name" and "instagram.com/explore/" no longer produce ghost handles).
- Zero-key yt-dlp search no longer fabricates YouTube handles from channel
  display names (which caused false FB/IG handle probes).
- `has_no_socials` now counts only platforms the user actually enabled.

### Changed
- Results table adapts per mode; opportunity flags, TikTok columns, and
  YouTube-existence columns added; CSV/JSON exports extended.
- Test suite expanded to 67 tests (100% passing); ruff clean.

### Known limitation (verified 2026-08-29)
- Anonymous TikTok **listing discovery** (keyword/`#tag` search) is blocked by
  TikTok for logged-out visitors (empty JS shells; yt-dlp search URLs
  unsupported, tag extractor broken upstream). Use seed profiles
  (`@handle` / profile URLs) or a cookies.txt file. YouTube-existence
  checking is unaffected.

### Engineering hardening (2026-09-09)
- **One theme.** The research suite now renders the app's single dark
  ink-plum/cyan system — the red accent, zinc cards, and OS light/dark
  switching are gone (`research_style()` always returns dark).
- **Secrets at rest.** API keys are sealed with Windows DPAPI in the settings
  store (plaintext rows migrate on first read); Gemini keys move out of the
  query string into the `x-goog-api-key` header.
- **WCAG-AA contrast.** Faint text lifted to `#8B83A0`; score/competition/SEO
  badge fills moved to the Tailwind-700 family; light secondary text now
  `#52525b`.
- **Version single-source.** Title bar, installer names, README, and packaging
  all derive from `__version__` (`2.1.0`).
- **Tests** grew to a QSS-parse regression for both stylesheets plus
  metadata-extractor and orchestrator control-flow coverage.
- **Git hygiene.** Session exports and personal `opencode.json` are ignored;
  a stray `W` token at the end of the research stylesheet removed.
- **CI.** Runs on Python 3.14, builds via `python -m PyInstaller`, and gates
  on `pip-audit`.
- **Dependencies.** `curl_cffi` pin relaxed to `>=0.15,<0.18`;
  `httpx`/`pydantic`/`beautifulsoup4` declared in `pyproject.toml`.

## [2.0.0] — 2026-08-06

### Added
- Open source release under the MIT license; activation keys removed entirely.
- Rebranded to **S-Q-Ali Media Downloader** with a new icon and dark cyan theme.
- YouTube support alongside TikTok — playlists and channels expand into
  individual videos automatically in the background.
- Per-platform download options (TikTok uses Chrome impersonation; YouTube
  uses native format selection).
- Audio-only preset (MP3) via bundled ffmpeg.
- Per-user Inno Setup installer (no admin required) that bundles ffmpeg.

### Changed
- Source reorganized into a proper `src/s_q_ali_media_downloader` package.
- Added pytest suite, ruff linting, and a GitHub Actions CI pipeline.

### Fixed
- Impersonation failure label now shows the underlying error instead of a
  literal `{exc}` placeholder.

### Removed
- Legacy activation gate and ANAS license keys (kept in git history only).
- Old `Anas Media Downloader` branding and orphaned artifacts.
