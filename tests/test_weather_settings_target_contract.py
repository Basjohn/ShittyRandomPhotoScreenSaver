"""Runtime Weather -> Settings semantic navigation contract.

Qt is deliberately not imported.  The semantic target resolver is pure, while
source-level assertions protect the lifecycle route until the physical Windows
PySide test can exercise the actual retained-QML click and modal dialog.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_TARGETS_PATH = ROOT / "ui/settings_launch_targets.py"
_SPEC = importlib.util.spec_from_file_location("srpss_settings_launch_targets", _TARGETS_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_TARGETS_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _TARGETS_MODULE
_SPEC.loader.exec_module(_TARGETS_MODULE)
resolve_settings_launch_target = _TARGETS_MODULE.resolve_settings_launch_target


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_weather_location_target_resolves_to_lazy_weather_settings() -> None:
    target = resolve_settings_launch_target("weather_location")
    assert target is not None
    assert target.tab_key == "widgets"
    assert dict(target.view_state) == {"subtab_id": "weather"}
    assert target.focus_attr == "weather_location"


def test_missing_location_qml_routes_semantic_target_through_family_adapter() -> None:
    qml = _source("rendering/quick/qml/WeatherPresentation.qml")
    weather = _source("rendering/quick/widgets/weather.py")
    binder = _source("rendering/quick/widgets/family_binder.py")

    assert 'weatherRoot.settingsRequested("weather_location")' in qml
    assert '_WEATHER_SETTINGS_TARGET = "weather_location"' in weather
    assert "on_settings_requested=self._on_settings_requested" in binder
    assert "WeatherFamilyAdapter(on_settings_requested=settings_target_requested)" in binder


def test_runtime_target_uses_existing_settings_lifecycle_barrier() -> None:
    display = _source("engine/display_manager.py")
    engine = _source("engine/screensaver_engine.py")
    handlers = _source("engine/engine_handlers.py")

    assert "settings_target_requested = Signal(str)" in display
    assert "manager.settings_target_requested.emit(target)" in display
    assert '"settings_target_requested",' in engine
    assert "request_settings_requested(self, target=str(target_id or \"\"))" in engine
    assert "target: str = \"\"" in handlers
    assert "on_settings_requested(engine, target=intent.target)" in handlers
    assert "initial_target=str(target or \"\").strip() or None" in handlers
    assert "continue_after_runtime_destruction" in handlers


def test_settings_dialog_target_overrides_persisted_navigation_without_timer() -> None:
    dialog = _source("ui/settings_dialog.py")

    assert "resolve_settings_launch_target(initial_target)" in dialog
    assert 'self._initial_view_state_for_tab("widgets")' in dialog
    assert "self._launch_target is not None" in dialog
    assert "_apply_initial_launch_target_focus" in dialog
    # Semantic navigation/focus is synchronous after lazy construction; do not
    # create a target-specific QTimer/single-shot workaround.
    target_focus_start = dialog.index("def _apply_initial_launch_target_focus")
    target_focus_end = dialog.index("def _restore_last_tab_selection", target_focus_start)
    focus_body = dialog[target_focus_start:target_focus_end]
    assert "QTimer" not in focus_body
    assert "single_shot" not in focus_body
