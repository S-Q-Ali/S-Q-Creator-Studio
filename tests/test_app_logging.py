"""Tests for the application logging setup.

The log lives next to the user's data and is what people attach to bug
reports, so nothing secret may be written to it.
"""

import logging

from s_q_ali_media_downloader import app


def test_secret_filter_redacts_api_keys_from_log_messages():
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        "f",
        1,
        'HTTP Request: GET https://www.googleapis.com/youtube/v3/search?key=AIzaSECRET&q=cats',
        None,
        None,
    )

    app.RedactSecrets().filter(record)

    assert "AIzaSECRET" not in record.getMessage()
    assert "cats" in record.getMessage()


def test_secret_filter_leaves_ordinary_messages_alone():
    record = logging.LogRecord(
        "app", logging.INFO, "f", 1, "app starting", None, None
    )

    app.RedactSecrets().filter(record)

    assert record.getMessage() == "app starting"
