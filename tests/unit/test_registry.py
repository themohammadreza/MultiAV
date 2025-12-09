import pytest

from app.services.orchestrator import registry


@pytest.mark.unit
def test_parse_engine_respects_enabled_flag():
    assert registry._parse_engine("clamav", {"enabled": False}) is None


@pytest.mark.unit
def test_get_active_engines_defaults_on_empty_config(monkeypatch):
    monkeypatch.setattr(registry, "load_engine_config", lambda path=None: {})

    engines = registry.get_active_engines()

    for name in registry.AVAILABLE_ENGINES:
        assert name in engines
        assert engines[name]["timeout"] == registry.DEFAULT_ENGINE_TIMEOUT
        assert engines[name]["weight"] == registry.DEFAULT_ENGINE_WEIGHT


@pytest.mark.unit
def test_get_engine_weights_handles_missing(monkeypatch):
    fake_registry = {
        "clamav": {"weight": 0.2},
        "custom": {"weight": -1},
    }

    weights = registry.get_engine_weights(fake_registry)

    assert weights == {"clamav": 0.2, "custom": -1}


@pytest.mark.unit
def test_get_active_engines_loads_from_yaml(tmp_path):
    """Validates config/engines.yaml integration"""
    config_file = tmp_path / "engines.yaml"
    config_file.write_text(
        """
engines:
  clamav:
    enabled: true
    weight: 0.5
    timeout: 60
  yara:
    enabled: false
"""
    )

    engines = registry.get_active_engines(config_path=config_file)

    assert "clamav" in engines
    assert engines["clamav"]["weight"] == 0.5
    assert engines["clamav"]["timeout"] == 60
    assert "yara" not in engines  # Disabled


@pytest.mark.unit
def test_get_active_engines_graceful_on_bad_yaml(tmp_path):
    """Malformed YAML shouldn't crash, should fall back to defaults"""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("engines:\n  - this: is: broken")

    engines = registry.get_active_engines(config_path=bad_yaml)

    # Should return defaults instead of crashing
    assert len(engines) > 0
