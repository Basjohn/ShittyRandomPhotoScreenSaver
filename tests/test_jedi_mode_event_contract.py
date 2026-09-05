from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_jedi_mode_defaults_off_and_settings_ui_is_glow_scoped() -> None:
    defaults = json.loads(_text("core/settings/defaults_snapshot.json"))
    assert defaults["input"]["widget_glow_jedi_mode"] is False

    model = _text("core/settings/models/_core.py")
    assert "widget_glow_jedi_mode: bool = False" in model
    assert 'settings.get("input.widget_glow_jedi_mode", False)' in model

    display_tab = _text("ui/tabs/display_tab.py")
    assert 'QCheckBox(\n            "Jedi Mode - Please Don\'t Do This"' in display_tab
    assert 'setProperty("circleIndicator", True)' in display_tab
    assert "widget_glow_jedi_widget" in display_tab
    assert "_widget_glow_detail_rows" in display_tab


def test_jedi_hover_reuses_existing_passive_hover_edges_without_timer() -> None:
    for relative in (
        "rendering/quick/qml/OverlayWidget.qml",
        "rendering/quick/qml/VisualizerPresentation.qml",
    ):
        source = _text(relative)
        assert "signal jediModeRequested(string trigger)" in source
        assert 'jediModeRequested("hover")' in source
        assert "onHoveredChanged" in source
        assert "Timer {" not in source


def test_jedi_click_reuses_discrete_click_glow_hit_test_and_event_system() -> None:
    scene = _text("rendering/quick/scene_controller.py")
    assert 'self._publish_jedi_mode_event("click", "visualizer")' in scene
    assert "ordinary_target.model_identity" in scene

    engine = _text("engine/screensaver_engine.py")
    assert "event_system.publish(" in engine
    assert "JEDI_MODE_EVENT" in engine
    assert "self.event_system.subscribe(_JEDI_MODE_EVENT, self._on_jedi_mode_event)" in engine


def test_jedi_player_has_hard_two_slot_cap_and_no_recurring_owner() -> None:
    source = _text("core/audio/jedi_mode_sound.py")
    parsed = ast.parse(source)
    names = {node.id for node in ast.walk(parsed) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(parsed) if isinstance(node, ast.Attribute)}
    assert "QTimer" not in names
    assert "Timer" not in names
    assert "schedule_recurring" not in attrs
    assert "single_shot" not in attrs
    assert "for index in range(2):" in source
    assert "Dropped event; two playback slots already busy" in source
    assert "slot.busy = True" in source  # synchronous reservation closes rapid-event race


def test_jedi_resource_is_explicit_in_every_build_family_and_installer() -> None:
    for relative in (
        "scripts/build_nuitka.ps1",
        "scripts/build_nuitka_mc_onedir.ps1",
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_mc_onedir.ps1",
        "tools/build_layout.ps1",
        "tools/build_runner.py",
        "scripts/SRPSS_Installer.iss",
        "scripts/SRPSS_MediaCenter_Installer.iss",
    ):
        assert "jedimodeyall.mp3" in _text(relative), relative
