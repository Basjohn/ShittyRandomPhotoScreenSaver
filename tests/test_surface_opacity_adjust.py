"""Surface overrides preserve authoring data and travel through real style seams."""
from dataclasses import dataclass, replace

import pytest

from core.settings.surface_opacity import (
    adjusted_surface_density, admit_opacity_adjust, project_settings_opacity_adjust,
    resolve_opacity_adjust,
)


@pytest.fixture(autouse=True)
def restore_projection():
    from core.settings.surface_opacity import settings_opacity_adjust
    before = settings_opacity_adjust()
    yield
    project_settings_opacity_adjust(before)


@pytest.mark.parametrize("density", [0.0, .17, .63, 1.0])
def test_mapping_is_identity_at_neutral_and_monotonic_to_both_endpoints(density):
    values = [adjusted_surface_density(density, amount) for amount in (-1, -.4, 0, .4, 1)]
    assert values == sorted(values)
    assert values[0] == 0 and values[2] == density and values[-1] == 1


@pytest.mark.parametrize("value", [None, "bad", float("nan"), float("inf"), float("-inf")])
def test_malformed_overrides_are_neutral(value):
    assert admit_opacity_adjust(value) == 0
    assert resolve_opacity_adjust({"global": {"widget_opacity_adjust": value}}, "widget") == 0


def test_settings_projection_changes_surfaces_without_mutating_authored_maps():
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle("glass", Rgba(4, 8, 12, 100)))
    authored = theme.colors
    project_settings_opacity_adjust(0)
    neutral = theme.color("panel.group.surface")
    text = theme.color("text.primary")
    project_settings_opacity_adjust(-.35)
    clearer = theme.color("panel.group.surface")
    assert clearer.a < neutral.a
    assert (clearer.r, clearer.g, clearer.b) == (neutral.r, neutral.g, neutral.b)
    assert theme.colors["text.primary"] == authored["text.primary"]
    assert theme.colors is authored


def test_normal_settings_surfaces_follow_override_and_cache_only_the_current_projection():
    import ui.settings_theme_spec as spec
    theme = replace(spec.DEFAULT_DARK_SETTINGS_THEME,
                    backdrop=spec.NativeBackdropStyle("off", spec.Rgba(20, 40, 60, 120)),
                    colors={**spec.DEFAULT_DARK_SETTINGS_THEME.colors,
                            "control.button.surface": spec.Rgba(20, 40, 60, 120)})
    authored = theme.color("control.button.surface")
    project_settings_opacity_adjust(-.25)
    clearer = theme.color("control.button.surface")
    assert clearer.a < authored.a
    assert theme.color("control.button.surface") is clearer
    project_settings_opacity_adjust(.25)
    denser = theme.color("control.button.surface")
    assert denser.a > authored.a
    assert theme._surface_projection_cache["control.button.surface"] is denser
    keys = set(theme._surface_projection_cache)
    for amount in (-.62, .13, .71):
        project_settings_opacity_adjust(amount)
        theme.color("control.button.surface")
        assert set(theme._surface_projection_cache) == keys


@pytest.mark.parametrize("scale", [.61, .77, .93])
def test_neutral_stack_calibrates_combined_density_once_without_opaque_ink_compensation(scale, monkeypatch):
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    import ui.settings_surface_composition as composition
    from ui.settings_surface_composition import _density, project_settings_composition
    monkeypatch.setattr(composition, "settings_surface_density",
                        lambda mode, density, **kwargs: density * scale)
    raw = {**DEFAULT_DARK_SETTINGS_THEME.colors,
           "window.dialog_glass": Rgba(12, 25, 38, 37),
           "content.surface": Rgba(12, 25, 38, 0),
           "panel.subsection.surface": Rgba(20, 40, 60, 239),
           "control.list.surface": Rgba(20, 40, 60, 255),
           "text.helper": Rgba(174, 191, 208, 150)}
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, colors=raw,
                    backdrop=NativeBackdropStyle("acrylic", Rgba(12, 25, 38, 162)))
    colors, native = project_settings_composition(theme, 0)
    for stack in (("window.dialog_glass",),
                  ("window.dialog_glass", "content.surface", "panel.subsection.surface"),
                  ("window.dialog_glass", "content.surface", "panel.subsection.surface", "control.list.surface")):
        before = _density(theme.backdrop.native_tint(), raw, stack)
        after = _density(native, colors, stack)
        assert after == pytest.approx(before * scale, abs=2/255)
    assert colors["content.surface"].a == 0
    assert theme.colors["text.helper"] == raw["text.helper"]
    assert colors["text.helper"].a >= raw["text.helper"].a


