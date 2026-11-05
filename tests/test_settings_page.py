"""Tests for the Settings page's Groq key test."""

from __future__ import annotations

from s_q_ali_media_downloader.ui.settings_page import SettingsPage


def test_the_groq_key_has_a_test_button(qapp, isolated_appdata):
    page = SettingsPage()

    assert page.btn_test_groq.text() == "Test"
    assert "Groq" in page.btn_test_groq.toolTip()


def test_testing_without_a_key_reports_it_without_starting_a_worker(
    qapp, isolated_appdata
):
    page = SettingsPage()
    page.groq_edit.clear()

    page._test_groq_key()

    assert "Enter a Groq API key" in page.groq_status.text()
    assert page._groq_worker is None


def test_a_successful_test_shows_the_model(qapp, isolated_appdata):
    page = SettingsPage()

    page._on_groq_test_ok("openai/gpt-oss-120b")

    assert "works" in page.groq_status.text()
    assert "gpt-oss-120b" in page.groq_status.text()


def test_a_failed_test_shows_the_error_inline(qapp, isolated_appdata):
    page = SettingsPage()

    page._on_groq_test_failed("Groq answered 401: invalid_api_key")

    assert "failed" in page.groq_status.text().lower()
    assert "401" in page.groq_status.text()


def test_editing_the_key_clears_a_stale_result(qapp, isolated_appdata):
    page = SettingsPage()
    page._on_groq_test_ok("openai/gpt-oss-120b")

    page.groq_edit.setText("gsk_a_different_key")

    assert "test it again" in page.groq_status.text().lower()


def test_the_test_button_is_re_enabled_when_the_worker_finishes(
    qapp, isolated_appdata
):
    page = SettingsPage()
    page.btn_test_groq.setEnabled(False)

    page._on_groq_test_finished()

    assert page.btn_test_groq.isEnabled()
    assert page.btn_test_groq.text() == "Test"


def test_a_late_result_for_an_old_key_is_not_shown_as_success(
    qapp, isolated_appdata
):
    page = SettingsPage()
    page.groq_edit.setText("gsk_old")
    page._groq_tested_key = "gsk_old"
    page.groq_edit.setText("gsk_new")

    page._on_groq_test_ok("openai/gpt-oss-120b")

    assert "works" not in page.groq_status.text()
    assert "test it again" in page.groq_status.text().lower()


def test_a_running_key_test_is_reported(qapp, isolated_appdata):
    class FakeWorker:
        def isRunning(self):
            return True

    page = SettingsPage()
    page._groq_worker = FakeWorker()

    assert page.key_test_running() is True


def test_the_gemini_key_has_its_own_test_button(qapp, isolated_appdata):
    page = SettingsPage()

    assert page.btn_test_gemini.text() == "Test"
    assert "Gemini" in page.btn_test_gemini.toolTip()


def test_testing_without_a_gemini_key_reports_it(qapp, isolated_appdata):
    page = SettingsPage()
    page.gemini_edit.clear()

    page._test_gemini_key()

    assert "Enter a Gemini API key" in page.gemini_status.text()
    assert page._gemini_worker is None


def test_a_successful_gemini_test_shows_the_model(qapp, isolated_appdata):
    page = SettingsPage()
    page.gemini_edit.setText("gemini-key")
    page._gemini_tested_key = "gemini-key"

    page._on_gemini_test_ok("gemini-3.8-flash")

    assert "works" in page.gemini_status.text()
    assert "gemini-3.8-flash" in page.gemini_status.text()


def test_a_failed_gemini_test_shows_the_error(qapp, isolated_appdata):
    page = SettingsPage()
    page.gemini_edit.setText("gemini-key")
    page._gemini_tested_key = "gemini-key"

    page._on_gemini_test_failed("Gemini answered 401: invalid key")

    assert "failed" in page.gemini_status.text().lower()
    assert "401" in page.gemini_status.text()


def test_a_running_gemini_test_is_reported(qapp, isolated_appdata):
    class FakeWorker:
        def isRunning(self):
            return True

    page = SettingsPage()
    page._gemini_worker = FakeWorker()

    assert page.key_test_running() is True


def test_the_discovery_browser_is_shown_by_default_and_can_be_hidden(
    qapp, isolated_appdata
):
    from s_q_ali_media_downloader.ui import settings_page as sp

    page = SettingsPage()
    page.load()

    assert page.show_browser_check.isChecked() is True
    assert sp.discovery_browser_is_visible() is True

    page.show_browser_check.setChecked(False)
    page.save()

    assert sp.discovery_browser_is_visible() is False

    page.show_browser_check.setChecked(True)
    page.save()


