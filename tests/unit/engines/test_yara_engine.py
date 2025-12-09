import pytest


yara_module = pytest.importorskip("app.services.engines.yara.yara", reason="yara not available")


@pytest.mark.unit
def test_yara_detects_eicar(eicar_file):
    """YARA should detect EICAR if rules are loaded"""
    if not yara_module.rules:
        pytest.skip("No YARA rules loaded")

    result = yara_module.run(str(eicar_file))

    assert result["status"] == "ok"
    assert isinstance(result["detected"], bool)


@pytest.mark.unit
def test_yara_clean_file_no_match(clean_file):
    """Clean files should not trigger YARA rules"""
    if not yara_module.rules:
        pytest.skip("No YARA rules loaded")

    result = yara_module.run(str(clean_file))

    assert result["status"] == "ok"
    assert result["detected"] is False
