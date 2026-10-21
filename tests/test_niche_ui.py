"""Offscreen tests for the Niche Research UI (theme, widgets, trending page)."""

from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from s_q_ali_media_downloader.niche_research.research import trending_engine as te
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.theme import research_style
from s_q_ali_media_downloader.niche_research.ui.trending_card import (
    TrendingCardData,
    TrendingChannelCard,
)
from s_q_ali_media_downloader.niche_research.ui.trending_page import (
    TrendingChannelsPage,
    TrendingDiscoveryWorker,
)


def test_format_helpers():
    assert w.format_number(1_820_000) == "1.8M"
    assert w.format_number(64_500) == "64.5K"
    assert w.format_number(450) == "450"


def test_sparkline_scales_big_series(qapp):
    """View counts (millions) used to clamp to the top of the chart, so every
    Competitors sparkline was a flat line."""
    from PySide6.QtGui import QImage

    from s_q_ali_media_downloader.niche_research.ui.widgets import Sparkline

    def render(points):
        spark = Sparkline(points, width=100, height=40)
        image = QImage(spark.size(), QImage.Format.Format_ARGB32)
        image.fill(0)
        spark.render(image)
        return image

    flat = render([1_000_000, 1_000_000])
    rising = render([1_000_000, 2_000_000])
    assert flat != rising
    # A 0-100 series keeps the fixed scale
    scaled = render([0, 50, 100])
    assert scaled.size().width() == 100


def test_earnings_format():
    rpm = {"min": 6.0, "max": 18.0}
    assert w.format_earnings(rpm, 100_000) == "$600-$1.8K"
    assert w.format_earnings(rpm, 10_000) == "$60-$180"


def test_tier_label_and_color():
    assert w.get_viral_score_label(80) == "S-Tier"
    assert w.get_viral_score_label(55) == "A-Tier"
    assert w.get_viral_score_label(35) == "B-Tier"
    assert w.get_viral_score_label(10) == "C-Tier"
    assert w.get_viral_score_color(80) == "High"
    assert w.get_viral_score_color(55) == "Mid"
    assert w.get_viral_score_color(10) == "Low"


def test_initials():
    assert w.get_initials("Tech Talk Daily") == "TT"
    assert w.get_initials("single") == "S"


def test_flow_layout_adds_and_counts(qapp):
    layout = w.FlowLayout()
    widget = QFrame()
    widget.setLayout(layout)
    first = QLabel("a")
    second = QLabel("b")
    layout.addWidget(first)
    layout.addWidget(second)
    assert layout.count() == 2
    assert layout.itemAt(0).widget() is first
    assert layout.itemAt(2) is None
    assert layout.takeAt(0).widget() is first
    assert layout.count() == 1


def test_trending_card_emits_analyze(qapp):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QPushButton

    card = TrendingChannelCard(
        TrendingCardData(
            channel_id="UCx",
            title="My Channel",
            subscriber_count=1000,
            view_count=5000,
            video_count=10,
            viral_score=77,
            growth_rate=60.0,
            is_newly_created=True,
            is_rapidly_growing=True,
            ai_score=80,
            category_name="Tech & AI",
            view_sub_ratio=5.0,
            video_format="longform",
            niche="tech_ai",
        )
    )
    emitted = []
    card.analyze_requested.connect(emitted.append)
    card.show()
    buttons = card.findChildren(QPushButton)
    assert buttons, "card should have the Create Similar Channel button"
    assert buttons[0].text() == "Create Similar Channel"
    QTimer.singleShot(0, buttons[0].click)
    qapp.processEvents()
    assert emitted == ["UCx"]


def test_trending_card_text_is_selectable(qapp):
    from PySide6.QtCore import Qt

    card = TrendingChannelCard(
        TrendingCardData(
            channel_id="UCx",
            title="My Channel",
            subscriber_count=1000,
            view_count=5000,
            video_count=10,
            viral_score=77,
            growth_rate=60.0,
            category_name="Tech & AI",
            view_sub_ratio=5.0,
            video_format="longform",
            niche="tech_ai",
            rpm={"min": 6.0, "max": 18.0, "avg": 12.0},
        )
    )
    sel = Qt.TextInteractionFlag.TextSelectableByMouse
    labels = card.findChildren(QLabel)
    for needle in ("My Channel", "Tech & AI", "+60.0% growth", "5.0x V/S", "Est.", "(RPM $12.0)"):
        matches = [label for label in labels if needle in label.text()]
        assert matches, needle
        assert all(bool(label.textInteractionFlags() & sel) for label in matches), needle


