# Graph Report - S Q Ali Media Downloader  (2026-09-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1165 nodes · 2525 edges · 62 communities (51 shown, 11 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 272 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dc25b211`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AnalysisModal
- niche_research/ui/widgets.py
- MainWindow
- engine.py
- LinkParserTool
- youtube_client.py
- main_window.py
- ai_analysis_engine.py
- test_niche_ai_engine.py
- ResearchContainer
- trending_engine.py
- ChannelInfo
- KeywordResearchPage
- AgentTabWidget
- test_niche_youtube_client.py
- SocialVerifierTool
- TikTokSearchTool
- test_tiktok_pipeline.py
- scorecard_engine.py
- CompetitorsPage
- test_niche_trending_engine.py
- ScorecardPage
- TrendingChannelsPage
- research_style
- keyword_engine.py
- SocialStatus
- YouTubeFetchThread
- niches.py
- fetch_suggestions
- test_niche_keyword_engine.py
- test_niche_scorecard_engine.py
- test_niche_ui.py
- AgentOrchestrator
- .add_links
- competitor_engine.py
- storage/__init__.py
- test_niche_competitor_engine.py
- test_niche_competitor_ui.py
- TikTokApiSession
- QVBoxLayout
- now
- db.py
- YouTubeExistenceTool
- trending_page.py
- test_niche_db.py
- test_niche_keyword_ui.py
- test_theme.py
- tiktok_api.py
- SettingsPage
- NichePoller
- YoutubeApiError
- conftest.py
- .cookiefile
- tiktok_search.py
- graphify.js
- TrendingDiscoveryWorker
- opencode.json
- s_q_ali_media_downloader/__init__.py
- data/__init__.py
- niche_research/__init__.py
- s_q_ali_media_downloader/ui/__init__.py
- s-q-ali-media-downloader

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 74 edges
2. `AnalysisModal` - 48 edges
3. `ChannelInfo` - 36 edges
4. `TrendingChannelsPage` - 33 edges
5. `TikTokSearchTool` - 32 edges
6. `ResearchContainer` - 31 edges
7. `AgentTabWidget` - 30 edges
8. `KeywordResearchPage` - 28 edges
9. `VideoInfo` - 28 edges
10. `CompetitorsPage` - 26 edges

## Surprising Connections (you probably didn't know these)
- `test_load_channel_analysis_data_recent_videos()` --uses--> `ChannelInfo`  [INFERRED]
  tests/test_niche_ai_engine.py → src/s_q_ali_media_downloader/niche_research/tools/youtube_client.py
- `_channel()` --uses--> `ChannelInfo`  [INFERRED]
  tests/test_niche_competitor_engine.py → src/s_q_ali_media_downloader/niche_research/tools/youtube_client.py
- `test_channel_seo_score()` --uses--> `ChannelInfo`  [INFERRED]
  tests/test_niche_scorecard_engine.py → src/s_q_ali_media_downloader/niche_research/tools/youtube_client.py
- `test_lookup_channel_flow()` --uses--> `ChannelInfo`  [INFERRED]
  tests/test_niche_scorecard_engine.py → src/s_q_ali_media_downloader/niche_research/tools/youtube_client.py
- `test_lookup_channel_handle_url_passthrough()` --uses--> `ChannelInfo`  [INFERRED]
  tests/test_niche_scorecard_engine.py → src/s_q_ali_media_downloader/niche_research/tools/youtube_client.py

## Import Cycles
- None detected.

## Communities (62 total, 11 thin omitted)

### Community 0 - "AnalysisModal"
Cohesion: 0.06
Nodes (24): QDialog, AnalysisModal, AnalyzeWorker, ChannelDataWorker, _fmt(), QThread, QWidget, ThumbnailWorker (+16 more)

### Community 1 - "niche_research/ui/widgets.py"
Cohesion: 0.05
Nodes (26): Orientation, QLayout, QRect, QSize, AvatarInitials, AvatarThumbnail, competition_color(), CompetitionBadge (+18 more)

### Community 2 - "MainWindow"
Cohesion: 0.10
Nodes (6): QMainWindow, default_output_dir(), MainWindow, queue_file(), Receives individual video URLs from a YouTube channel/playlist fetch and shows…, storage_dir()

### Community 3 - "engine.py"
Cohesion: 0.07
Nodes (27): DownloadThread, human_size(), impersonate_target(), impersonation_summary(), is_permanent(), _listdir(), normalize_account(), platform_of() (+19 more)