def test_ink_projection_preserves_rgb_when_alpha_is_sufficient_and_never_adds_surface_density():
    from ui.settings_surface_composition import _correct_ink
    from ui.settings_theme_spec import Rgba
    from ui.theme_semantics import contrast_ratio, composite_over
    ink = Rgba(195, 213, 231, 130)
    surface = Rgba(27, 44, 60)
    result = _correct_ink(ink, [(surface, 4.5)])
    assert (result.r, result.g, result.b) == (ink.r, ink.g, ink.b)
    assert ink.a < result.a <= 255
    assert contrast_ratio(composite_over(result, surface), surface) >= 4.5
    assert contrast_ratio(composite_over(replace(result, a=result.a-1), surface), surface) < 4.5
    impossible = _correct_ink(ink, [(Rgba(0, 0, 0), 4.5), (Rgba(255, 255, 255), 4.5)])
    assert impossible.a == 255


def test_midtone_ink_chooses_the_readable_hue_preserving_direction_on_a_light_surface():
    from ui.settings_surface_composition import _correct_ink
    from ui.settings_theme_spec import Rgba
    from ui.theme_semantics import contrast_ratio
    ink = Rgba(149, 151, 153)
    surface = Rgba(235, 237, 239)
    result = _correct_ink(ink, [(surface, 4.5)])
    assert result.r < ink.r and result.g < ink.g and result.b < ink.b
    assert contrast_ratio(result, surface) >= 4.5
    assert contrast_ratio(Rgba(result.r+1, result.g+1, result.b+1), surface) < 4.5


