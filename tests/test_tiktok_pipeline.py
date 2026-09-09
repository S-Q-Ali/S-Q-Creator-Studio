"""Unit tests for the TikTok discovery pipeline (offline, faked responses)."""

from s_q_ali_media_downloader.agent.schema import SocialStatus, TikTokProfileMetadata
from s_q_ali_media_downloader.agent.tools.tiktok_search import (
    TikTokSearchTool,
    format_followers,
)
from s_q_ali_media_downloader.agent.tools.youtube_existence import (
    YouTubeExistenceTool,
    name_similarity,
)

# ---------------------------------------------------------------------------
# TikTokSearchTool
# ---------------------------------------------------------------------------


def test_format_followers():
    assert format_followers(1_500_000) == "1.5M"
    assert format_followers(24_000) == "24.0K"
    assert format_followers(733) == "733"


def test_handle_from_entry_url():
    entry = {"webpage_url": "https://www.tiktok.com/@clip_machine/video/73123"}
    assert TikTokSearchTool._handle_from_entry(entry) == "clip_machine"


def test_handle_from_entry_uploader():
    entry = {"uploader": "@daily_edits"}
    assert TikTokSearchTool._handle_from_entry(entry) == "daily_edits"


def test_handle_from_entry_garbage_uploader():
    entry = {"uploader": "Some Creator Name!"}
    assert TikTokSearchTool._handle_from_entry(entry) is None


def test_search_profiles_dedupes_and_excludes(monkeypatch):
    tool = TikTokSearchTool()
    handles = ["creator_a", "creator_a", "tiktok", "creator_b", "x", "creator_c"]
    monkeypatch.setattr(tool, "_discover_via_ytdlp", lambda query: list(handles))
    monkeypatch.setattr(tool.api_session, "fetch_tag_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool.api_session, "fetch_search_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool, "_discover_via_html", lambda url: [])
    monkeypatch.setattr(tool, "enrich_profile", lambda p: p)
    profiles = tool.search_profiles("query", max_profiles=50)
    names = [p.handle for p in profiles]
    assert names.count("creator_a") == 1
    assert "tiktok" not in names
    assert "x" not in names  # too short
    assert all(p.profile_url.startswith("https://www.tiktok.com/@") for p in profiles)


# ---------------------------------------------------------------------------
# name_similarity
# ---------------------------------------------------------------------------


def test_name_similarity_exact():
    assert name_similarity("speed edits", "SpeedEdits") == 1.0


def test_name_similarity_token_overlap():
    assert name_similarity("speed_edits", "Speed Edits Official") >= 0.8


def test_name_similarity_disjoint():
    assert name_similarity("cooking_stuff", "car_reviews") < 0.5


# ---------------------------------------------------------------------------
# YouTubeExistenceTool — bio link path (no network needed)
# ---------------------------------------------------------------------------


def _profile(bio: str) -> TikTokProfileMetadata:
    return TikTokProfileMetadata(
        profile_id="tester",
        handle="tester",
        nickname="Tester",
        bio=bio,
        profile_url="https://www.tiktok.com/@tester/",
    )


def test_youtube_bio_link_is_verified():
    tool = YouTubeExistenceTool()
    presence = tool.check_youtube_presence(
        _profile("daily edits! youtube.com/@testerclips check it")
    )
    assert presence.status == SocialStatus.VERIFIED
    assert presence.source == "bio_link"
    assert presence.confidence_score == 0.95
    assert presence.verified_url is not None


def test_no_bio_link_and_no_candidates_is_not_found(monkeypatch):
    tool = YouTubeExistenceTool()
    monkeypatch.setattr(
        tool.search_tool,
        "search_channels",
        lambda query, max_results=10, min_subscribers=0: [],
    )
    presence = tool.check_youtube_presence(_profile("just vibing, no links"))
    assert presence.status == SocialStatus.NOT_FOUND


