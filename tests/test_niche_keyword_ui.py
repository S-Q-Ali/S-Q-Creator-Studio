"""Offscreen tests for the Keyword Research page widgets."""

from PySide6.QtWidgets import QLabel

from s_q_ali_media_downloader.niche_research.research import keyword_engine as ke
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.keyword_page import KeywordResearchPage


def test_research_style_has_app_font_family():
    from s_q_ali_media_downloader.niche_research.ui.theme import FONT_FAMILY, research_style

    css = research_style()
    assert FONT_FAMILY in css
    assert "Segoe UI" in css


def test_score_badge_object_names(qapp):
    from s_q_ali_media_downloader.niche_research.ui.theme import research_style

    css = research_style(dark=False)
    assert "scoreBadgeGreen" in css
    assert "competitionBadge16a34a" in css

    high = w.ScoreBadge(90)
    assert high.objectName() == "scoreBadgeGreen"
    mid = w.ScoreBadge(50)
    assert mid.objectName() == "scoreBadgeYellow"
    low = w.ScoreBadge(10)
    assert low.objectName() == "scoreBadgeRed"
    small = w.ScoreBadge(70, size="sm")
    assert small.objectName() == "scoreBadgeSmLime"

    comp_low = w.CompetitionBadge("Low")
    assert comp_low.objectName() == "competitionBadge16a34a"
    comp_high = w.CompetitionBadge("High")
    assert comp_high.objectName() == "competitionBadgeDc2626"


def test_sparkline_renders(qapp):
    spark = w.Sparkline([10, 40, 70, 30, 85])
    assert spark.sizeHint().width() == 140
    spark.set_points([5, 90, 50])
    assert spark.minimumWidth() == 140
    spark2 = w.Sparkline([], width=200, height=40)
    assert spark2.width() == 200


def test_score_helper_functions():
    assert w.score_label(90) == "Very High"
    assert w.score_label(65) == "High"
    assert w.score_label(45) == "Medium"
    assert w.score_label(25) == "Low"
    assert w.score_label(5) == "Very Low"
    assert w.score_color(85) == "green"
    assert w.score_color(55) == "yellow"
    assert w.competition_color("High") == "#dc2626"
    assert w.competition_color("Medium") == "#eab308"
    assert w.competition_color("Low") == "#16a34a"


def _seed_output():
    return ke.ResearchOutput(
        seed="keto",
        results=[
            ke.KeywordResult(
                term="keto diet",
                display_term="keto diet",
                demand_score=100,
                competition_score=30,
                competition_label="Low",
                overall_score=70,
                source="autocomplete",
                scored=True,
            ),
            ke.KeywordResult(
                term="what is keto",
                display_term="what is keto",
                demand_score=90,
                competition_score=10,
                competition_label="Low",
                overall_score=81,
                source="autocomplete",
                scored=True,
            ),
        ],
        related_count=2,
        matching_terms=["keto meal plan"],
        questions=["what is keto"],
        ranked=2,
        truncated=False,
    )


def test_keyword_page_renders_results(isolated_appdata, qapp):
    from s_q_ali_media_downloader.niche_research.ui.keyword_page import KeywordResearchPage

    db.configure(None)
    page = KeywordResearchPage()
    page.resize(1000, 700)
    page.show()
    qapp.processEvents()

    assert page._stack.currentWidget() is page._placeholder
    kw_edit = page._seed_edit
    kw_edit.setText("keto")
    page._on_done(_seed_output())
    qapp.processEvents()

    table = page._table
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "keto diet"
    assert "related keywords for" in page._results_meta.text()
    assert page._stack.currentWidget() is page._results_page

    # tags rendered
    chips = page._tags_area.findChildren(QLabel)
    assert any("keto meal plan" in c.text() for c in chips)
    assert any("what is keto" in c.text() for c in chips)
    db.close_db()


def test_keyword_page_detail_view(isolated_appdata, qapp):
    db.configure(None)

    def seed_detail():
        return ke.ResearchOutput(
            seed="keto",
            results=[
                ke.KeywordResult(
                    term="keto diet",
                    display_term="keto diet",
                    demand_score=80,
                    competition_score=40,
                    competition_label="Medium",
                    overall_score=48,
                    source="search",
                    scored=True,
                )
            ],
            related_count=1,
            matching_terms=[],
            questions=[],
            ranked=1,
            truncated=False,
        )

    page = KeywordResearchPage()
    page.resize(1000, 700)
    page.show()
    page._on_done(seed_detail())
    qapp.processEvents()

    # persist the keyword row that research_keyword would have saved
    ke._upsert_keyword(
        "keto diet",
        "keto diet",
        score=48,
        demand_score=80,
        competition_score=40,
        competition_label="Medium",
        source="search",
        language="en",
        country="us",
    )

    table = page._table
    assert table.rowCount() == 1

    # view the detail (simulate row click)
    page._on_result_clicked(0, 0)
    qapp.processEvents()

    assert page._detail_term == "keto diet"
    assert page._demand_value.text() == "80"
    assert page._competition_value.text() == "40"
    assert page._overall_value.text() == "48"
    assert page._stack.currentWidget() is page._detail_page
    assert page._track_btn.text() == "Track this keyword"

    # Track it
    page._on_track()
    assert page._track_btn.text() == "Tracking"
    assert page._track_btn.text() != "Track this keyword"

    rows = db.all("SELECT * FROM tracked_items WHERE kind='keyword' AND ref_id=?", ("keto diet",))
    assert len(rows) == 1

    # Back
    page._back_btn.click()
    qapp.processEvents()
    assert page._stack.currentWidget() is page._results_page
    db.close_db()


def test_keyword_detail_metrics_start_honest(isolated_appdata, qapp):
    db.configure(None)
    page = KeywordResearchPage()
    # no term selected yet -> "—" instead of a fabricated 0
    assert page._demand_value.text() == "—"
    assert page._competition_value.text() == "—"
    assert page._overall_value.text() == "—"
    db.close_db()


def test_keyword_page_failed(isolated_appdata, qapp):
    db.configure(None)
    page = KeywordResearchPage()
    page.show()
    page._on_failed("network down")
    assert "Research failed" in page._hint.text()
    assert page._research_btn.isEnabled() is True
    db.close_db()


def test_keyword_re_run_restarts_last_search(isolated_appdata, qapp, monkeypatch):
    calls = []

    def fake_start():
        calls.append(1)

    db.configure(None)
    page = KeywordResearchPage()
    monkeypatch.setattr(page, "start_research", fake_start)
    page._on_done(_seed_output())
    page.re_run()
    assert page._seed_edit.text() == "keto"
    assert calls == [1]
    db.close_db()


def test_keyword_re_run_noop_without_results(isolated_appdata, qapp, monkeypatch):
    calls = []

    def fake_start():
        calls.append(1)

    db.configure(None)
    page = KeywordResearchPage()
    monkeypatch.setattr(page, "start_research", fake_start)
    page.re_run()
    assert calls == []
    db.close_db()
