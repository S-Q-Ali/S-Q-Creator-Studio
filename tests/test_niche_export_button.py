"""Tests for the shared export button."""

from __future__ import annotations

import json

from PySide6.QtWidgets import QFileDialog

from s_q_ali_media_downloader.niche_research.ui.export_button import ExportButton

ROWS = [{"title": "Video A", "views": 10}]


def test_export_button_is_disabled_without_data(qapp):
    button = ExportButton("discovery", "Discovery")
    assert button.isEnabled() is False
    assert button.has_data() is False
    button.set_payload([])
    assert button.isEnabled() is False


def test_export_button_enables_with_data(qapp):
    button = ExportButton("discovery", "Discovery")
    button.set_payload(ROWS)
    assert button.isEnabled() is True
    assert button.has_data() is True


def test_export_button_writes_the_chosen_format(qapp, tmp_path, monkeypatch):
    target = tmp_path / "out.json"
    button = ExportButton("discovery", "Discovery")
    button.set_payload(ROWS)

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )

    got: list = []
    button.exported.connect(got.append)
    button.export("json")

    assert got == [str(target)]
    assert json.loads(target.read_text(encoding="utf-8"))[0]["title"] == "Video A"


def test_export_button_reports_write_errors(qapp, tmp_path, monkeypatch):
    button = ExportButton("discovery", "Discovery")
    button.set_payload(ROWS)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("C:/nope/out.json", ""))
    )
    errors: list = []
    button.failed.connect(errors.append)
    button.export("json")
    assert errors and "Export failed" in errors[0]


def test_export_button_without_a_path_writes_nothing(qapp, monkeypatch):
    button = ExportButton("discovery", "Discovery")
    button.set_payload(ROWS)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    got: list = []
    button.exported.connect(got.append)
    assert button.export("csv") is None
    assert got == []
