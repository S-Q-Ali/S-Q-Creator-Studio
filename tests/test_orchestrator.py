"""Tests for AgentOrchestrator control flow (no network: search stubbed)."""

from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator


def test_run_discovery_no_channels_returns_empty(monkeypatch):
    captured = []

    def fake_search_channels(*args, **kwargs):
        return []

    orchestrator = AgentOrchestrator(progress_callback=lambda p, m: captured.append((p, m)))
    monkeypatch.setattr(orchestrator.search_tool, "search_channels", fake_search_channels)

    result = orchestrator.run_discovery("nothing interesting", max_channels=10)

    assert result.total_searched == 0
    assert result.channels_matching_filter == 0
    assert result.channels == []
    assert result.query == "nothing interesting"
    assert captured[0][1].startswith("Initializing Agent")
    assert captured[-1][0] == 100


def test_progress_callback_errors_are_swallowed():
    def bad_callback(percent, message):
        raise RuntimeError("ui gone")

    orchestrator = AgentOrchestrator(progress_callback=bad_callback)
    # _emit must never bubble the callback's failure into the pipeline
    orchestrator._emit(10, "started")
    orchestrator._emit(10, "started")
    assert True


def test_every_youtube_step_is_written_to_the_activity_log(monkeypatch):
    lines = []
    orchestrator = AgentOrchestrator(log_callback=lines.append)
    monkeypatch.setattr(
        orchestrator.search_tool, "search_channels", lambda **kwargs: []
    )

    orchestrator.run_discovery("nobody", max_channels=10)

    text = "\n".join(lines)
    assert "YouTube discovery" in text
    assert "yt-dlp" in text
    assert "Found 0 candidate channels" in text
    assert "0 channels found" in text


def test_every_tiktok_step_is_written_to_the_activity_log(monkeypatch):
    lines = []
    orchestrator = AgentOrchestrator(log_callback=lines.append)
    monkeypatch.setattr(
        orchestrator.tiktok_tool, "search_profiles", lambda *a, **k: []
    )

    orchestrator.run_tiktok_discovery("cats")

    text = "\n".join(lines)
    assert "TikTok discovery" in text
    assert "TikTok search" in text
    assert "Found 0 TikTok profiles" in text


def test_a_log_callback_error_does_not_stop_the_pipeline(monkeypatch):
    def bad_log(message):
        raise RuntimeError("log widget gone")

    orchestrator = AgentOrchestrator(log_callback=bad_log)
    monkeypatch.setattr(
        orchestrator.search_tool, "search_channels", lambda **kwargs: []
    )

    result = orchestrator.run_discovery("x")

    assert result.total_searched == 0


def test_run_discovery_without_callback(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import AgentSearchResult as Result

    class FakeSearch:
        def search_channels(self, **kwargs):
            return []

    orchestrator = AgentOrchestrator()
    monkeypatch.setattr(orchestrator.search_tool, "search_channels", FakeSearch().search_channels)
    result = orchestrator.run_discovery("x")
    assert isinstance(result, Result)
    assert result.total_searched == 0