"""Keyword Research page — autocomplete expansion + scored results table + detail.

Ported from Niche-Scope's KeywordResearch.tsx (table with ScoreBadge /
CompetitionBadge) plus the keyword detail view (Sparkline of snapshot history,
ranked-videos breakdown, Track button).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import keyword_engine as ke
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.theme import research_style

logger = logging.getLogger(__name__)


class KeywordResearchWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, seed: str, *, parent: QWidget | None = None):
        super().__init__(parent)
        self.seed = seed

    def run(self) -> None:
        try:
            out = ke.research_keyword(self.seed, ke.ResearchOptions(rank_top=5))
            self.done.emit(out)
        except Exception as exc:
            logger.warning("Keyword research failed", exc_info=True)
            self.failed.emit(str(exc))


class KeywordResearchPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self.setStyleSheet(research_style())

        self._worker: KeywordResearchWorker | None = None
        self._out: ke.ResearchOutput | None = None
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
        self._title = QLabel("Keyword Research")
        self._title.setObjectName("headerTitle")
        self._subtitle = QLabel("Expand ideas via autocomplete, then score the top candidates")
        self._subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        # Search form (mimics the Niche-Scope form row)
        form = QHBoxLayout()
        form.setSpacing(8)
        self._seed_edit = QLineEdit()
        self._seed_edit.setPlaceholderText("e.g. keto diet, minecraft, python tutorial…")
        self._seed_edit.returnPressed.connect(self.start_research)
        self._research_btn = QPushButton("Research")
        self._research_btn.clicked.connect(self.start_research)
        form.addWidget(self._seed_edit, 1)
        form.addWidget(self._research_btn)
        root.addLayout(form)

        # Status bar
        status = QFrame()
        status.setObjectName("statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        self._hint = QLabel(
            "Typing a seed + pressing Research expands it and scores the best keywords."
        )
        self._hint.setObjectName("statusText")
        status_layout.addWidget(self._hint, 1)
        root.addWidget(status)

        # Stacked: empty / results / detail
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_placeholder())
        self._stack.addWidget(self._build_results())
        self._stack.addWidget(self._build_detail())
        root.addWidget(self._stack, 1)

    def _build_placeholder(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        box = QFrame()
        box.setObjectName("emptyState")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(40, 40, 40, 40)
        box_layout.setSpacing(8)
        icon = QLabel("🔎")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(icon)
        text = QLabel("No keywords researched yet")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setObjectName("sectionLabel")
        box_layout.addWidget(text)
        sub = QLabel("Enter a topic and press Research to discover related search terms.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setObjectName("smallLabel")
        box_layout.addWidget(sub)
        layout.addWidget(box)
        layout.addStretch(1)
        self._placeholder = page
        return page

    def _build_results(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._results_meta = QLabel("")
        self._results_meta.setObjectName("statusText")
        layout.addWidget(self._results_meta)

        self._tags_area = QWidget()
        self._tags_layout = QVBoxLayout(self._tags_area)
        self._tags_layout.setContentsMargins(0, 0, 0, 0)
        self._tags_layout.setSpacing(8)
        layout.addWidget(self._tags_area)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Keyword", "Demand", "Competition", "Overall", ""])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.cellClicked.connect(self._on_result_clicked)
        layout.addWidget(self._table, 1)
        self._results_page = page
        return page

    def _build_detail(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self._back_btn = QPushButton("← Back")
        self._back_btn.setProperty("variant", "ghost")
        self._back_btn.clicked.connect(self._show_results_back)
        header.addWidget(self._back_btn)
        header.addStretch(1)
        layout.addLayout(header)

        self._detail_title = QLabel("")
        self._detail_title.setObjectName("kwTitle")
        layout.addWidget(self._detail_title)

        self._detail_source = QLabel("")
        self._detail_source.setObjectName("kwMuted")
        layout.addWidget(self._detail_source)

        summary = QFrame()
        summary.setObjectName("card")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(28)

        def metric(label: str) -> tuple[QVBoxLayout, QLabel]:
            box = QVBoxLayout()
            box.setSpacing(2)
            value = QLabel("0")
            value.setObjectName("kwMetricValue")
            cap = QLabel(label)
            cap.setObjectName("kwMetricLabel")
            box.addWidget(value)
            box.addWidget(cap)
            summary_layout.addLayout(box)
            return box, value

        _, self._demand_value = metric("Demand")
        _, self._competition_value = metric("Competition")
        _, self._overall_value = metric("Overall")
        summary_layout.addStretch(1)
        layout.addWidget(summary)

        # Sparkline section
        spark_card = QFrame()
        spark_card.setObjectName("card")
        spark_layout = QVBoxLayout(spark_card)
        spark_layout.setContentsMargins(16, 12, 16, 12)
        cap = QLabel("Opportunity score history")
        cap.setObjectName("sectionLabel")
        spark_layout.addWidget(cap)
        self._spark = w.Sparkline([], width=560, height=48)
        spark_layout.addWidget(self._spark)
        layout.addWidget(spark_card)

        # Ranked videos
        ranked_label = QLabel("Top ranked videos for this term")
        ranked_label.setObjectName("sectionLabel")
        layout.addWidget(ranked_label)
        self._ranked_list = QVBoxLayout()
        self._ranked_list.setSpacing(6)
        self._ranked_list.addStretch(1)
        layout.addLayout(self._ranked_list, 1)

        self._track_btn = QPushButton("Track this keyword")
        self._track_btn.setProperty("variant", "outline")
        self._track_btn.clicked.connect(self._on_track)
        layout.addWidget(self._track_btn)

        self._detail_term: str | None = None
        self._detail_page = page
        return page

    # ------------------------------------------------------------------ #
    # Research
    # ------------------------------------------------------------------ #
    def start_research(self) -> None:
        seed = self._seed_edit.text().strip()
        if not seed or (self._worker is not None and self._worker.isRunning()):
            return
        self._hint.setText("Expanding via YouTube autocomplete, then scoring top candidates…")
        self._research_btn.setEnabled(False)
        self._research_btn.setText("Researching...")
        self._stack.setCurrentWidget(self._placeholder)
        self._worker = KeywordResearchWorker(seed, parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def re_run(self) -> None:
        """Re-run research with the last seed (used by the container Update button)."""
        if self._out is None or (self._worker is not None and self._worker.isRunning()):
            return
        self._seed_edit.setText(self._out.seed)
        self.start_research()

    def _on_done(self, out: ke.ResearchOutput) -> None:
        self._research_btn.setEnabled(True)
        self._research_btn.setText("Research")
        self._out = out
        self._render_results(out)

    def _on_failed(self, error: str) -> None:
        self._research_btn.setEnabled(True)
        self._research_btn.setText("Research")
        self._hint.setText(f"Research failed: {error}")

    # ------------------------------------------------------------------ #
    # Results rendering
    # ------------------------------------------------------------------ #
    def _render_results(self, out: ke.ResearchOutput) -> None:
        meta_items = [str(len(out.results))]
        if out.ranked > 0:
            meta_items.append(f"competition scored for top {out.ranked}")
        if out.truncated:
            meta_items.append("truncated")
        self._results_meta.setText(
            f"<b>{len(out.results)}</b> related keywords for “{out.seed}”"
            + (" · " + " · ".join(meta_items[1:]) if len(meta_items) > 1 else "")
        )

        # Clear previous tags
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tags_area.setVisible(True)

        if out.matching_terms:
            self._render_tag_row(out.matching_terms, "Matching terms")
        if out.questions:
            self._render_tag_row(out.questions, "Questions")
        self._tags_area.setVisible(bool(out.matching_terms or out.questions))

        self._table.setRowCount(len(out.results))
        for i, r in enumerate(out.results):
            term_item = QTableWidgetItem(r.display_term)
            term_item.setData(Qt.ItemDataRole.UserRole, r.term)
            self._table.setItem(i, 0, term_item)

            demand = w.ScoreBadge(r.demand_score, size="sm")
            self._table.setCellWidget(i, 1, demand)

            label = r.competition_label if r.scored else "Low"
            comp = w.CompetitionBadge(label)
            if not r.scored:
                comp.setToolTip("est. until scored")
            self._table.setCellWidget(i, 2, comp)

            overall = w.ScoreBadge(r.overall_score, size="sm")
            self._table.setCellWidget(i, 3, overall)

            detail = QLabel("Details →")
            detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            detail.setObjectName("linkLabel")
            self._table.setCellWidget(i, 4, detail)

        self._table.resizeColumnsToContents()
        self._stack.setCurrentWidget(self._results_page)

    def _render_tag_row(self, tags: list[str], title: str) -> None:
        card = QFrame()
        card.setObjectName("panel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        cap = QLabel(title)
        cap.setObjectName("sectionLabel")
        layout.addWidget(cap)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for tag in tags[:12]:
            chip = QLabel(tag)
            chip.setObjectName("chip")
            chip.setToolTip("Click to research this term")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.mousePressEvent = lambda _e, t=tag: self._research_tag(t)
            chips.addWidget(chip)
        chips.addStretch(1)
        layout.addLayout(chips)
        self._tags_layout.addWidget(card)

    def _research_tag(self, tag: str) -> None:
        self._seed_edit.setText(tag)
        self.start_research()

    # ------------------------------------------------------------------ #
    # Detail view
    # ------------------------------------------------------------------ #
    def _on_result_clicked(self, row: int, _col: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        term = item.data(Qt.ItemDataRole.UserRole)
        self.show_detail(term)

    def show_detail(self, term: str) -> None:
        row = ke.get_keyword(term)
        if row is None:
            return
        self._detail_term = term
        self._detail_title.setText(row["display_term"])
        self._detail_source.setText(
            f"source: {row['source']} · demand {row['demand_score']} · competition "
            f"{row['competition_score']} ({row['competition_label']})"
        )
        self._demand_value.setText(str(row["demand_score"]))
        self._competition_value.setText(str(row["competition_score"]))
        self._overall_value.setText(str(row["score"]))

        snaps = ke.get_keyword_snapshots(term)
        self._spark.set_points([s["score"] for s in snaps])

        while self._ranked_list.count():
            item = self._ranked_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ranked = ke.get_ranked_videos(term)
        if not ranked:
            note = QLabel("No ranked videos yet. Run research to score this term.")
            note.setObjectName("statusText")
            self._ranked_list.addWidget(note)
        for r in ranked:
            self._ranked_list.addWidget(self._make_ranked_row(r))
        self._ranked_list.addStretch(1)

        self._track_btn.setText("Tracking" if _is_tracked(term) else "Track this keyword")
        self._track_btn.setEnabled(not _is_tracked(term))
        self._stack.setCurrentWidget(self._detail_page)

    def _make_ranked_row(self, r: dict[str, Any]) -> QWidget:
        row = QFrame()
        row.setObjectName("panel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        pos = QLabel(str(r["position"]))
        pos.setObjectName("statKey")
        pos.setFixedWidth(24)
        layout.addWidget(pos)
        title = QLabel(r["title"])
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title, 1)
        views = QLabel(w.format_number(r["view_count"]))
        views.setObjectName("growthPositive")
        layout.addWidget(views)
        return row

    def _on_track(self) -> None:
        if not self._detail_term:
            return
        _set_tracked(self._detail_term)
        self._track_btn.setText("Tracking")
        self._track_btn.setEnabled(False)

    def _show_results_back(self) -> None:
        self._stack.setCurrentWidget(self._results_page)

    def selected_term(self) -> str | None:
        return self._detail_term


# --------------------------------------------------------------------------- #
# Tracked-items helpers (uses the shared tracked_items table)
# --------------------------------------------------------------------------- #
def _is_tracked(term: str) -> bool:
    from s_q_ali_media_downloader.niche_research.storage import db

    return (
        db.get("SELECT 1 FROM tracked_items WHERE kind='keyword' AND ref_id=?", (term,)) is not None
    )


def _set_tracked(term: str) -> None:
    from s_q_ali_media_downloader.niche_research.storage import db

    db.run(
        "INSERT OR IGNORE INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("keyword", term, term, db.now()),
    )