# --------------------------------------------------------------------------- #
# where the keys live, stated per OS (issue #13)
# --------------------------------------------------------------------------- #
def _page_with_backend(qapp, isolated_appdata, monkeypatch, backend: str) -> SettingsPage:
    from s_q_ali_media_downloader.ui import settings_page as sp

    monkeypatch.setattr(sp.settings_store, "secret_backend_name", lambda: backend)
    page = SettingsPage()
    page.load()
    return page


def test_the_keyring_note_names_the_keychain_and_not_windows(
    qapp, isolated_appdata, monkeypatch
):
    page = _page_with_backend(qapp, isolated_appdata, monkeypatch, "keyring")

    text = page.key_storage_note.text().lower()
    assert "keychain" in text
    assert "windows" not in text


def test_the_plain_note_admits_the_keys_are_unencrypted(
    qapp, isolated_appdata, monkeypatch
):
    page = _page_with_backend(qapp, isolated_appdata, monkeypatch, "plain")

    text = page.key_storage_note.text().lower()
    assert "unencrypted" in text
    assert "windows" not in text


def test_the_dpapi_note_keeps_the_windows_wording(qapp, isolated_appdata, monkeypatch):
    page = _page_with_backend(qapp, isolated_appdata, monkeypatch, "dpapi")

    assert "windows" in page.key_storage_note.text().lower()


def test_an_unreadable_key_asks_again_without_naming_windows(
    qapp, isolated_appdata, monkeypatch
):
    """The database can be copied from a machine that sealed the key a
    different way; the message must fit the machine it is shown on."""
    from s_q_ali_media_downloader.ui import settings_page as sp

    monkeypatch.setattr(sp.settings_store, "secret_backend_name", lambda: "keyring")
    monkeypatch.setattr(sp.settings_store, "secret_is_unreadable", lambda key: True)

    page = SettingsPage()
    page.load()

    assert page.key_warning.isHidden() is False
    assert "Groq API key" in page.key_warning.text()
    assert "Windows" not in page.key_warning.text()
    assert "Enter them again" in page.key_warning.text()


# --------------------------------------------------------------------------- #
# the vertical 9:16 and the shorts split (tasks/plan-vertical-reframe.md)
# --------------------------------------------------------------------------- #
def _page_with_fresh_store(qapp, tmp_path):
    """A page whose preferences live in a file of their own."""
    from PySide6.QtCore import QSettings

    page = SettingsPage()
    page.settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat)
    page.load()
    return page


def test_the_vertical_version_is_off_by_default(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)

    assert page.vertical.isChecked() is False


def test_the_split_is_off_by_default(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)

    assert page.split.currentText() == "Off"


def test_the_split_offers_every_mode_the_engine_knows(qapp, tmp_path):
    from s_q_ali_media_downloader.engine import SPLIT_OPTIONS

    page = _page_with_fresh_store(qapp, tmp_path)

    choices = [page.split.itemText(i) for i in range(page.split.count())]
    assert choices == list(SPLIT_OPTIONS)


def test_the_clip_count_shows_only_in_the_n_clips_mode(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)

    assert page.clips.isHidden()

    page.split.setCurrentText("N clips")
    assert page.clips.isHidden() is False

    page.split.setCurrentText("60 s")
    assert page.clips.isHidden()


def test_the_vertical_choice_survives_a_save_and_a_load(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)

    page.vertical.setChecked(True)
    page.save()
    page.vertical.setChecked(False)
    page.load()

    assert page.vertical.isChecked() is True


def test_the_split_mode_and_the_clip_count_survive_a_load(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)

    page.split.setCurrentText("N clips")
    page.clips.setValue(11)
    page.save()
    page.split.setCurrentText("Off")
    page.clips.setValue(6)
    page.load()

    assert page.split.currentText() == "N clips"
    assert page.clips.value() == 11
    assert page.clips.isHidden() is False


def test_a_stored_mode_the_app_does_not_know_falls_back_to_off(qapp, tmp_path):
    page = _page_with_fresh_store(qapp, tmp_path)
    page.settings.setValue("split", "every second")
    page.settings.setValue("clips", "not a number")

    page.load()

    assert page.split.currentText() == "Off"
    assert page.clips.value() == 6
