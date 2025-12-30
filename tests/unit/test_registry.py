import types

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


@pytest.mark.unit
def test_lazy_engine_runner_is_lazy_until_invoked(monkeypatch):
    """Lazy runners should not be imported during registry parsing."""

    class RecordingLazy(registry._LazyEngineRunner):
        def __init__(self):
            super().__init__("app.services.engines.yara.yara")
            self.load_calls = 0

        def _load(self):
            self.load_calls += 1
            return lambda path: {"status": "ok"}

    runner = RecordingLazy()

    monkeypatch.setattr(registry, "AVAILABLE_ENGINES", {"yara": runner})
    monkeypatch.setattr(
        registry, "load_engine_config", lambda path=None: {"engines": {"yara": {"enabled": True}}}
    )

    engines = registry.get_active_engines()

    assert "yara" in engines
    assert runner.load_calls == 0  # no eager import

    # Loading should happen only when the runner is actually invoked
    engines["yara"]["runner"]("dummy-path")
    assert runner.load_calls == 1


@pytest.mark.unit
def test_lazy_engine_failure_surfaces_on_invocation(monkeypatch):
    class FailingLazy(registry._LazyEngineRunner):
        def _load(self):  # pragma: no cover - invoked indirectly
            return None

    runner = FailingLazy("app.missing.module")

    monkeypatch.setattr(registry, "AVAILABLE_ENGINES", {"missing": runner})
    monkeypatch.setattr(
        registry, "load_engine_config", lambda path=None: {"engines": {"missing": {"enabled": True}}}
    )

    engines = registry.get_active_engines()

    assert "missing" in engines
    with pytest.raises(RuntimeError):
        engines["missing"]["runner"]("dummy-path")


@pytest.mark.unit
def test_warm_up_active_engines_eagerly_imports_lazy_runner(monkeypatch):
    class RecordingLazy(registry._LazyEngineRunner):
        def __init__(self):
            super().__init__("app.services.engines.yara.yara")
            self.load_calls = 0

        def _load(self):
            self.load_calls += 1
            return lambda path: {"status": "ok"}

    runner = RecordingLazy()
    monkeypatch.setattr(registry, "AVAILABLE_ENGINES", {"yara": runner})
    monkeypatch.setattr(
        registry, "load_engine_config", lambda path=None: {"engines": {"yara": {"enabled": True}}}
    )

    warm_up_result = registry.warm_up_active_engines()

    assert warm_up_result == {"yara": True}
    assert runner.load_calls == 1


@pytest.mark.unit
def test_warm_up_active_engines_handles_load_failures(monkeypatch):
    class FailingLazy(registry._LazyEngineRunner):
        def __init__(self):
            super().__init__("app.services.engines.yara.yara")

        def _load(self):  # pragma: no cover - invoked indirectly
            raise RuntimeError("boom")

    runner = FailingLazy()
    monkeypatch.setattr(registry, "AVAILABLE_ENGINES", {"yara": runner})
    monkeypatch.setattr(
        registry, "load_engine_config", lambda path=None: {"engines": {"yara": {"enabled": True}}}
    )

    warm_up_result = registry.warm_up_active_engines()

    assert warm_up_result == {"yara": False}


@pytest.mark.unit
def test_lazy_engine_runner_invokes_module_warm_up(monkeypatch):
    called = {"count": 0}

    def warm_up():
        called["count"] += 1
        return True

    module = types.SimpleNamespace(run=lambda path: {"status": "ok"}, warm_up=warm_up)
    monkeypatch.setattr(registry.importlib, "import_module", lambda path: module)

    runner = registry._LazyEngineRunner("app.services.engines.fake")

    assert runner.warm_up() is True
    assert called["count"] == 1