def test_real_link_button_uses_state_ink_for_checked_text_and_lock_icon_offscreen(qt_app):
    import numpy as np
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QImage, QIcon, QEnterEvent, QPainter
    from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.tabs import shared_styles
    from ui.tabs.themes_tab import _theme_link_icon, _ThemeLinkButton, ThemesTab
    from types import SimpleNamespace
    from ui.theme_semantics import contrast_ratio
    before = get_active_settings_theme()
    theme = replace(DEFAULT_DARK_SETTINGS_THEME,
                    backdrop=NativeBackdropStyle("off", Rgba(10, 20, 30, 40)),
                    colors={**DEFAULT_DARK_SETTINGS_THEME.colors,
                            "control.mode.surface": Rgba(236, 238, 240),
                            "control.mode.checked_surface": Rgba(64, 67, 70),
                            "control.mode.hover_surface": Rgba(80, 84, 88),
                            "control.mode.text": Rgba(30, 32, 34)})
    button = _ThemeLinkButton("Linked")
    button.setCheckable(True)
    button.resize(280, 52)
    try:
        set_active_settings_theme(theme)
        shared_styles.bind_shared_styles(button, "THEME_LINK_BUTTON_STYLE", base_style="")
        # Production hydration deliberately blocks toggle signals.
        owner = SimpleNamespace(settings_keep_synced=button)
        ThemesTab._sync_link_buttons(owner, True)
        assert button.isChecked()
        button.ensurePolished()
        def pixels(*, hover=False):
            frame = QImage(button.size(), QImage.Format.Format_RGBA8888)
            frame.fill(0)
            if hover:
                # A never-shown widget has no real OS pointer hit-test. Draw
                # its actual style option with MouseOver explicitly admitted.
                option = QStyleOptionButton()
                button.initStyleOption(option)
                option.state |= QStyle.StateFlag.State_MouseOver
                painter = QPainter(frame)
                button.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, button)
                painter.end()
            else:
                button.render(frame)
            return np.frombuffer(frame.bits(), np.uint8).reshape(frame.height(), frame.bytesPerLine())[:, :frame.width()*4].reshape(frame.height(), frame.width(), 4).copy()
        on = pixels()
        # A contrast-only assertion could pass against a stale Default style.
        assert np.max(np.abs(on[26, 12, :3].astype(int)-np.array((64, 67, 70)))) <= 1
        button.setText("")
        button.setIcon(QIcon())
        off = pixels()
        changed = np.max(np.abs(on[:, :, :3].astype(int)-off[:, :, :3]), axis=2)
        cores = changed >= .90 * changed.max()
        assert cores.sum() > 20
        worst = min(contrast_ratio(Rgba(*map(int, rgb)), Rgba(*map(int, background)))
                    for rgb, background in zip(on[cores, :3], off[cores, :3]))
        assert worst >= 4.5
        state = theme.mode_state_ink("checked")
        assert contrast_ratio(state, theme.color("control.mode.checked_surface")) >= 4.5
        # The actual geometric lock strokes use that same state-derived colour.
        icon = _theme_link_icon(True).pixmap(32, 32).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        data = np.frombuffer(icon.bits(), np.uint8).reshape(32, icon.bytesPerLine())[:, :128].reshape(32, 32, 4)
        opaque = data[:, :, 3] >= 240
        assert opaque.any()
        assert np.max(np.abs(data[opaque, :3].astype(int)-np.array(state.as_tuple()[:3]))) <= 1
        changed_theme = replace(theme, colors={**theme.colors, "control.mode.checked_surface": Rgba(236, 238, 240)})
        set_active_settings_theme(changed_theme)
        icon = button.icon().pixmap(32, 32).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        data = np.frombuffer(icon.bits(), np.uint8).reshape(32, icon.bytesPerLine())[:, :128].reshape(32, 32, 4)
        opaque = data[:, :, 3] >= 240
        changed_ink = changed_theme.mode_state_ink("checked")
        assert changed_ink.r < state.r
        assert np.max(np.abs(data[opaque, :3].astype(int)-np.array(changed_ink.as_tuple()[:3]))) <= 1
        # Hydrated checked:hover follows checked QSS precedence; unchecked
        # hover must instead use the opposite-polarity hover ink for the lock.
        for checked, expected_state in ((True, "checked"), (False, "hover")):
            ThemesTab._sync_link_buttons(owner, checked)
            button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
            qt_app.sendEvent(button, QEnterEvent(QPointF(20, 20), QPointF(20, 20), QPointF(20, 20)))
            button.setText("")  # Isolate actual icon strokes in the real button render.
            on = pixels(hover=True)
            saved_icon = button.icon()
            button.setIcon(QIcon())
            off = pixels(hover=True)
            delta = np.max(np.abs(on[:, :, :3].astype(int)-off[:, :, :3]), axis=2)
            cores = delta >= .90 * delta.max()
            assert cores.sum() > 5
            contrast_worst = min(contrast_ratio(Rgba(*map(int, rgb)), Rgba(*map(int, bg)))
                                 for rgb, bg in zip(on[cores, :3], off[cores, :3]))
            assert contrast_worst >= 4.5, (checked, expected_state, on[26,12,:3], button._link_icon_key,
                                           np.median(on[cores,:3],axis=0), np.median(off[cores,:3],axis=0))
            expected = changed_theme.mode_state_ink(expected_state)
            # Restore the actual icon removed only for the matched background.
            button.setIcon(saved_icon)
            icon = button.icon().pixmap(32, 32).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            data = np.frombuffer(icon.bits(), np.uint8).reshape(32, icon.bytesPerLine())[:, :128].reshape(32, 32, 4)
            opaque = data[:, :, 3] >= 240
            assert np.max(np.abs(data[opaque, :3].astype(int)-np.array(expected.as_tuple()[:3]))) <= 1
            button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
            qt_app.sendEvent(button, QEvent(QEvent.Type.Leave))
    finally:
        set_active_settings_theme(before)
        button.deleteLater()