### Community 4 - "LinkParserTool"
Cohesion: 0.10
Nodes (28): LinkParserTool, Tool for extracting Facebook, Instagram, TikTok, and YouTube URLs and handles…, Extracts handle string from a FB/IG/TikTok URL., Strips tracking params but preserves profile.php?id= payloads., Lower = higher priority. Vanity pages first, groups last., Extracts social URLs and handles from channel metadata, descriptions, and link…, Extracts primary (facebook_url, instagram_url, tiktok_url) from raw text and…, MetadataExtractorTool (+20 more)

### Community 5 - "youtube_client.py"
Cohesion: 0.13
Nodes (34): datetime, _base_opts(), _chunks(), _extract(), fetch_channel(), fetch_channels(), _fetch_channels_via_api(), fetch_video() (+26 more)

### Community 6 - "main_window.py"
Cohesion: 0.10
Nodes (21): main(), Application entry point for S-Q-Ali Media Downloader., is_youtube_url(), Run the app with ``python -m s_q_ali_media_downloader``., Visual identity for S-Q-Ali Media Downloader. Palette: ink-plum base with a…, Main window for S-Q-Ali Media Downloader., resource(), Chip (+13 more)

### Community 7 - "ai_analysis_engine.py"
Cohesion: 0.13
Nodes (30): analyze_channel(), asdict_strategy(), build_analysis_prompt(), call_provider(), ChannelAnalysis, ContentIdea, generate_thumbnail(), get_analysis() (+22 more)

### Community 8 - "test_niche_ai_engine.py"
Cohesion: 0.08
Nodes (13): parametrize, _db(), fixture, Tests for the AI analysis + thumbnail engine., _SeqClient, _StatusResponse, test_analyze_channel_runs_and_persists(), test_build_prompt_contains_channel_and_top_videos() (+5 more)

### Community 9 - "ResearchContainer"
Cohesion: 0.12
Nodes (17): QFrame, QWidget, Refresh the visible page's data (live scan / re-research / snapshots)., ResearchContainer, _db(), fixture, Offscreen tests for the ResearchContainer + main-window research tab., test_container_analysis_signal() (+9 more)

### Community 10 - "trending_engine.py"
Cohesion: 0.13
Nodes (27): calculate_growth_rate(), calculate_viral_score(), _channel_created_at(), _dedupe_videos(), detect_ai_generated(), discover_trending_channels(), get_trending_channel_count(), get_trending_channels() (+19 more)