def test_weak_name_match_is_not_found(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import ChannelMetadata

    tool = YouTubeExistenceTool()
    far_channel = ChannelMetadata(
        channel_id="UC1",
        title="Completely Different Channel",
        youtube_url="https://www.youtube.com/channel/UC1",
    )
    monkeypatch.setattr(
        tool.search_tool,
        "search_channels",
        lambda query, max_results=10, min_subscribers=0: [far_channel],
    )
    presence = tool.check_youtube_presence(_profile("no links here"))
    assert presence.status == SocialStatus.NOT_FOUND


def test_strong_name_match_flags_unverified(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import ChannelMetadata

    tool = YouTubeExistenceTool()
    near_channel = ChannelMetadata(
        channel_id="UC2",
        title="Tester",
        handle="@tester",
        youtube_url="https://www.youtube.com/channel/UC2",
    )
    monkeypatch.setattr(
        tool.search_tool,
        "search_channels",
        lambda query, max_results=10, min_subscribers=0: [near_channel],
    )
    monkeypatch.setattr(
        YouTubeExistenceTool, "_channel_links_to_tiktok", lambda self, url, handle: False
    )
    presence = tool.check_youtube_presence(_profile("no links in bio"))
    assert presence.status == SocialStatus.UNVERIFIED_HANDLE
    assert presence.source == "name_match"


def test_bidirectional_backlink_confirms_verified(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import ChannelMetadata

    tool = YouTubeExistenceTool()
    near_channel = ChannelMetadata(
        channel_id="UC3",
        title="Tester Clips",
        handle="@tester",
        youtube_url="https://www.youtube.com/channel/UC3",
    )
    monkeypatch.setattr(
        tool.search_tool,
        "search_channels",
        lambda query, max_results=10, min_subscribers=0: [near_channel],
    )
    monkeypatch.setattr(
        YouTubeExistenceTool, "_channel_links_to_tiktok", lambda self, url, handle: True
    )
    presence = tool.check_youtube_presence(_profile("bio without youtube link"))
    assert presence.status == SocialStatus.VERIFIED
    assert presence.confidence_score == 0.90


# ---------------------------------------------------------------------------
# Seed profiles (@handles / profile URLs typed directly)
# ---------------------------------------------------------------------------


def test_parse_seed_handles():
    handles = TikTokSearchTool._parse_seed_handles(
        "@movie_explains https://www.tiktok.com/@filmbreakdown @tiktok plainword"
    )
    assert sorted(handles) == ["filmbreakdown", "movie_explains"]


def test_search_profiles_uses_seeds_without_discovery(monkeypatch):
    tool = TikTokSearchTool()

    def _fail(url):
        raise AssertionError("discovery must not run when seeds are present")

    monkeypatch.setattr(tool, "_discover_via_ytdlp", _fail)
    monkeypatch.setattr(tool, "enrich_profile", lambda p: p)
    profiles = tool.search_profiles("https://www.tiktok.com/@creator_a", max_profiles=10)
    assert [p.handle for p in profiles] == ["creator_a"]
    assert profiles[0].profile_url == "https://www.tiktok.com/@creator_a"


def test_ydl_opts_includes_cookiefile_when_set():
    tool = TikTokSearchTool(cookiefile="C:/tmp/cookies.txt")
    opts = tool._ydl_opts(flat=True)
    assert opts["cookiefile"] == "C:/tmp/cookies.txt"
    assert opts["extract_flat"] is True


def test_ydl_opts_omits_cookiefile_when_unset():
    opts = TikTokSearchTool()._ydl_opts(flat=False)
    assert "cookiefile" not in opts
    assert "extract_flat" not in opts


def test_cookiefile_property_refreshes_api_session(tmp_path):
    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "sessionid", "abc"), (".tiktok.com", "ttwid", "xyz")])
    tool = TikTokSearchTool()
    assert tool.cookie_count == 0
    tool.cookiefile = str(p)
    assert tool.cookiefile == str(p)
    assert tool.cookie_count == 2
    assert tool.api_session.cookie_count == 2
    assert tool.api_session._flat_cookies["sessionid"] == "abc"
    assert tool.api_session._flat_cookies["ttwid"] == "xyz"


def test_cookiefile_property_resets_session_when_cleared(tmp_path):
    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "sessionid", "abc")])
    tool = TikTokSearchTool(cookiefile=str(p))
    assert tool.cookie_count == 1
    tool.cookiefile = None
    assert tool.cookie_count == 0
    assert tool.api_session.cookie_count == 0


def test_orchestrator_propagates_cookiefile_to_api_session(tmp_path, monkeypatch):
    from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator

    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "sessionid", "abc")])
    orchestrator = AgentOrchestrator()
    assert orchestrator.tiktok_tool.cookie_count == 0
    monkeypatch.setattr(orchestrator.tiktok_tool, "search_profiles", lambda *a, **k: [])
    orchestrator.tiktok_tool.search_note = "note"
    orchestrator.run_tiktok_discovery("#tag", max_profiles=5, cookiefile=str(p))
    assert orchestrator.tiktok_tool.cookie_count == 1
    assert orchestrator.tiktok_tool.api_session._flat_cookies["sessionid"] == "abc"


# ---------------------------------------------------------------------------
# TikTokApiSession — cookies loader, X-Bogus signing, handle extraction
# ---------------------------------------------------------------------------


def _write_netscape_cookies(path, rows):
    lines = ["# Netscape HTTP Cookie File"]
    for domain, name, value in rows:
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t1900000000\t{name}\t{value}")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_cookie_loader_parses_netscape(tmp_path):
    from s_q_ali_media_downloader.agent.tools.tiktok_api import TikTokApiSession

    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "sessionid", "abc"), ("www.tiktok.com", "ttwid", "xyz")])
    session = TikTokApiSession(cookiefile=str(p))
    assert session.cookie_count == 2
    assert session._flat_cookies["sessionid"] == "abc"
    assert session._flat_cookies["ttwid"] == "xyz"


def test_cookie_loader_tolerates_missing_file(tmp_path):
    from s_q_ali_media_downloader.agent.tools.tiktok_api import TikTokApiSession

    session = TikTokApiSession(cookiefile=str(tmp_path / "nope.txt"))
    assert session.cookie_count == 0