def test_normal_neutral_theme_projection_is_authoring_identity():
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle("off", Rgba(10, 20, 30, 40)))
    assert {role: theme.color(role) for role in theme.colors} == dict(theme.colors)


@pytest.mark.parametrize("mode", ["off", "glass", "acrylic", "frosted", "mica", "smoked"])
def test_shared_native_request_and_qt_window_fill_apply_material_tint_exactly_once(mode, monkeypatch, qt_app):
    from types import SimpleNamespace
    from core import platform_paths
    from PySide6.QtGui import QColor
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.theme_semantics import composite_over
    from ui.settings_theme import _build_custom_styles
    from ui.settings_theme_qss import render_qss_rgba255
    from ui.studio.theme import studio_theme
    from tools.godzip_foundry_theme import render_foundry_stylesheet
    from tools.foundry_chrome import apply_native_backdrop
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle(mode, Rgba(43, 99, 147, 137)))
    expected_request = ("off" if mode == "off" else "glass", None)
    assert theme.native_backdrop_request() == expected_request
    window = theme.window_surface()
    assert theme.window_surface() is window
    tint = theme.material_tint()
    for pole in (0, 255):
        desktop = Rgba(pole, pole, pole)
        base = desktop if tint is None else composite_over(tint, desktop)
        expected = composite_over(theme.color("window.dialog_glass"), base)
        actual = composite_over(window, desktop)
        assert max(abs(a-b) for a,b in zip(actual.as_tuple(), expected.as_tuple())) <= 1
    assert render_qss_rgba255(window) in _build_custom_styles(theme)
    assert render_qss_rgba255(window) in render_foundry_stylesheet(theme)
    from tools import visualizer_preset_repair as repair
    monkeypatch.setattr(repair, "resolve_tool_theme", lambda key: SimpleNamespace(theme_id="test-owned", theme=theme))
    class RepairShell:
        def setStyleSheet(self, value): self.qss = value
        def isVisible(self): return False
    repair_shell = RepairShell()
    repair.VisualizerPresetRepairApp._apply_theme(repair_shell)
    assert f"QFrame#presetShell {{ background: {render_qss_rgba255(window)};" in repair_shell.qss
    monkeypatch.setattr(platform_paths, "IS_WINDOWS", True)
    if mode != "off":
        color = QColor(studio_theme(theme)["windowSurface"])
        assert color.getRgb() == window.as_tuple()
    calls = []
    monkeypatch.setattr("core.windows.dwm_blur.apply_backdrop", lambda hwnd, *request: calls.append(request) or request[0] != "off")
    apply_native_backdrop(SimpleNamespace(winId=lambda: 42), SimpleNamespace(theme=theme))
    assert calls == [expected_request]


def test_native_theme_projection_calibrates_density_and_invalidates_with_override():
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    theme = replace(DEFAULT_DARK_SETTINGS_THEME,
                    backdrop=NativeBackdropStyle("mica", Rgba(30, 50, 70, 90)))
    original = theme.backdrop.native_tint()
    projected = theme.material_tint()
    assert 0 < projected.a < original.a
    assert theme.material_tint() is projected
    project_settings_opacity_adjust(.4)
    assert theme.material_tint().a > projected.a
    assert theme.backdrop.native_tint() == original


def test_runtime_projection_rolls_back_when_a_renderer_rejects_the_change(qt_app):
    from core.settings.surface_opacity import settings_opacity_adjust
    from ui.settings_theme_runtime import apply_settings_opacity_adjust, subscribe_settings_theme
    project_settings_opacity_adjust(0)
    seen = []

    def reject(_theme):
        seen.append(settings_opacity_adjust())
        if settings_opacity_adjust() > 0:
            raise RuntimeError("test-owned renderer rejection")

    unsubscribe = subscribe_settings_theme(reject)
    try:
        with pytest.raises(RuntimeError, match="test-owned renderer rejection"):
            apply_settings_opacity_adjust(.4)
        assert settings_opacity_adjust() == 0
        assert seen == [.4, 0]
    finally:
        unsubscribe()