def test_trending_card_has_uniform_width_and_wrapped_title(qapp):
    title = "A very long channel title that should wrap onto two lines instead of being clipped"
    card = TrendingChannelCard(
        TrendingCardData(
            channel_id="UCx",
            title=title,
            subscriber_count=1000,
            view_count=5000,
            video_count=10,
            viral_score=77,
            growth_rate=60.0,
            category_name="Tech & AI",
            view_sub_ratio=5.0,
            video_format="longform",
            niche="tech_ai",
            rpm={"min": 6.0, "max": 18.0, "avg": 12.0},
        )
    )
    assert card.minimumWidth() == card.maximumWidth() == 300
    title_label = next(l for l in card.findChildren(QLabel) if l.text() == title)
    assert title_label.wordWrap() is True
    assert title_label.toolTip() == title


def test_trending_page_renders_rows(isolated_appdata, qapp):
    db.configure(None)
    te.save_trending_channels([_sample("UC1", "One", 90), _sample("UC2", "Two", 20)])
    page = TrendingChannelsPage()
    page.resize(1200, 800)
    page.show()
    qapp.processEvents()

    cards = page.findChildren(TrendingChannelCard)
    assert len(cards) == 2
    # Sorted: viral score desc
    assert cards[0].data().channel_id == "UC1"
    assert page._subtitle.text().startswith("2 channels")
    db.close_db()


def test_trending_page_pagination(isolated_appdata, qapp):
    db.configure(None)
    te.save_trending_channels([_sample(f"UC{i}", f"Ch {i}", i) for i in range(45)])
    page = TrendingChannelsPage()
    page.show()
    qapp.processEvents()
    assert page._page_label.text() == "Page 1 of 3"
    assert page._next_btn.isEnabled() is True
    assert page._prev_btn.isEnabled() is False
    page.show_page(3)
    qapp.processEvents()
    assert page._page_label.text() == "Page 3 of 3"
    assert page._next_btn.isEnabled() is False
    db.close_db()


def test_discovery_start_forces_refresh(isolated_appdata, qapp, monkeypatch):
    db.configure(None)
    monkeypatch.setattr(
        te,
        "refresh_all_trending",
        lambda *a, **k: {"discovered": 0, "niches": 0, "searches_used": 0},
    )
    page = TrendingChannelsPage()
    page._selected_format = "longform"
    page._selected_niche = "faceless"
    page.start_discovery()
    assert page._worker is not None
    assert page._worker.force is True
    assert page._worker.video_format == "longform"
    assert page._worker.niche == "faceless"
    assert "force refresh" in page._message.text()
    db.close_db()


def test_discovery_worker_passes_force(isolated_appdata, monkeypatch):
    captured: dict = {}

    def fake_refresh(*args, **kwargs):
        captured["kwargs"] = kwargs
        return {"discovered": 5, "niches": 1, "searches_used": 2}

    monkeypatch.setattr(te, "refresh_all_trending", fake_refresh)
    worker = TrendingDiscoveryWorker("longform", "faceless", force=True)
    worker.run()
    assert captured["kwargs"]["force"] is True


class _FakeMessageBox:
    answer = None

    @staticmethod
    def question(*args, **kwargs):
        return _FakeMessageBox.answer


def test_start_discovery_full_scan_asks_confirmation(isolated_appdata, qapp, monkeypatch):
    import s_q_ali_media_downloader.niche_research.ui.trending_page as tp

    db.configure(None)
    _FakeMessageBox.answer = False
    monkeypatch.setattr(tp.QMessageBox, "question", _FakeMessageBox.question)
    page = TrendingChannelsPage()
    assert page.selected_format() == "all"
    assert page.selected_niche() == "all"
    page.start_discovery()
    assert page._worker is None  # cancelled before starting
    assert page._discover_btn.isEnabled() is True
    assert page._discover_btn.text() == "Discover"
    db.close_db()


def test_trending_page_empty_state(isolated_appdata, qapp):
    db.configure(None)
    page = TrendingChannelsPage()
    page.show()
    qapp.processEvents()
    assert page._empty_state is not None
    assert page._page_label.text() == "Page 1 of 1"
    db.close_db()


def test_trending_page_niche_combo_width(isolated_appdata, qapp):
    from s_q_ali_media_downloader.niche_research.data import niches

    db.configure(None)
    page = TrendingChannelsPage()
    combo = page._niche_combo
    page._selected_format = "longform"
    page._populate_niche_combo()

    names = [combo.itemText(i) for i in range(combo.count())]
    widest = max(combo.fontMetrics().horizontalAdvance(n) for n in names)
    floor = max(190, min(340, widest + 48))

    assert combo.minimumWidth() == floor
    assert combo.minimumWidth() >= 190
    # popup view matches the combo width so names are not clipped
    assert combo.view().minimumWidth() == floor
    # every niche name fits inside the combo button + popup
    assert widest + 48 <= combo.minimumWidth()
    assert len(niches.LONGFORM_NICHES) == combo.count() - 1
    db.close_db()