def test_generate_xbogus_is_deterministic_and_shape_stable():
    from s_q_ali_media_downloader.agent.tools.tiktok_api import CUSTOM_B64_ALPHABET, generate_xbogus

    qs = "aid=1988&count=30&challengeName=ishowspeed"
    ua = "Mozilla/5.0 test"
    a = generate_xbogus(qs, ua, timestamp=1788690000)
    b = generate_xbogus(qs, ua, timestamp=1788690000)
    c = generate_xbogus(qs, ua, timestamp=1788690001)
    assert a == b
    assert a != c
    assert len(a) == 28
    assert all(ch in CUSTOM_B64_ALPHABET for ch in a)


def test_signed_url_appends_xbogus_with_ms_token(tmp_path):
    from s_q_ali_media_downloader.agent.tools.tiktok_api import TikTokApiSession

    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "msToken", "tok123"), (".tiktok.com", "ttwid", "wid1")])
    session = TikTokApiSession(cookiefile=str(p))
    params = session._sign_base_params()
    params.update({"keyword": "test", "aid": "1988"})
    url = session._signed_url("/api/search/item/full/", params)
    assert "/api/search/item/full/?" in url
    assert "msToken=tok123" in url
    assert "ttwid=wid1" in url
    assert "X-Bogus=" in url


def test_api_handles_parses_item_list(tmp_path, monkeypatch):
    from s_q_ali_media_downloader.agent.tools.tiktok_api import TikTokApiSession

    class FakeResponse:
        status_code = 200
        text = "{}"

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def __bool__(self):
            return True

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            return FakeResponse({"statusCode": 0, "itemList": [
                {"author": {"uniqueId": "creator_a"}},
                {"author": {"uniqueId": "creator_b"}},
                {"author": {}},
            ]})

    session = TikTokApiSession(cookiefile=str(tmp_path / "x.txt"))
    monkeypatch.setattr(session, "_client", lambda: FakeClient())
    handles = session._api_handles("/api/challenge/item_list/", {"challengeName": "test"})
    assert handles == ["creator_a", "creator_b"]


def test_fetch_tag_handles_cleans_and_caps(tmp_path, monkeypatch):
    from s_q_ali_media_downloader.agent.tools.tiktok_api import TikTokApiSession

    session = TikTokApiSession()
    monkeypatch.setattr(session, "_api_handles", lambda *a, **k: ["..bad", "ok_creator", "tiktok"])
    monkeypatch.setattr(session, "_html_handles", lambda *a, **k: [])
    assert session.fetch_tag_handles("test", limit=40) == ["ok_creator"]


def test_zero_results_sets_actionable_note(monkeypatch):
    tool = TikTokSearchTool()
    monkeypatch.setattr(tool.api_session, "fetch_tag_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool.api_session, "fetch_search_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool, "_discover_via_html", lambda url: [])
    monkeypatch.setattr(tool, "_discover_via_ytdlp", lambda url: [])
    monkeypatch.setattr(tool, "enrich_profile", lambda p: p)
    profiles = tool.search_profiles("#sometag", max_profiles=10)
    assert profiles == []
    assert tool.search_note is not None
    assert "@handles" in tool.search_note
    assert "0" in tool.search_note


def test_orchestrator_surfaces_note_when_zero_profiles(monkeypatch):
    from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator

    emitted = []
    orchestrator = AgentOrchestrator(progress_callback=lambda p, m: emitted.append((p, m)))
    note = "TikTok returned 0 profiles. TikTok blocks anonymous #tag listing. Tip: paste @handles."
    orchestrator.tiktok_tool.search_profiles = lambda *a, **k: []
    orchestrator.tiktok_tool.search_note = note
    result = orchestrator.run_tiktok_discovery("not a tag", max_profiles=5)
    assert result.profiles == []
    assert emitted[-1] == (100, note)


def test_note_when_no_cookiefile_provided():
    tool = TikTokSearchTool()
    note = tool._build_no_results_note(tags=["sometag"], had_keywords=False)
    assert "No cookies.txt was provided" in note
    assert "@handles" in note


def test_note_when_cookiefile_failed_to_load(tmp_path):
    tool = TikTokSearchTool(cookiefile=str(tmp_path / "missing.txt"))
    assert tool.cookie_count == 0
    assert tool.cookiefile is not None
    note = tool._build_no_results_note(tags=[], had_keywords=True)
    assert "failed to load" in note
    assert "No cookies.txt was provided" not in note


def test_note_when_cookiefile_loaded_but_blocked(tmp_path):
    p = tmp_path / "cookies.txt"
    _write_netscape_cookies(p, [(".tiktok.com", "sessionid", "abc")])
    tool = TikTokSearchTool(cookiefile=str(p))
    assert tool.cookie_count == 1
    note = tool._build_no_results_note(tags=["tech"], had_keywords=False)
    assert "1 cookies" in note
    assert "listing stayed blocked" in note