### Community 11 - "ChannelInfo"
Cohesion: 0.14
Nodes (17): Dual-mode YouTube Discovery Engine (YouTube Data API v3 + yt-dlp Zero-Key…, Zero-Key channel discovery via the shared yt-dlp client (impersonation +…, Maps a shared ChannelInfo into the Agent's ChannelMetadata schema., Discovers YouTube channels by prompt, tag/hashtag, or channel name., Formats integer subscriber count (e.g. 1820000 -> 1.8M)., Entry point: Uses YouTube Data API if key is available, else yt-dlp scraper., Queries YouTube Data API v3 search.list and channels.list., YouTubeSearchTool (+9 more)

### Community 12 - "KeywordResearchPage"
Cohesion: 0.13
Nodes (8): ResearchOutput, _is_tracked(), KeywordResearchPage, KeywordResearchWorker, Any, QThread, QWidget, Re-run research with the last seed (used by the container Update button).

### Community 13 - "AgentTabWidget"
Cohesion: 0.10
Nodes (6): AgentTabWidget, AgentWorkerThread, QThread, QWidget, Main UI view for AI Channel & Social Presence Discovery Agent., Background worker thread for running AgentOrchestrator without blocking Qt main…

### Community 14 - "test_niche_youtube_client.py"
Cohesion: 0.08
Nodes (4): Network/tooling for the Niche Research suite (yt-dlp client, autocomplete)., _isolated_db(), fixture, Tests for the Niche Research yt-dlp YouTube client.

### Community 15 - "SocialVerifierTool"
Cohesion: 0.12
Nodes (16): Response, Verifies if a Facebook page exists., Verifies if an Instagram profile exists., Verifies if a TikTok profile exists., Probes Facebook, Instagram, and TikTok in parallel., Probes Facebook, Instagram, and TikTok profile existence asynchronously., Applies the bio-link downgrade rule on a failed/ambiguous probe., Classifies a 200 response body into a SocialStatus. (+8 more)

### Community 16 - "TikTokSearchTool"
Cohesion: 0.14
Nodes (16): A TikTok creator profile discovered by the TikTok-first search mode., TikTokProfileMetadata, Common yt-dlp options: impersonation + optional cookies file., Extracts @handles / profile URLs typed directly into the query., Dedupes handles into profiles and enriches them (best effort)., Flat-extracts a TikTok listing URL, collecting uploader handles., Pulls the creator handle out of a flat TikTok video entry., Cookies-aware harvest of uniqueId / @handle tokens from TikTok HTML. (+8 more)

### Community 17 - "test_tiktok_pipeline.py"
Cohesion: 0.11
Nodes (24): name_similarity(), Normalized similarity in [0, 1] between two creator names/handles., Unit tests for the TikTok discovery pipeline (offline, faked responses)., test_api_handles_parses_item_list(), test_cookie_loader_parses_netscape(), test_cookie_loader_tolerates_missing_file(), test_cookiefile_property_refreshes_api_session(), test_cookiefile_property_resets_session_when_cleared() (+16 more)

### Community 18 - "scorecard_engine.py"
Cohesion: 0.16
Nodes (23): _age_days(), ChannelLookupResult, _clamp(), compute_channel_seo_score(), compute_seo_score(), compute_vph(), contains_keyword(), _fmt_views_per_day() (+15 more)

### Community 19 - "CompetitorsPage"
Cohesion: 0.16
Nodes (9): CompetitorsPage, _fmt(), Any, QFrame, QLabel, QThread, QWidget, RefreshWorker (+1 more)

### Community 20 - "test_niche_trending_engine.py"
Cohesion: 0.12
Nodes (15): _channel(), _isolated_db(), _make_raw_video(), fixture, Tests for the trending channel engine (ported from Niche-Scope…, test_detect_ai_faceless_bonus(), test_detect_ai_generated_contributions(), test_discover_duration_filters() (+7 more)

### Community 21 - "ScorecardPage"
Cohesion: 0.19
Nodes (7): _mark_tracked(), QFrame, QThread, QWidget, ScorecardPage, ScorecardWorker, _SeoPanel

### Community 23 - "research_style"
Cohesion: 0.17
Nodes (13): AnalysisModal — AI channel strategy, ideas, scripts, blueprint + thumbnail.…, Competitors page — dashboard of tracked videos / channels / keywords. Ported…, Niche Research UI package (Niche-Scope style widgets and pages)., Keyword Research page — autocomplete expansion + scored results table + detail.…, ResearchContainer — sidebar + stacked research pages for the main nav. Ported…, Settings page — API keys for the AI analysis / thumbnail providers., _build_qss(), Niche-Scope themed stylesheet for the research UI (Tailwind zinc + red-600).… (+5 more)

### Community 24 - "keyword_engine.py"
Cohesion: 0.22
Nodes (16): CompetitionLabel, competition_from_views(), competition_label(), compute_demand(), _fetch_suggestions_safe(), KeywordResult, overall_score(), rank_keyword() (+8 more)

### Community 25 - "SocialStatus"
Cohesion: 0.21
Nodes (13): Enum, Autonomous YouTube Channel & Social Verification Agent Module., Data schemas for YouTube Discovery and Social Presence Agent., SocialPlatform, SocialPresence, SocialStatus, Asynchronous Verification Engine for Facebook, Instagram, and TikTok Profile…, YouTube Presence Detector for TikTok Creators (bio links + bidirectional search… (+5 more)

### Community 26 - "YouTubeFetchThread"
Cohesion: 0.12
Nodes (11): patch, AccountFetchThread, find_ffmpeg(), QThread, Lists a public account's newest videos without downloading them., Expands a YouTube playlist or channel into individual video URLs., YouTubeFetchThread, Tests for YouTubeFetchThread — verifies playlistend is honored without… (+3 more)

### Community 27 - "niches.py"
Cohesion: 0.15
Nodes (10): format_name(), get_niche(), get_niches(), Niche, Niche catalog — ported from Niche-Scope's lib/niches.ts., Return niches, optionally filtered by format id ('longform' | 'shortform')., Rpm, VideoFormat (+2 more)

### Community 28 - "fetch_suggestions"
Cohesion: 0.19
Nodes (15): _add_dedup(), AutocompleteError, expand_seed(), fetch_suggestions(), Exception, Keyless YouTube autocomplete (ported from Niche-Scope's lib/autocomplete.ts).…, Fetch YouTube autocomplete suggestions for a query. Best-effort + retry., Expand a seed by appending a-z / 0-9 prefixes and question words. (+7 more)

### Community 29 - "test_niche_keyword_engine.py"
Cohesion: 0.12
Nodes (3): Tests for the keyword engine (ported from Niche-Scope's keywordEngine.ts)., test_get_ranked_videos_joins_videos(), _video()

### Community 30 - "test_niche_scorecard_engine.py"
Cohesion: 0.11
Nodes (6): Tests for the scorecard + VPH engine (ported from scorecard.ts / vphEngine.ts)., test_channel_seo_score(), test_lookup_channel_flow(), test_lookup_channel_handle_url_passthrough(), test_lookup_video_flow(), test_save_video_snapshot_idempotent()

### Community 31 - "test_niche_ui.py"
Cohesion: 0.12
Nodes (11): _FakeMessageBox, Offscreen tests for the Niche Research UI (theme, widgets, trending page)., _sample(), test_discovery_start_forces_refresh(), test_discovery_worker_passes_force(), test_start_discovery_full_scan_asks_confirmation(), test_trending_card_emits_analyze(), test_trending_page_empty_state() (+3 more)

### Community 32 - "AgentOrchestrator"
Cohesion: 0.24
Nodes (11): BaseModel, AgentOrchestrator, Agent Orchestrator controller for YouTube discovery and cross-platform social…, Runs async verification probes for list of channels., TikTok-first mode: find creators, flag those WITHOUT a YouTube channel., Orchestrates multi-tool execution DAG for channel discovery & social presence…, Executes full autonomous agent pipeline., AgentSearchResult (+3 more)

### Community 33 - ".add_links"
Cohesion: 0.18
Nodes (14): is_profile_url(), is_tiktok_url(), is_youtube_channel_url(), is_youtube_playlist_url(), normalize_youtube_channel_url(), Ensures youtube.com/UC... shorthand URLs are normalized to…, URL classification and account normalisation., test_profile_urls() (+6 more)

### Community 34 - "competitor_engine.py"
Cohesion: 0.21
Nodes (15): get_competitor_dashboard(), get_tracked_channels(), get_tracked_keywords(), get_tracked_videos(), Any, Competitor dashboard: tracked videos / channels / keywords + snapshot refresh.…, Score history + latest rankings for tracked keywords., Latest stats + VPH series for every tracked 'video' item. (+7 more)

### Community 35 - "storage/__init__.py"
Cohesion: 0.17
Nodes (12): Research engines for the Niche Research suite (discovery, keywords, etc.)., Persistence layer for the Niche Research suite., _fmt_duration(), Scorecard page — paste a video/channel URL and get a vidIQ-style SEO score.…, Offscreen tests for the Scorecard page., test_fmt_duration(), test_mode_toggle(), test_scorecard_placeholder_and_failure() (+4 more)

### Community 36 - "test_niche_competitor_engine.py"
Cohesion: 0.22
Nodes (14): _channel(), _configure_db(), _now_ms(), fixture, Tests for the competitor dashboard + snapshot refresh engine., test_get_competitor_dashboard_aggregates(), test_get_tracked_channels_growth7d(), test_get_tracked_channels_no_growth() (+6 more)

### Community 37 - "test_niche_competitor_ui.py"
Cohesion: 0.22
Nodes (15): _db(), _labels(), fixture, Offscreen tests for the Competitors dashboard page., _seed_channel(), _seed_keyword(), _seed_video(), test_channel_card_shows_growth() (+7 more)

### Community 38 - "TikTokApiSession"
Cohesion: 0.24
Nodes (4): _clean_handles(), Client, Best-effort TikTok listing client backed by a Netscape cookies.txt., TikTokApiSession

### Community 39 - "QVBoxLayout"
Cohesion: 0.26
Nodes (3): QPushButton, QVBoxLayout, Auto-hide the left rail on the Niche Research tab so it gets full width.

### Community 40 - "now"
Cohesion: 0.22
Nodes (12): Cursor, Re-fetch every tracked item and record a fresh snapshot row. Stores a…, refresh_snapshots(), json_dumps(), save_channel_snapshot(), save_video_snapshot(), update_last_analyzed(), now() (+4 more)

### Community 41 - "db.py"
Cohesion: 0.21
Nodes (10): Connection, configure(), _connect(), db_path(), exec_many(), Any, SQLite persistence for the Niche Research suite. Schema is mirrored from Niche-…, Resolve the SQLite database file path. (+2 more)

### Community 42 - "YouTubeExistenceTool"
Cohesion: 0.24
Nodes (10): True if the YouTube channel page references the TikTok profile., Checks whether TikTok profiles already run a YouTube channel., Synchronous presence check for one TikTok profile., YouTubeExistenceTool, _profile(), test_bidirectional_backlink_confirms_verified(), test_no_bio_link_and_no_candidates_is_not_found(), test_strong_name_match_flags_unverified() (+2 more)

### Community 43 - "trending_page.py"
Cohesion: 0.31
Nodes (7): QFrame, QWidget, Niche-Scope style trending channel card (ported from TrendingChannelCard.tsx)., _stat_block(), TrendingCardData, TrendingChannelCard, Niche Discovery page — trending channel card grid (Niche-Scope look).

### Community 44 - "test_niche_db.py"
Cohesion: 0.18
Nodes (3): _isolated_db(), fixture, Tests for the Niche Research SQLite persistence layer.

### Community 45 - "test_niche_keyword_ui.py"
Cohesion: 0.24
Nodes (7): Offscreen tests for the Keyword Research page widgets., _seed_output(), test_keyword_page_detail_view(), test_keyword_page_failed(), test_keyword_page_renders_results(), test_keyword_re_run_noop_without_results(), test_keyword_re_run_restarts_last_search()

### Community 47 - "tiktok_api.py"
Cohesion: 0.48
Nodes (6): _double_md5(), generate_xbogus(), _md5_user_agent(), TikTok listing data via customer-authorized requests (web API + HTML). TikTok…, _rc4(), test_generate_xbogus_is_deterministic_and_shape_stable()

### Community 49 - "NichePoller"
Cohesion: 0.50
Nodes (3): QObject, NichePoller, Hourly background snapshot poller (VPH + growth history).

### Community 50 - "YoutubeApiError"
Cohesion: 0.40
Nodes (5): NotFoundError, Exception, Base error for all YouTube fetch failures., The requested video/channel does not exist or was removed., YoutubeApiError

### Community 51 - "conftest.py"
Cohesion: 0.50
Nodes (4): isolated_appdata(), fixture, qapp(), Shared fixtures. Offscreen Qt platform so GUI tests run headless.

### Community 52 - ".cookiefile"
Cohesion: 0.50
Nodes (3): setter, Path to the Netscape cookies.txt in use (or None)., (Re)builds the API session so signed listings carry the cookies.

### Community 53 - "tiktok_search.py"
Cohesion: 0.50
Nodes (3): format_followers(), TikTok Creator Discovery Engine (yt-dlp flat extraction + HTML fallback, zero…, test_format_followers()

## Knowledge Gaps
- **3 isolated node(s):** `VideoFormat`, `$schema`, `s-q-ali-media-downloader`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 371 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `.add_links`, `engine.py`, `main_window.py`, `QVBoxLayout`, `ResearchContainer`, `AgentTabWidget`, `YouTubeFetchThread`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `ResearchContainer` connect `ResearchContainer` to `AnalysisModal`, `MainWindow`, `main_window.py`, `QVBoxLayout`, `KeywordResearchPage`, `SettingsPage`, `NichePoller`, `CompetitorsPage`, `ScorecardPage`, `TrendingChannelsPage`, `research_style`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `AgentTabWidget` connect `AgentTabWidget` to `AgentOrchestrator`, `MainWindow`, `main_window.py`, `QVBoxLayout`, `SocialStatus`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `MainWindow` (e.g. with `AccountFetchThread` and `DownloadThread`) actually correct?**
  _`MainWindow` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `AnalysisModal` (e.g. with `ResearchContainer` and `test_modal_content_is_scrollable()`) actually correct?**
  _`AnalysisModal` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `QVBoxLayout` (e.g. with `._build()` and `._make_channel_card()`) actually correct?**
  _`QVBoxLayout` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `ChannelInfo` (e.g. with `YouTubeSearchTool` and `build_analysis_prompt()`) actually correct?**
  _`ChannelInfo` has 25 INFERRED edges - model-reasoned connections that need verification._