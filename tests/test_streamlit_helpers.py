import pytest

pytest.importorskip("streamlit")

from ui.streamlit_app import readable_status, render_engine_table


def test_readable_status_variants():
    assert readable_status("done").lower().startswith("✅".lower())
    assert readable_status("DONE_WITH_ERRORS").startswith("⚠️")
    assert readable_status(None) == "pending"
    assert readable_status("queued") == "queued"


def test_render_engine_table():
    table = render_engine_table(
        {
            "clamav": {
                "status": "ok",
                "verdict": "clean",
                "signature": "sig1",
                "severity": "low",
                "confidence": 0.5,
                "duration": 1.2,
                "error": None,
            }
        }
    )

    assert table[0]["engine"] == "clamav"
    assert table[0]["verdict"] == "clean"
    assert table[0]["signature"] == "sig1"