def test_both_style_override_sliders_round_trip_through_the_existing_coalesced_save(qt_app, settings_manager):
    from ui.tabs.widgets_tab import WidgetsTab
    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "defaults"})
    try:
        for target, value in (("settings", -27), ("widget", 42)):
            slider = getattr(tab, f"{target}_opacity_adjust_slider")
            slider.setValue(value)
        tab.flush_pending_changes()
        stored = settings_manager.get("widgets")["global"]
        assert stored["settings_opacity_adjust"] == -.27
        assert stored["widget_opacity_adjust"] == .42
    finally:
        tab.deleteLater()


def test_authoring_payload_and_widget_projection_ignore_runtime_opacity():
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.settings_theme_io import settings_theme_to_payload
    from tools.generate_widget_theme_mirrors import widget_counterpart_for_settings_theme

    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle("acrylic", Rgba(20, 30, 40, 100)))
    project_settings_opacity_adjust(0)
    payload = settings_theme_to_payload(theme)
    before = widget_counterpart_for_settings_theme(theme, settings_theme_id="test-owned-id")
    project_settings_opacity_adjust(.5)
    assert settings_theme_to_payload(theme) == payload
    assert widget_counterpart_for_settings_theme(theme, settings_theme_id="test-owned-id") == before


def test_widget_override_is_projected_at_the_family_style_seam():
    from PySide6.QtGui import QColor
    from rendering.quick.widgets.host import OverlayCardStyle
    from rendering.quick.widgets.surface_material import with_surface_material

    @dataclass(frozen=True)
    class Style:
        card_style: OverlayCardStyle

    style = Style(OverlayCardStyle(background_color=QColor(17, 29, 43, 127)))
    config = {"global": {"surface_material": "normal", "widget_opacity_adjust": -.4}}
    result = with_surface_material(style, config, "clock")
    assert result.card_style.background_color.alphaF() < style.card_style.background_color.alphaF()
    assert result.card_style.border_color == style.card_style.border_color
    config["global"]["surface_material"] = "glass"
    material = with_surface_material(style, config, "clock")
    assert material.card_style.surface_opacity_adjust == -.4
    assert material.card_style.background_color == style.card_style.background_color


def test_both_settings_profiles_admit_new_overrides_through_canonical_defaults():
    from core.settings.default_contract import get_canonical_default, NORMAL_PROFILE, MC_PROFILE
    for profile in (NORMAL_PROFILE, MC_PROFILE):
        for target in ("settings", "widget"):
            value = get_canonical_default(f"widgets.global.{target}_opacity_adjust", profile)
            assert admit_opacity_adjust(value) == value


def test_material_density_override_reaches_the_retained_shader_without_fading_the_card(qt_app):
    import numpy as np
    from PySide6.QtGui import QColor
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs Windows QPA")
    scene = MaterialScene(640, 360)
    try:
        scene.set_wallpaper(PresentationImage("test-owned", "test-owned", (640.0, 360.0), 1.0,
            (640, 360), 640 * 4, bytes((140, 160, 190, 255)) * (640 * 360)))
        card = scene.host.create_widget(object_name="densityCard", model_identity="clock",
            geometry=OverlayWidgetGeometry(170, 100, 300, 160),
            card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77), shadow_enabled=False))
        scene.set_material("glass")
        scene.render(4)
        before = np.asarray(scene.read(), np.int16)
        source = card.item.property("cardSurfaceBackdrop")
        tones = []
        for amount in (-.4, .4):
            card.item.setProperty("cardSurfaceOpacityAdjust", amount)
            scene.render(3)
            frame = np.asarray(scene.read(), np.int16)
            tones.append(float(frame[160:200, 280:360].mean()))
            assert np.array_equal(frame[:50], before[:50])
            assert card.item.opacity() == 1.0
            assert card.item.property("cardSurfaceBackdrop") is source
        assert tones[0] > tones[1] + 3
        card.item.setProperty("cardSurfaceOpacityAdjust", 0)
        scene.render(3)
        assert np.array_equal(np.asarray(scene.read(), np.int16), before)
    finally:
        scene.close()
