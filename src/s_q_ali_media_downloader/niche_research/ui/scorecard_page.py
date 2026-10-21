"""Scorecard page — paste a video/channel URL and get a vidIQ-style SEO score.

Ported from the companion research web tool's ScorecardLookup.tsx (Video/Channel tabs, stats strip,
recent uploads, SEO panel with per-check pass/fail circles).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce
from s_q_ali_media_downloader.niche_research.research import scorecard_engine as se
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.export_button import ExportButton
from s_q_ali_media_downloader.niche_research.ui.theme import research_style

logger = logging.getLogger(__name__)


class ScorecardWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        mode: str,
        url: str,
        *,
        focus_keyword: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.url = url
        self.focus_keyword = focus_keyword

    def run(self) -> None:
        try:
            if self.mode == "video":
                self.done.emit(
                    se.lookup_video(self.url, focus_keyword=self.focus_keyword)
                )
            else:
                self.done.emit(
                    se.lookup_channel(self.url, focus_keyword=self.focus_keyword)
                )
        except Exception as exc:
            logger.warning("Scorecard lookup failed", exc_info=True)
            self.failed.emit(str(exc))


class ScorecardPage(QWidget):
    analyze_requested = Signal(str)
    queue_urls_requested = Signal(list)
    open_browser_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self.setStyleSheet(research_style())

        self._worker: ScorecardWorker | None = None
        self._mode = "video"
        self._build()

    # ------------------------------------------------------------------ #
    # UI build
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title = QLabel("Scorecard")
        self._title.setObjectName("headerTitle")
        self._subtitle = QLabel("vidIQ-style: 50% on-page SEO, 50% audience performance")
        self._subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        # Mode + URL form
        form = QHBoxLayout()
        form.setSpacing(8)
        mode_frame = QFrame()
        mode_frame.setObjectName("card")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(4, 4, 4, 4)
        mode_layout.setSpacing(0)
        self._video_btn = QPushButton("Video")
        self._video_btn.setObjectName("modeToggle")
        self._video_btn.setProperty("active", True)
        self._channel_btn = QPushButton("Channel")
        self._channel_btn.setObjectName("modeToggle")
        self._video_btn.clicked.connect(lambda: self._set_mode("video"))
        self._channel_btn.clicked.connect(lambda: self._set_mode("channel"))
        mode_layout.addWidget(self._video_btn)
        mode_layout.addWidget(self._channel_btn)
        form.addWidget(mode_frame)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("Paste a YouTube video URL…")
        self._url_edit.returnPressed.connect(self._run_lookup)
        form.addWidget(self._url_edit, 1)
        self._score_btn = QPushButton("Score")
        self._score_btn.clicked.connect(self._run_lookup)
        form.addWidget(self._score_btn)
        self._export_btn = ExportButton("scorecard", "SEO Scorecard")
        self._export_btn.exported.connect(
            lambda path: self._status.setText(f"Exported to {path}")
        )
        self._export_btn.failed.connect(
            lambda message: self._status.setText(message)
        )
        form.addWidget(self._export_btn)
        root.addLayout(form)

        # Focus keyword — enables the keyword-placement checks (title,
        # description, tags). Without it those four checks cannot run.
        kw_row = QHBoxLayout()
        kw_row.setSpacing(8)
        kw_label = QLabel("Focus keyword")
        kw_label.setObjectName("statKey")
        self._keyword_edit = QLineEdit()
        self._keyword_edit.setPlaceholderText(
            "Optional — checks keyword placement in title, description and tags"
        )
        self._keyword_edit.returnPressed.connect(self._run_lookup)
        kw_row.addWidget(kw_label)
        kw_row.addWidget(self._keyword_edit, 1)
        root.addLayout(kw_row)

        # Status bar
        status = QFrame()
        status.setObjectName("statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        self._status = QLabel("Paste a video or channel URL to score it.")
        self._status.setObjectName("statusText")
        status_layout.addWidget(self._status, 1)
        root.addWidget(status)

        # Content scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 1)

        self._empty = self._build_empty_state()
        self._content_layout.addWidget(self._empty)

    def _build_empty_state(self) -> QFrame:
        """A fresh empty-state frame.

        The frame is rebuilt on every placeholder render: a shared instance
        would be deleted by `_clear_content` and then re-added, which raises
        "Internal C++ object already deleted" on the second failure.
        """
        empty = QFrame()
        empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(40, 40, 40, 40)
        icon = QLabel("📊")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon)
        hint = QLabel("No score yet — paste a URL to start.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setObjectName("sectionLabel")
        empty_layout.addWidget(hint)
        return empty

    def _set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._video_btn.setProperty("active", mode == "video")
        self._channel_btn.setProperty("active", mode == "channel")
        for btn in (self._video_btn, self._channel_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._url_edit.setPlaceholderText(
            "Paste a YouTube channel / @handle URL…"
            if mode == "channel"
            else "Paste a YouTube video URL…"
        )
        self._render_placeholder()

    def set_mode(self, mode: str) -> None:
        """Public mode switch (used by the discovery -> scorecard handoff)."""
        self._set_mode(mode)

    def prefill(self, url: str, focus_keyword: str = "") -> None:
        """Put a URL (and optionally a focus keyword) in the inputs."""
        self._url_edit.setText(url or "")
        if focus_keyword:
            self._keyword_edit.setText(focus_keyword)

    # ------------------------------------------------------------------ #
    # Lookup
    # ------------------------------------------------------------------ #
    def _run_lookup(self) -> None:
        url = self._url_edit.text().strip()
        if not url or (self._worker is not None and self._worker.isRunning()):
            return
        self._status.setText("Fetching metadata via yt-dlp…")
        self._score_btn.setEnabled(False)
        self._score_btn.setText("Fetching...")
        self._worker = ScorecardWorker(
            self._mode,
            url,
            focus_keyword=self._keyword_edit.text().strip(),
            parent=self,
        )
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_done(self, result) -> None:
        self._score_btn.setEnabled(True)
        self._score_btn.setText("Score")
        self._status.setText("Done.")
        self._render_result(result)

    def _on_failed(self, error: str) -> None:
        self._score_btn.setEnabled(True)
        self._score_btn.setText("Score")
        self._status.setText(f"Lookup failed: {error}")
        self._render_placeholder()

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_placeholder(self) -> None:
        self._clear_content()
        self._empty = self._build_empty_state()
        self._content_layout.addWidget(self._empty)

    def _render_result(self, result) -> None:
        self._clear_content()
        if result.kind == "video":
            self._render_video(result)
        else:
            self._render_channel(result)
        self._export_btn.set_payload(self._export_rows(result))

    def _export_rows(self, result) -> list[dict]:
        """The rows this page shows, flattened for the export."""
        if result.kind == "video":
            video = dict(result.video)
            video["views"] = video.get("view_count")
            video["likes"] = video.get("like_count")
            video["comments"] = video.get("comment_count")
            video["tags"] = video.get("tags") or []
            rows = [video]
        else:
            rows = [dict(result.channel or {})]
        seo = result.seo
        if seo is not None:
            rows[0]["seo_total"] = seo.total
            rows[0]["seo_actionable_pct"] = seo.actionable_pct
            rows[0]["seo_performance_pct"] = seo.performance_pct
            rows[0]["seo_checks"] = [
                f"{c.id}={c.score} ({c.detail})" for c in seo.checks
            ]
        if getattr(result, "vph", None) is not None:
            rows[0]["vph"] = result.vph.vph
        for video_row in getattr(result, "recent_videos", []) or []:
            rows.append(dict(video_row))
        return rows

    def stop_workers(self) -> None:
        """Stop and join the lookup worker (called when the app closes)."""
        w.stop_worker(self._worker)
        self._worker = None

    def _render_video(self, result) -> None:
        row = QHBoxLayout()
        thumb = w.AvatarThumbnail(
            result.video.get("thumbnail_url", ""), result.video.get("title", ""), size=96
        )
        row.addWidget(thumb)
        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(result.video.get("title", ""))
        title.setObjectName("urlTitle")
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.addWidget(title)
        meta = QLabel(
            f"{result.channel['title'] if result.channel else 'Unknown channel'} · "
            f"{result.video.get('published_at', '')[:10]} · "
            f"{_fmt_duration(result.video.get('duration_seconds', 0))}"
        )
        meta.setObjectName("urlMeta")
        info.addWidget(meta)

        video_id = result.video.get("video_id") or ""
        track = QPushButton()
        track.setProperty("variant", "outline")
        if result.tracked:
            track.setText("Tracking")
            track.setEnabled(False)
        elif not video_id:
            track.setText("Track video")
            track.setEnabled(False)
            track.setToolTip("No video id available — this video cannot be tracked")
        else:
            track.setText("Track video")
            track.clicked.connect(
                lambda: _mark_tracked(
                    "video", video_id, result.video.get("title", ""), track
                )
            )
        info.addWidget(track)

        # Action row: the scored video must be usable without leaving the
        # page — queue it for download or open it on YouTube.
        actions = QHBoxLayout()
        actions.setSpacing(6)
        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        queue = QPushButton("Queue")
        queue.setProperty("variant", "outline")
        queue.setEnabled(bool(video_url))
        queue.setToolTip(
            "Add this video to the download queue"
            if video_url
            else "No video id available — this video cannot be queued"
        )
        queue.clicked.connect(lambda _=False: self.queue_urls_requested.emit([video_url]))
        actions.addWidget(queue)
        open_btn = QPushButton("Open on YouTube")
        open_btn.setProperty("variant", "outline")
        open_btn.setEnabled(bool(video_url))
        open_btn.setToolTip(
            "Open this video on YouTube in your browser"
            if video_url
            else "No video id available — this video cannot be opened"
        )
        open_btn.clicked.connect(lambda _=False: self.open_browser_requested.emit(video_url))
        actions.addWidget(open_btn)
        actions.addStretch(1)
        info.addLayout(actions)
        info.addStretch(1)
        row.addLayout(info, 1)
        row.addStretch(0)

        row_wrap = QWidget()
        row_wrap.setLayout(row)
        self._content_layout.addWidget(row_wrap)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        for label, value in (
            ("Views", w.format_number(result.video.get("view_count", 0))),
            ("Likes", w.format_number(result.video.get("like_count") or 0)),
            ("Comments", w.format_number(result.video.get("comment_count") or 0)),
            ("VPH (24h)", f"{result.vph.vph}/hr" if result.vph and result.vph.vph else "—"),
        ):
            stats.addWidget(self._stat_chip(label, value))
        stats_wrap = QWidget()
        stats_wrap.setLayout(stats)
        self._content_layout.addWidget(stats_wrap)

        if result.vph and result.vph.error and not result.vph.vph:
            note = QLabel(result.vph.error)
            note.setObjectName("smallLabel")
            self._content_layout.addWidget(note)

        tags = result.video.get("tags") or []
        if tags:
            cap = QLabel(f"Tags ({len(tags)})")
            cap.setObjectName("sectionLabel")
            self._content_layout.addWidget(cap)
            chips = QHBoxLayout()
            chips.setSpacing(6)
            for tag in tags[:24]:
                chip = QLabel(tag)
                chip.setObjectName("chip")
                chips.addWidget(chip)
            chips.addStretch(1)
            chip_wrap = QWidget()
            chip_wrap.setLayout(chips)
            self._content_layout.addWidget(chip_wrap)

        self._content_layout.addWidget(_SeoPanel(result.seo))

    def _render_channel(self, result) -> None:
        row = QHBoxLayout()
        avatar = w.AvatarThumbnail(
            result.channel.get("thumbnail_url", ""), result.channel.get("title", ""), size=72
        )
        row.addWidget(avatar)
        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(result.channel.get("title", ""))
        title.setObjectName("urlTitle")
        info.addWidget(title)
        cid = QLabel(result.channel.get("channel_id", ""))
        cid.setObjectName("urlMeta")
        info.addWidget(cid)

        channel_id = result.channel.get("channel_id") or ""
        track = QPushButton()
        track.setProperty("variant", "outline")
        if result.tracked:
            track.setText("Tracking")
            track.setEnabled(False)
        elif not channel_id:
            track.setText("Track channel")
            track.setEnabled(False)
            track.setToolTip("No channel id available — this channel cannot be tracked")
        else:
            track.setText("Track channel")
            track.clicked.connect(
                lambda: _mark_tracked(
                    "channel", channel_id, result.channel.get("title", ""), track
                )
            )
        info.addWidget(track)

        analyze = QPushButton("Analyze channel")
        analyze.setProperty("variant", "outline")
        analyze.setToolTip(
            "Run the AI channel analysis for this channel"
            if channel_id
            else "No channel id available — this channel cannot be analysed"
        )
        analyze.setEnabled(bool(channel_id))
        analyze.clicked.connect(lambda: self.analyze_requested.emit(channel_id))
        info.addWidget(analyze)
        info.addStretch(1)
        row.addLayout(info, 1)
        row_wrap = QWidget()
        row_wrap.setLayout(row)
        self._content_layout.addWidget(row_wrap)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        for label, value in (
            ("Subscribers", w.format_number(result.channel.get("subscriber_count", 0))),
            ("Videos", w.format_number(result.channel.get("video_count", 0))),
            ("Views", w.format_number(result.channel.get("view_count", 0))),
        ):
            stats.addWidget(self._stat_chip(label, value))
        stats_wrap = QWidget()
        stats_wrap.setLayout(stats)
        self._content_layout.addWidget(stats_wrap)

        recent = QLabel("Recent uploads")
        recent.setObjectName("sectionLabel")
        self._content_layout.addWidget(recent)
        uploads = result.recent_videos or []
        if not uploads:
            none = QLabel("No uploads fetched.")
            none.setObjectName("smallLabel")
            self._content_layout.addWidget(none)
        for v in uploads[:10]:
            frame = QFrame()
            frame.setObjectName("panel")
            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(12, 8, 12, 8)
            vtitle = QLabel(v.get("title", ""))
            vtitle.setObjectName("checkName")
            vtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            frame_layout.addWidget(vtitle, 1)
            vmeta = QLabel(
                f"{v.get('published_at', '')[:10]} · {w.format_number(v.get('view_count', 0))}"
            )
            vmeta.setObjectName("checkMeta")
            frame_layout.addWidget(vmeta)
            self._content_layout.addWidget(frame)

        self._content_layout.addWidget(_SeoPanel(result.seo))

    def _stat_chip(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        cap = QLabel(label)
        cap.setObjectName("statKey")
        layout.addWidget(cap)
        val = QLabel(value)
        val.setObjectName("kwMetricValue")
        layout.addWidget(val)
        return frame


# --------------------------------------------------------------------------- #
# Seo panel
# --------------------------------------------------------------------------- #
class _SeoPanel(QFrame):
    def __init__(self, seo: se.SeoResult, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(12)
        badge = w.ScoreBadge(seo.total, size="lg")
        head.addWidget(badge)
        meta = QVBoxLayout()
        meta.setSpacing(2)

        row1 = QHBoxLayout()
        row1.addWidget(self._pair("Actionable", seo.actionable_pct))
        row1.addStretch(1)
        row1.addWidget(self._pair("Performance", seo.performance_pct))
        meta.addLayout(row1)
        expl = QLabel("vidIQ-style: 50% on-page SEO, 50% audience performance")
        expl.setObjectName("smallLabel")
        meta.addWidget(expl)
        head.addLayout(meta, 1)
        layout.addLayout(head)

        for check in seo.checks:
            row = QHBoxLayout()
            circle = QLabel("✓" if check.passed else "✕")
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if check.passed:
                circle.setObjectName("seoCheckPass")
            elif check.score > 0:
                circle.setObjectName("seoCheckPart")
            else:
                circle.setObjectName("seoCheckFail")
            row.addWidget(circle)

            name = QLabel(check.label)
            name.setObjectName("checkName" if check.passed else "checkMeta")
            row.addWidget(name, 1)
            detail = QLabel(f"{check.score}/100 · {check.detail}")
            detail.setObjectName("checkMeta")
            row.addWidget(detail)
            layout.addLayout(row)

    def _pair(self, label: str, value: int) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        cap = QLabel(label)
        cap.setObjectName("statKey")
        box.addWidget(cap)
        val = QLabel(f"{value}%")
        val.setObjectName("urlTitle")
        box.addWidget(val)
        return widget


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _fmt_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _mark_tracked(kind: str, ref_id: str, label: str, button: QPushButton) -> None:
    """Track an item (the engine owns the tracked-items table)."""
    ce.track_item(kind, ref_id, label)
    button.setText("Tracking")
    button.setEnabled(False)
