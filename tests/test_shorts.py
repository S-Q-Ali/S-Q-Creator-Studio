"""Tests for the cut points and the clip maths."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from s_q_ali_media_downloader.core import ffmpeg_process, shorts

# What ffmpeg's silencedetect prints on stderr.
SILENCE_OUTPUT = """
[silencedetect @ 000001f2] silence_start: 8.5
[silencedetect @ 000001f2] silence_end: 9.75 | silence_duration: 1.25
[silencedetect @ 000001f2] silence_start: 30
[silencedetect @ 000001f2] silence_end: 30.2 | silence_duration: 0.2
"""

# What ffmpeg's metadata filter prints for the scene score.
SCENE_OUTPUT = """
frame:0    pts:0       pts_time:0
lavfi.scene_score=0.000000
frame:12   pts:1536    pts_time:32
lavfi.scene_score=0.512000
frame:30   pts:3840    pts_time:80
lavfi.scene_score=0.301000
"""


def _fake_runner(text: str):
    """A runner that hands back canned ffmpeg output and keeps the command."""

    calls = []

    def runner(command):
        calls.append(command)
        return text

    runner.calls = calls
    return runner


def test_the_pause_parser_finds_the_middle_of_each_pause():
    assert shorts.parse_silences(SILENCE_OUTPUT) == [9.125]


def test_a_gap_between_words_is_not_a_pause():
    """A silence of 0.2 s is a gap between two words, not a pause to cut at."""
    assert shorts.parse_silences(SILENCE_OUTPUT) == [9.125]


def test_the_scene_parser_takes_the_changes_above_the_threshold():
    assert shorts.parse_scene_changes(SCENE_OUTPUT) == [32.0]


def test_a_pause_in_the_speech_is_preferred_over_a_scene_change():
    plan = shorts.plan_cuts(180, target=60, silences=[62.0], scenes=[58.0])

    assert plan.segments[0].end == 62.0


def test_the_cut_point_lands_within_fifteen_seconds_of_the_target():
    plan = shorts.plan_cuts(180, target=60, silences=[70.0])

    assert plan.segments[0].end == 70.0


def test_a_pause_further_than_fifteen_seconds_is_not_used():
    plan = shorts.plan_cuts(180, target=60, silences=[76.0])

    assert plan.segments[0].end == 60.0


def test_a_video_with_no_pauses_or_scenes_falls_back_to_even_segments():
    plan = shorts.plan_cuts(180, target=60)

    assert [(s.start, s.end) for s in plan.segments] == [
        (0.0, 60.0),
        (60.0, 120.0),
        (120.0, 180.0),
    ]


def test_the_auto_mode_cuts_on_the_scene_changes():
    plan = shorts.plan_cuts(120, scenes=[20.0, 45.0])

    assert [(s.start, s.end) for s in plan.segments] == [
        (0.0, 20.0),
        (20.0, 45.0),
        (45.0, 120.0),
    ]


def test_the_auto_mode_leaves_a_video_without_scene_changes_alone():
    plan = shorts.plan_cuts(120, scenes=[])

    assert plan.segments == []


def test_the_n_clips_mode_divides_the_duration_by_the_clip_count():
    plan = shorts.plan_cuts(1980, clips=6)

    assert plan.clips == 6
    assert plan.clip_duration == 330
    assert len(plan.segments) == 6


def test_the_n_clips_mode_moves_each_boundary_to_the_nearest_pause():
    plan = shorts.plan_cuts(1980, clips=6, silences=[325.0])

    assert plan.segments[0].end == 325.0
    assert plan.clips == 6


def test_the_report_says_the_duration_it_will_use():
    plan = shorts.plan_cuts(1980, clips=6)

    assert "6 clips" in plan.note
    assert "5 min 30 s" in plan.note


def test_the_report_says_when_the_duration_is_over_the_shorts_limit():
    plan = shorts.plan_cuts(1980, clips=6)

    assert "3-minute limit" in plan.note
    assert "11 clips would fit" in plan.note


def test_the_report_stays_quiet_when_the_clips_fit():
    plan = shorts.plan_cuts(600, clips=6)

    assert "limit" not in plan.note


def test_a_video_shorter_than_one_target_is_not_split():
    plan = shorts.plan_cuts(45, target=60)

    assert plan.segments == []


def test_a_two_second_tail_merges_into_the_clip_before_it():
    plan = shorts.plan_cuts(122, target=60)

    assert [(s.start, s.end) for s in plan.segments] == [(0.0, 60.0), (60.0, 122.0)]


def test_a_tail_worth_its_own_clip_is_still_kept():
    plan = shorts.plan_cuts(150, target=60)

    assert [s.end for s in plan.segments] == [60.0, 120.0, 150.0]


def test_the_segments_cover_the_whole_video_without_a_gap():
    pauses = [325.0, 660.0, 990.0, 1320.0, 1650.0]
    plan = shorts.plan_cuts(1980, clips=6, silences=pauses)

    assert plan.segments[0].start == 0.0
    assert plan.segments[-1].end == 1980
    for earlier, later in zip(plan.segments, plan.segments[1:]):
        assert earlier.end == later.start
    assert sum(segment.duration for segment in plan.segments) == 1980


def test_the_detection_runs_ffmpeg_and_reads_the_pauses():
    runner = _fake_runner(SILENCE_OUTPUT)

    assert shorts.detect_silences("movie.mp4", runner=runner) == [9.125]
    assert "silencedetect" in " ".join(runner.calls[0])


def test_the_scene_detection_runs_ffmpeg_and_reads_the_changes():
    runner = _fake_runner(SCENE_OUTPUT)

    assert shorts.detect_scene_changes("movie.mp4", runner=runner) == [32.0]
    assert "scene" in " ".join(runner.calls[0])


def test_a_failing_ffmpeg_leaves_no_cut_points():
    def runner(command):
        return ""

    assert shorts.detect_silences("movie.mp4", runner=runner) == []
    assert shorts.detect_scene_changes("movie.mp4", runner=runner) == []


def test_the_shorts_recommendation_rounds_up():
    plan = shorts.plan_cuts(2000, clips=6)

    assert "12 clips would fit" in plan.note
    assert shorts.clips_that_fit(2000) == 12


@pytest.mark.parametrize("duration, count, pauses", [
    (60, 6, [15.0]),
    (12, 6, [3.0, 6.0, 9.0]),
    (100, 7, []),
])
def test_n_clips_preserves_the_requested_count(duration, count, pauses):
    plan = shorts.plan_cuts(duration, clips=count, silences=pauses)

    assert len(plan.segments) == plan.clips == count
    assert all(segment.duration > 0 for segment in plan.segments)
    assert sum(segment.duration for segment in plan.segments) == pytest.approx(duration)


def test_scene_cuts_are_ordered_unique_and_inside_the_video():
    plan = shorts.plan_cuts(120, scenes=[130, 140, 30, 10, 30, 0, -1, float("nan")])

    assert [(s.start, s.end) for s in plan.segments] == [(0.0, 30), (30, 120)]


def test_auto_leaves_a_video_shorter_than_one_clip_alone():
    plan = shorts.plan_cuts(12, scenes=[2, 4, 11])

    assert plan.segments == []
    assert "not split" in plan.note.lower()


def test_auto_never_plans_a_clip_shorter_than_the_floor():
    scenes = [float(step) for step in range(3, 300, 3)]

    plan = shorts.plan_cuts(300, scenes=scenes)

    assert all(segment.duration >= shorts.MIN_CLIP for segment in plan.segments)
    assert plan.segments[0].start == 0.0
    assert plan.segments[-1].end == 300


def test_auto_never_plans_a_clip_longer_than_the_shorts_limit():
    plan = shorts.plan_cuts(1000, scenes=[200.0])

    assert all(segment.duration <= shorts.SHORTS_LIMIT for segment in plan.segments)
    assert plan.segments[0].start == 0.0
    assert plan.segments[-1].end == 1000


def test_a_scene_cannot_move_a_target_cut_past_the_video_end():
    plan = shorts.plan_cuts(122, target=60, scenes=[125, 130])

    assert [s.end for s in plan.segments] == [60.0, 122.0]


def test_the_report_warns_if_a_pause_makes_one_clip_exceed_the_limit():
    plan = shorts.plan_cuts(360, clips=2, silences=[195])

    assert "3-minute limit" in plan.note
    assert "2 min 45 s" in plan.note and "3 min 15 s" in plan.note
    assert "average" in plan.note


def test_one_requested_clip_does_not_copy_the_original():
    plan = shorts.plan_cuts(120, clips=1)

    assert plan.segments == []
    assert "not split" in plan.note.lower()


@pytest.mark.parametrize("options", [
    {"target": 0}, {"target": float("nan")}, {"target": float("inf")},
    {"clips": 0}, {"clips": 2.5}, {"clips": True}, {"target": 30, "clips": 4},
])
def test_invalid_split_options_are_rejected(options):
    with pytest.raises(ValueError):
        shorts.plan_cuts(120, **options)


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -10])
def test_invalid_media_duration_is_rejected(duration):
    with pytest.raises(ValueError):
        shorts.plan_cuts(duration, clips=6)


def test_missing_ffmpeg_returns_no_detections(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("missing binary")

    monkeypatch.setattr(ffmpeg_process.subprocess, "run", missing)
    assert shorts.detect_silences("movie.mp4") == []
    assert shorts.detect_scene_changes("movie.mp4") == []


def test_failed_ffmpeg_does_not_use_partial_detections(monkeypatch):
    monkeypatch.setattr(ffmpeg_process.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a, 1, "", SILENCE_OUTPUT))
    assert shorts.detect_silences("movie.mp4") == []


@pytest.mark.parametrize("options", [{"target": -60}, {"clips": -6}])
def test_negative_options_cannot_enter_the_cut_loop(options):
    with pytest.raises(ValueError):
        shorts.plan_cuts(120, **options)


@pytest.fixture(scope="module")
def ffmpeg_media(tmp_path_factory):
    from s_q_ali_media_downloader.engine import find_ffmpeg

    directory = find_ffmpeg()
    assert directory, "Real media tests require ffmpeg and ffprobe."
    binary = Path(directory) / "ffmpeg"
    probe = Path(directory) / "ffprobe"
    folder = tmp_path_factory.mktemp("shorts-media")
    source = folder / "two minute source.mp4"
    subprocess.run([
        str(binary), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-f", "lavfi", "-i", "color=black:s=160x90:r=10:d=40",
        "-f", "lavfi", "-i", "color=white:s=160x90:r=10:d=40",
        "-f", "lavfi", "-i", "color=black:s=160x90:r=10:d=40",
        "-f", "lavfi", "-i",
        ("sine=frequency=440:sample_rate=48000:duration=120,"
         "volume=0:enable='between(t,38,42)+between(t,78,82)'"),
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-preset", "ultrafast",
        "-g", "100", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], capture_output=True, check=True, timeout=60)
    return str(binary), str(probe), source


@pytest.mark.live
def test_real_ffmpeg_finds_pauses_and_scene_changes(ffmpeg_media):
    binary, _, source = ffmpeg_media
    silences = shorts.detect_silences(str(source), ffmpeg=binary)
    scenes = shorts.detect_scene_changes(str(source), ffmpeg=binary)

    assert silences == pytest.approx([40, 80], abs=0.05)
    assert scenes == pytest.approx([40, 80], abs=0.1)
    plan = shorts.plan_cuts(120, clips=3, silences=silences, scenes=scenes)
    assert [s.end for s in plan.segments] == pytest.approx([40, 80, 120], abs=0.05)


def _render_clip(command):
    Path(command[-1]).write_bytes(b"rendered clip")
    return 0


def test_split_writes_numbered_clips_and_preserves_the_original(tmp_path):
    source = tmp_path / "my movie.mkv"
    source.write_bytes(b"original")
    plan = shorts.plan_cuts(122, target=60)

    result = shorts.split_video(str(source), plan, runner=_render_clip)

    assert [Path(p).name for p in result.outputs] == [
        "my movie_short01.mp4", "my movie_short02.mp4",
    ]
    assert all(Path(p).read_bytes() == b"rendered clip" for p in result.outputs)
    assert source.read_bytes() == b"original"
    assert "2 shorts saved" in result.note


def test_split_command_reencodes_video_but_copies_all_audio():
    segment = shorts.Segment(0, 40.3, 80.7)
    command = shorts.build_split_command("ffmpeg", "in.mp4", "out.mp4", segment)

    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-c:a") + 1] == "copy"
    assert "0:a?" in command
    assert float(command[command.index("-ss") + 1]) == pytest.approx(40.3)
    assert float(command[command.index("-t") + 1]) == pytest.approx(40.4)
    assert "-n" in command and "-y" not in command


def test_no_split_plan_does_not_run_ffmpeg(tmp_path):
    source = tmp_path / "short.mp4"
    source.write_bytes(b"original")
    result = shorts.split_video(str(source), shorts.plan_cuts(45, target=60),
                                runner=lambda cmd: pytest.fail("unexpected render"))

    assert result.outputs == []
    assert list(tmp_path.iterdir()) == [source]


def test_existing_clip_aborts_before_writing_any_files(tmp_path):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"original")
    existing = tmp_path / "movie_short02.mp4"
    existing.write_bytes(b"user file")

    result = shorts.split_video(str(source), shorts.plan_cuts(120, target=60),
                                runner=lambda cmd: pytest.fail("unexpected render"))

    assert result.outputs == []
    assert existing.read_bytes() == b"user file"
    assert "already exists" in result.note
    assert not (tmp_path / "movie_short01.mp4").exists()


@pytest.mark.parametrize("failure", ["exit", "missing", "empty", "launch"])
def test_failed_split_never_publishes_a_partial_clip(tmp_path, failure):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"original")

    def fail(command):
        if failure == "launch":
            raise FileNotFoundError("missing binary")
        if failure != "missing":
            Path(command[-1]).write_bytes(b"" if failure == "empty" else b"partial")
        return 1 if failure == "exit" else 0

    result = shorts.split_video(str(source), shorts.plan_cuts(120, target=60), runner=fail)

    assert result.outputs == []
    assert "could not" in result.note.lower()
    assert source.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [source]


def test_failed_second_clip_keeps_the_completed_first_clip(tmp_path):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"original")

    def render(command):
        if (tmp_path / "movie_short01.mp4").exists():
            Path(command[-1]).write_bytes(b"partial")
            return 1
        return _render_clip(command)

    result = shorts.split_video(str(source), shorts.plan_cuts(120, target=60), runner=render)

    assert [Path(p).name for p in result.outputs] == ["movie_short01.mp4"]
    assert "could not" in result.note.lower()
    assert not (tmp_path / "movie_short02.mp4").exists()


def test_file_created_during_render_is_not_overwritten(tmp_path):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"original")
    collision = tmp_path / "movie_short01.mp4"

    def render(command):
        collision.write_bytes(b"another writer")
        return _render_clip(command)

    result = shorts.split_video(str(source), shorts.plan_cuts(120, target=60), runner=render)

    assert result.outputs == []
    assert collision.read_bytes() == b"another writer"


def test_failed_output_copy_removes_only_its_own_partial_file(tmp_path, monkeypatch):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"original")

    def fail_copy(src, dst, *args, **kwargs):
        dst.write(b"partial copy")
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copyfileobj", fail_copy)
    result = shorts.split_video(str(source), shorts.plan_cuts(120, target=60),
                                runner=_render_clip)

    assert result.outputs == []
    assert list(tmp_path.iterdir()) == [source]


def _probe_media(probe, path):
    result = subprocess.run([
        probe, "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def _audio_packet_hashes(probe, path):
    result = subprocess.run([
        probe, "-v", "error", "-select_streams", "a:0", "-show_packets",
        "-show_data_hash", "sha256", "-show_entries", "packet=pts_time,data_hash",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=True, timeout=60)
    return [p["data_hash"] for p in json.loads(result.stdout)["packets"]
            if float(p["pts_time"]) >= 0]


@pytest.mark.live
@pytest.mark.parametrize("cuts", [[40.3, 80.7], [40.35, 80.75], [40.000005, 80.000005]])
def test_real_split_preserves_video_frames_and_audio_at_non_keyframe_cuts(
    ffmpeg_media, tmp_path, cuts,
):
    binary, probe, fixture = ffmpeg_media
    source = tmp_path / "movie with spaces.mp4"
    shutil.copyfile(fixture, source)
    original_bytes = source.read_bytes()
    plan = shorts.plan_cuts(120, clips=3, silences=cuts)

    result = shorts.split_video(str(source), plan, ffmpeg=binary)

    assert len(result.outputs) == 3, result.note
    frame_count = 0
    for path, segment in zip(result.outputs, plan.segments):
        media = _probe_media(probe, path)
        video = next(s for s in media["streams"] if s["codec_type"] == "video")
        audio = next(s for s in media["streams"] if s["codec_type"] == "audio")
        assert video["codec_name"] == "h264"
        assert (video["width"], video["height"]) == (160, 90)
        assert audio["codec_name"] == "aac"
        assert float(video["duration"]) == pytest.approx(segment.duration, abs=0.100001)
        assert float(audio["duration"]) == pytest.approx(segment.duration, abs=0.05)
        assert float(audio.get("start_time", 0)) == pytest.approx(0, abs=0.05)
        frame_count += int(video["nb_read_frames"])
    assert frame_count == 1200
    copied_packets = [packet for path in result.outputs for packet in _audio_packet_hashes(probe, path)]
    assert copied_packets == _audio_packet_hashes(probe, source)
    assert source.read_bytes() == original_bytes


@pytest.mark.live
def test_real_split_also_handles_a_video_without_audio(ffmpeg_media, tmp_path):
    binary, probe, fixture = ffmpeg_media
    source = tmp_path / "silent.mp4"
    subprocess.run([binary, "-v", "error", "-nostdin", "-n", "-i", str(fixture),
                    "-t", "8", "-map", "0:v:0", "-c:v", "copy", str(source)],
                   capture_output=True, check=True, timeout=60)
    result = shorts.split_video(str(source), shorts.plan_cuts(8, clips=2), ffmpeg=binary)

    assert len(result.outputs) == 2, result.note
    for path in result.outputs:
        assert [s["codec_type"] for s in _probe_media(probe, path)["streams"]] == ["video"]