def test_trending_page_niche_combo_is_populated_at_startup(isolated_appdata, qapp):
    """The niche filter used to stay empty until the format combo was
    touched, because only _on_format_changed populated it."""
    db.configure(None)
    page = TrendingChannelsPage()
    combo = page._niche_combo
    assert combo.count() >= 1
    assert combo.itemText(0) == "All Niches"
    db.close_db()


def test_ai_only_filter_reaches_the_engine(isolated_appdata, qapp, monkeypatch):
    """The engine supported `ai_only` but nothing could switch it on."""
    db.configure(None)
    seen = {}

    def fake_get(fmt, niche, limit=20, offset=0, ai_only=False):
        seen["ai_only"] = ai_only
        return []

    monkeypatch.setattr(te, "get_trending_channels", fake_get)
    page = TrendingChannelsPage()

    page._ai_only_check.setChecked(True)

    assert seen["ai_only"] is True
    db.close_db()


def test_trending_card_shows_niche_competition_and_difficulty(qapp):
    """Niche.competition and Niche.difficulty were in the catalog but never
    rendered."""
    from s_q_ali_media_downloader.niche_research.ui.trending_card import (
        TrendingCardData,
        TrendingChannelCard,
    )

    card = TrendingChannelCard(
        TrendingCardData(
            channel_id="UCx",
            title="Chan",
            niche_competition="med",
            niche_difficulty="easy",
        )
    )
    badges = [
        b.text() for b in card.findChildren(QLabel) if b.text().startswith(("Comp.", "Diff."))
    ]
    assert "Comp. med" in badges
    assert "Diff. easy" in badges


def test_trending_card_exposes_its_actions(qapp):
    """A discovered channel must be actionable: queue, score, track, open."""
    from s_q_ali_media_downloader.niche_research.ui.trending_card import (
        TrendingCardData,
        TrendingChannelCard,
    )

    card = TrendingChannelCard(TrendingCardData(channel_id="UCx", title="Chan"))
    seen: dict = {}
    card.queue_requested.connect(lambda cid: seen.setdefault("queue", cid))
    card.scorecard_requested.connect(lambda cid: seen.setdefault("scorecard", cid))
    card.track_requested.connect(lambda cid: seen.setdefault("track", cid))
    card.open_requested.connect(lambda cid: seen.setdefault("open", cid))

    buttons = {b.text(): b for b in card.findChildren(QPushButton)}
    buttons["Queue"].click()
    buttons["Scorecard"].click()
    buttons["Track"].click()
    buttons["Open"].click()

    assert seen == {"queue": "UCx", "scorecard": "UCx", "track": "UCx", "open": "UCx"}


def test_trending_page_track_action_tracks_the_channel(isolated_appdata, qapp):
    """Tracking from the discovery card must land in tracked_items so the
    Competitors page can show it."""
    db.configure(None)
    page = TrendingChannelsPage()
    page._track_channel("UCtrack", "Tracked Channel")
    row = db.get(
        "SELECT * FROM tracked_items WHERE kind='channel' AND ref_id='UCtrack'"
    )
    assert row is not None
    assert row["label"] == "Tracked Channel"
    db.close_db()


def test_research_style_renders_unified_dark_theme():
    # The research suite shares the app's single dark ink-plum/cyan theme now;
    # research_style always returns it regardless of the legacy dark argument.
    default = research_style()
    light_arg = research_style(dark=False)
    assert "#dc2626" not in default  # red accent retired in 2.1
    assert "#100E14" in default  # ink-plum page background
    assert "#22D3EE" in default  # cyan accent
    assert default == light_arg


def _sample(channel_id, title, viral_score):
    return te.TrendingChannel(
        channel_id=channel_id,
        title=title,
        description="",
        thumbnail_url="",
        subscriber_count=1000,
        view_count=5000,
        video_count=10,
        published_at="",
        video_format="longform",
        niche="tech_ai",
        category_name="Tech & AI",
        viral_score=viral_score,
        growth_rate=0,
        view_sub_ratio=5.0,
        recent_video_count=2,
        avg_views_per_video=500,
        is_newly_created=False,
        is_rapidly_growing=False,
        ai_score=0,
    )
