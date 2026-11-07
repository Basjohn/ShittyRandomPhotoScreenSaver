"""Settings sliders reload a stored value at the nearest slider position, never one position lower.

A slider storing ``position / scale`` must load that value back to the same position: ``int(0.29 * 100)`` is 28 (the
float product is 28.999...), so a truncating load moved a stored 0.29 to 0.28 on every reload and re-save, and a
Studio commit (which loads its values into the Settings widgets, then runs Settings' own save) came back one
hundredth lower. Proven through the real widgets: the Visualizers tab's spec sliders, the Custom smoothing row and
the shared bar border opacity via the Studio's canonical store, and the generic ``SliderBinding``; plus a source
guard that no Settings tab converts a scaled slider value with a bare ``int``. Values are test-owned, never presets.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.test_spectrum_studio import (  # noqa: F401  (fixtures)
    LightAdapter, _surfaces, dialog_tab, no_gl_checks, settings_manager,
)

ROOT = Path(__file__).resolve().parents[1]
AWKWARD = (0.29, 0.57, 0.58)


def _percent_keys():
    """Spectrum keys stored as hundredths: the Custom smoothing row, the shared border opacity, and every 0..1 spec
    slider (the formerly truncating ones included)."""
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    from core.settings.visualizer_mode_settings import Slider, require_mode_settings
    keys = ["spectrum_visual_smoothing", get_owned_mode_setting_keys("spectrum", "shared_bar")["bar_border_opacity"]]
    for control in require_mode_settings("spectrum").body_controls:
        if (isinstance(control, Slider) and control.scale == 100 and not control.integer
                and control.low <= min(AWKWARD) and max(AWKWARD) <= control.high and not control.source):
            keys.append(control.key)
    return keys


def test_awkward_hundredths_survive_a_studio_commit_through_the_settings_widgets(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, "spectrum", adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    keys = _percent_keys()
    assert any(require_truncating(key) for key in keys)          # the formerly truncating sliders are covered
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    for value in AWKWARD:
        for key in keys:
            controller.bridge.commitValue(key, 0, value)
            assert stored()[key] == pytest.approx(value, abs=1e-9), (key, value)
            assert controller.session.values[key] == pytest.approx(value, abs=1e-9), (key, value)
    controller.close()
    # A fresh Settings load of the last values (the reload path) keeps them too.
    tab._load_settings()
    tab._save_settings_now()
    for key in keys:
        assert stored()[key] == pytest.approx(AWKWARD[-1], abs=1e-9), key


def require_truncating(key: str) -> bool:
    from core.settings.visualizer_mode_settings import require_mode_settings
    try:
        return bool(require_mode_settings("spectrum").control(key).truncate)
    except KeyError:
        return False


def test_spec_slider_positions_are_nearest_and_round_trip():
    from core.settings.visualizer_mode_settings import Slider, require_mode_settings
    for value in AWKWARD:
        for control in require_mode_settings("spectrum").controls:
            if isinstance(control, Slider) and control.scale == 100:
                assert control.position(value) == round(value * 100), control.key
                assert control.position(control.position(value) / control.scale) == control.position(value)


def test_slider_binding_reloads_the_stored_hundredth(qt_app):
    from PySide6.QtWidgets import QSlider
    from ui.tabs.settings_binding import SliderBinding

    class Tab:
        pass
    tab = Tab()
    tab.opacity = QSlider()
    tab.opacity.setRange(0, 100)
    binding = SliderBinding("opacity", scale=100, default=1.0)
    for value in AWKWARD:
        binding.load(tab, {"opacity": value})
        assert tab.opacity.value() == round(value * 100)
        assert binding.save(tab)[1] == pytest.approx(value)


# -------------------------------------------------------------------------------------------- source guard
def _truncating_conversions(source: str) -> list[str]:
    """``int(x * 100)``, ``int(x * 1000)`` and ``int(x * self.scale)``: a scaled slider value truncated."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int"
                and len(node.args) == 1 and isinstance(node.args[0], ast.BinOp)
                and isinstance(node.args[0].op, ast.Mult)):
            continue
        right = node.args[0].right
        if ((isinstance(right, ast.Constant) and right.value in (100, 100.0, 1000, 1000.0))
                or (isinstance(right, ast.Attribute) and right.attr == "scale")):
            found.append(ast.unparse(node))
    return found


def test_no_settings_tab_truncates_a_scaled_slider_value():
    offenders = {}
    for path in sorted((ROOT / "ui" / "tabs").rglob("*.py")):
        found = _truncating_conversions(path.read_text(encoding="utf-8"))
        if found:
            offenders[str(path.relative_to(ROOT))] = found
    assert offenders == {}


def test_source_guard_detects_a_truncating_load_negative_control():
    assert _truncating_conversions("pct = int(tab._config_float('clock', c, 'bg_opacity') * 100)")
    assert _truncating_conversions("val = int(float(raw) * self.scale)")
    assert not _truncating_conversions("pct = int(round(tab._config_float('clock', c, 'bg_opacity') * 100))")
