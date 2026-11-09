"""Studio chrome is derived from SRPSS Settings-theme semantics and keeps contrast in every shipped theme."""
from __future__ import annotations

from pathlib import Path

import pytest

from ui.studio.theme import contrast, studio_theme

THEMES = sorted((Path(__file__).resolve().parents[1] / "themes").glob("*.srtheme"))


def _rgb(text):
    text = text.lstrip("#")[-6:]
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


@pytest.mark.parametrize("path", THEMES, ids=lambda p: p.stem[:40])
def test_every_theme_yields_readable_studio_chrome(path):
    from ui.settings_theme_io import load_settings_theme_file
    theme = load_settings_theme_file(path)
    skin = studio_theme(theme)
    panel = _rgb(skin["panel"])
    assert contrast(_rgb(skin["text"]), panel) >= 4.5
    assert contrast(_rgb(skin["accent"]), panel) >= 3.0
    assert contrast(_rgb(skin["focus"]), panel) >= 3.0
    assert contrast(_rgb(skin["accentText"]), _rgb(skin["accent"])) >= 4.5
    if theme.backdrop.enabled:
        from PySide6.QtGui import QColor
        window = QColor(skin["windowSurface"])
        for pole in (0.0, 1.0):
            base = (pole, pole, pole)
            base = tuple(channel * window.alphaF() + below * (1 - window.alphaF())
                         for channel, below in zip((window.redF(), window.greenF(), window.blueF()), base))
            alpha = float(skin["panelAlpha"])
            composed = tuple(channel * alpha + below * (1 - alpha) for channel, below in zip(panel, base))
            assert contrast(_rgb(skin["text"]), composed) >= 4.5
            assert contrast(_rgb(skin["textDim"]), composed) >= 3.0


@pytest.mark.parametrize("parent_alpha", [53, 173])
@pytest.mark.parametrize("child_alpha", [74, 201])
def test_panel_passes_its_own_density_to_the_guard_above_the_existing_window(parent_alpha, child_alpha, monkeypatch):
    from dataclasses import replace
    import ui.studio.theme as material
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    # Both opacity recipes and the guard are test-owned here: this boundary
    # proves composition ownership, independently of any catalogue calibration.
    theme = replace(DEFAULT_DARK_SETTINGS_THEME,
                    backdrop=NativeBackdropStyle("glass", Rgba(20, 40, 60, 100)),
                    colors={**DEFAULT_DARK_SETTINGS_THEME.colors,
                            "window.dialog_glass": Rgba(18, 36, 54, parent_alpha),
                            "panel.group.surface": Rgba(30, 60, 90, child_alpha)})
    monkeypatch.setattr(material, "PANEL_MATERIAL_FLOOR", .43)
    admitted = []
    def guard(colour, alpha, backgrounds, inks):
        admitted.append((alpha, tuple(backgrounds)))
        return alpha
    monkeypatch.setattr(material, "_readable_alpha", guard)
    skin = material.studio_theme(theme)
    expected = max(.43, theme.color("panel.group.surface").a / 255)
    assert float(skin["panelAlpha"]) == pytest.approx(expected, abs=.00051)
    assert admitted[0][0] == expected
    # The parent is already represented in the guard's actual backdrop poles.
    window = theme.window_surface()
    expected_bases = [tuple(channel/255*(window.a/255) + pole*(1-window.a/255)
                            for channel in (window.r, window.g, window.b)) for pole in (0, 1)]
    assert admitted[0][1] == tuple(expected_bases)


def test_chrome_follows_the_theme_not_hard_coded_colours():
    from ui.settings_theme_io import load_settings_theme_file
    if len(THEMES) < 2:
        pytest.skip("needs two theme files")
    skins = [studio_theme(load_settings_theme_file(path)) for path in THEMES[:6]]
    for key in ("bg", "panel", "accent"):
        assert len({skin[key] for skin in skins}) > 1, key


def test_a_theme_change_reskins_subscribers(qt_app):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.studio.theme import subscribe_studio_theme
    if not THEMES:
        pytest.skip("no theme files")
    seen = []
    unsubscribe = subscribe_studio_theme(seen.append)
    original = get_active_settings_theme()
    try:
        set_active_settings_theme(load_settings_theme_file(THEMES[0]))
        assert seen and seen[-1] == studio_theme(load_settings_theme_file(THEMES[0]))
    finally:
        set_active_settings_theme(original)
        unsubscribe()


# ----------------------------------------------------------------- instrument wells (trace cards, transport bar)
WELL_INKS = {"wellText": 4.5, "wellDim": 3.0, "wellTrace1": 3.0, "wellTrace2": 3.0, "wellTrace3": 3.0}


@pytest.mark.parametrize("path", THEMES, ids=lambda p: p.stem[:40])
def test_instrument_well_inks_read_on_their_well_in_every_theme(path):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.theme_semantics import settings_theme_is_light
    theme = load_settings_theme_file(path)
    skin = studio_theme(theme)
    for name, minimum in WELL_INKS.items():
        assert contrast(_rgb(skin[name]), _rgb(skin["well"])) >= minimum, name
    # Instrument wells are UI semantic surfaces in every palette polarity; the
    # viewport backing belongs exclusively to the authored scene.
    assert _rgb(skin["well"]) == _rgb(skin["input"])


def test_the_former_viewport_well_is_illegible_on_a_light_theme_negative_control():
    """Before: trace cards and the transport readout sat on the viewport tone with the panel's inks."""
    from ui.settings_theme_io import load_settings_theme_file
    from ui.theme_semantics import settings_theme_is_light
    light = [studio_theme(t) for t in map(load_settings_theme_file, THEMES) if settings_theme_is_light(t)]
    if not light:
        pytest.skip("no light shipped theme")
    for skin in light:
        assert contrast(_rgb(skin["textDim"]), _rgb(skin["viewportBg"])) < 3.0


class _Store:
    def __init__(self, mode):
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0},
                                                                 mode=mode).resolved_config)

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


def test_trace_cards_and_the_transport_readout_wear_the_well(qt_app):
    """The shell binds the trace cards, the transport bar and its time readout to the well roles (hidden render)."""
    from PySide6.QtGui import QColor
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.settings_theme_io import load_settings_theme_file
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    from ui.theme_semantics import settings_theme_is_light
    themes = [t for t in map(load_settings_theme_file, THEMES) if settings_theme_is_light(t)]
    if not themes:
        pytest.skip("no light shipped theme")
    disable_per_call_gl_error_checking()
    skin = studio_theme(themes[0])
    adapter = create_adapter("bubble")
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
        return surfaces[0]
    controller = StudioController(adapter, _Store("bubble"), _Presence(), factory, theme_provider=lambda: skin)
    try:
        assert controller.open()
        surface = surfaces[0]
        surface.pump(3)
        found, stack = {}, [surface.host.root]
        while stack:
            item = stack.pop()
            found.setdefault(item.objectName(), []).append(item)
            stack.extend(item.childItems())
        (readout,) = found["transportTime"]
        (scrub,) = found["scrubBar"]
        assert readout.property("color") == QColor(skin["wellDim"])
        # The transport overlays the scene, so it keeps the well's RGB opaque.
        transport_colour = QColor(skin["well"])
        transport_colour.setAlpha(255)
        assert scrub.property("color") == transport_colour
        traces = found.get("signalTrace", [])
        assert traces, "the open group shows no signal trace"
        assert all(t.property("color") == QColor(skin["well"]) for t in traces)
        assert QColor(skin["well"]) != QColor(skin["viewportBg"])
    finally:
        controller.close()
