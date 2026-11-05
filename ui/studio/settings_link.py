"""Settings -> Studio wiring for spec-built Visualizer modes (mode-neutral).

``VisualizerSettingsStore`` is the Studio's canonical store over the existing
Visualizers Settings owner: it hydrates from the same resolved mode config the
mode body loads, and commits by loading the values into that body and running the
body's own Custom transition and save (``_force_visualizer_preset_to_custom`` then
``_save_settings_now``). No preset JSON or settings map is written directly.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping

from core.logging.logger import get_logger

logger = get_logger(__name__)

def studio_adapter(mode_id: str):
    from ui.studio.registry import create_adapter
    return create_adapter(mode_id)


def has_mode_studio(mode_id: str) -> bool:
    from ui.studio.registry import has_studio
    return has_studio(mode_id)


class VisualizerSettingsStore:
    """CanonicalStore over a VisualizersTab-like Settings owner for one mode."""

    def __init__(self, tab, mode_id: str) -> None:
        self._tab = tab
        self._mode = mode_id

    def _spec(self):
        from core.settings.visualizer_mode_settings import require_mode_settings
        return require_mode_settings(self._mode)

    def snapshot(self) -> dict[str, Any]:
        """The resolved section exactly as the mode body hydrates from it, controls admitted."""
        from core.settings.visualizer_mode_settings import read_control_value
        tab = self._tab
        tab.flush_pending_changes()
        config = dict(tab._prepare_mode_hydration_config(self._mode))
        for control in self._spec().controls:
            default = tab._widget_default("spotify_visualizer", control.key)
            config[control.key] = control.admit(read_control_value(control, config.get, default), default)
        # The mode's technical (audio analysis) values, as Settings' technical controls hold them.
        from ui.tabs.media.technical_controls import collect_per_mode_technical_controls
        collect_per_mode_technical_controls(tab, config, current_mode=self._mode)
        config["scene3d_detail"] = self._scene3d_detail()
        return config

    def _scene3d_detail(self) -> str:
        """The 3D Detail tier the stored 3D Settings resolve for this mode, exactly as the display manager hands it
        to the visualizer's presentation (renderers never read Settings). Not an edited value: a render context."""
        from core.settings.scene3d_quality import read_scene3d_section, resolve_visualizer_tier
        from rendering.quick.bootstrap import last_validated_gpu
        manager = getattr(self._tab, "_settings", None)
        section = read_scene3d_section(manager.get) if manager is not None and hasattr(manager, "get") else None
        return resolve_visualizer_tier(section, self._mode, gpu=last_validated_gpu())

    def commit(self, values: Mapping[str, Any], changed: frozenset[str]) -> dict[str, Any]:
        from ui.tabs.media import framed_camera_editor as fce
        from ui.tabs.media.spec_mode_builder import load_spec_mode_settings
        from core.settings.framed_camera import spec_for_mode
        tab = self._tab
        tab.flush_pending_changes()
        config = dict(values)
        previous = tab._loading
        tab._loading = True
        try:
            load_spec_mode_settings(tab, self._mode, config)   # blocked signals: loading saves nothing
            from ui.tabs.media.technical_controls import load_per_mode_technical_controls
            load_per_mode_technical_controls(tab, config, only_mode=self._mode)
        finally:
            tab._loading = previous
        camera = spec_for_mode(self._mode)
        if camera is not None:
            aimed = {camera.key("turn"), camera.key("tilt")} & set(changed)
            if aimed:
                # Persist the exact previewed orbit through the camera editor's own pose authority.
                pose = getattr(tab, fce.pose_attr(self._mode))
                for key in (camera.key("turn"), camera.key("tilt")):
                    pose[key] = config[key]
                setattr(tab, fce.aim_dirty_attr(self._mode), True)
        tab._force_visualizer_preset_to_custom(self._mode)
        tab._save_settings_now()
        return self.snapshot()

    def presets(self) -> list[str]:
        """Every preset slot of the mode, curated first and Custom last (Settings' own order)."""
        from core.settings.visualizer_presets import get_preset_names
        return list(get_preset_names(self._mode))

    def preset_index(self) -> int:
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        return -1 if slider is None else int(slider.preset_index())

    def select_preset(self, index: int) -> None:
        """Switch exactly as Settings' preset slider does when the user moves it: the same handler applies
        the curated values (snapshotting Custom first) or restores Custom, then saves."""
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is None:
            raise RuntimeError("This mode has no preset slider")
        self._tab.flush_pending_changes()
        slider._slider.setValue(int(index))       # the user path: valueChanged -> preset_changed -> tab handler
        self._tab._save_settings_now()

    def preset_label(self) -> str:
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is None:
            return "Custom"
        from core.settings.visualizer_presets import get_preset_names
        names = get_preset_names(self._mode)
        index = slider.preset_index()
        return names[index] if 0 <= index < len(names) else "Custom"

    def card_extent(self, screen=None) -> tuple[float, float] | None:
        """The live card's CUSTOM world extent, resolved with production's own resolver.

        The card lives on the display the visualizer is routed to, which is usually NOT the screen
        Settings is on (5 Nov: a Settings-screen-only lookup missed the operator's TV card, so the
        Studio fell back to the 420x280 baseline: aperture 1 instead of ~3.6, a 3.6x magnification).
        Every connected screen is tried, the Settings screen first; when no connected screen matches
        (the card's display is off), a single saved display bucket for this mode is still the card."""
        try:
            from PySide6.QtGui import QGuiApplication
            from rendering.custom_layout_contract import (get_screen_signature_aliases, get_widget_layout_variant_payload,
                                                          load_custom_layout_map)
            from rendering.custom_layout_session import normalize_viewport_extent
            from rendering.quick.custom_layout_hydration import resolve_visualizer_custom_entry_for_aliases
            from core.settings.visualizer_mode_registry import get_visualizer_layout_profile
            widgets = self._tab._settings.get("widgets")
            if not isinstance(widgets, dict):
                return None
            screens = [screen] if screen is not None else []
            screens += [self._tab.window().screen(), *QGuiApplication.screens()]
            seen = set()
            for candidate in screens:
                if candidate is None or id(candidate) in seen:
                    continue
                seen.add(id(candidate))
                entry = resolve_visualizer_custom_entry_for_aliases(widgets, get_screen_signature_aliases(candidate),
                                                                    self._mode)
                if entry is not None:
                    extent = normalize_viewport_extent(entry.size_payload.get("viewport_extent"))
                    if extent is not None:
                        return extent
            section = widgets.get("spotify_visualizer", {})
            if not isinstance(section, dict) or str(section.get("position", "")).lower() != "custom":
                return None
            profile = get_visualizer_layout_profile(self._mode)
            displays = load_custom_layout_map(widgets).get("displays", {})
            extents = []
            for bucket in displays.values() if isinstance(displays, dict) else ():
                payload = get_widget_layout_variant_payload(bucket, "spotify_visualizer", profile) \
                    if isinstance(bucket, dict) else None
                if payload is not None:
                    size = payload.get("size_payload", {})
                    extent = normalize_viewport_extent(size.get("viewport_extent")) if isinstance(size, dict) else None
                    if extent is not None:
                        extents.append(extent)
            return extents[0] if len(extents) == 1 else None
        except Exception:
            logger.debug("[STUDIO] No live card extent", exc_info=True)
            return None

    def card_style(self) -> dict | None:
        """The live card chrome production presents with (the display manager's card border rule)."""
        try:
            import math
            from core.settings.default_contract import require_canonical_default
            from widgets.spotify_visualizer.presentation_geometry import VISUALIZER_CARD_CONTENT_INSET
            canonical = float(require_canonical_default("widgets.global.card_border_width_px"))
            widgets = self._tab._settings.get("widgets")
            stored = (widgets.get("global") or {}).get("card_border_width_px") if isinstance(widgets, dict) else None
            try:
                border = float(stored) if stored is not None else canonical
            except (TypeError, ValueError):
                border = canonical
            if not math.isfinite(border):
                border = canonical
            return {"border_width": max(0.0, min(12.0, border)), "content_inset": VISUALIZER_CARD_CONTENT_INSET}
        except Exception:
            logger.debug("[STUDIO] No live card style", exc_info=True)
            return None

    def camera_commit_allowed(self) -> bool:
        """The preset's existing 'Include current camera view' choice governs saving Studio views."""
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        checkbox = getattr(slider, "_include_starting_view", None)
        return bool(checkbox is not None and checkbox.isChecked())

    def include_view(self) -> bool | None:
        """Settings' "Include current camera view when saving" choice (None: the mode has no camera view)."""
        checkbox = getattr(self._tab._get_visualizer_preset_slider(self._mode), "_include_starting_view", None)
        return None if checkbox is None else bool(checkbox.isChecked())

    def set_include_view(self, include: bool) -> None:
        checkbox = getattr(self._tab._get_visualizer_preset_slider(self._mode), "_include_starting_view", None)
        if checkbox is not None:
            checkbox.setChecked(bool(include))

    def move_to_custom(self) -> None:
        """Settings' Move To Custom: copy the current curated preset into Custom and switch to it."""
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is not None and slider.preset_index() != slider.custom_index():
            slider._move_to_custom()
            self._tab._save_settings_now()

    def preset_file_editable(self) -> bool:
        """Settings' Edit Preset availability (a curated preset whose JSON exists on disk)."""
        button = getattr(self._tab._get_visualizer_preset_slider(self._mode), "_edit_btn", None)
        return bool(button is not None and button.isEnabled())

    def edit_preset_file(self) -> None:
        """Settings' Edit Preset: open the curated preset's JSON in the default editor."""
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        action = getattr(slider, "_open_preset_json", None)
        if callable(action):
            action()

    def save_preset_as(self) -> None:
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        action = getattr(slider, "_save_custom_preset_as", None)
        if callable(action):
            action()

    def refresh_settings(self) -> None:
        """Reload the mode body and preset slider from the canonical snapshot (never stale widgets)."""
        from ui.tabs.media.spec_mode_builder import load_spec_mode_settings
        from core.settings.visualizer_presets import resolve_preset_index_from_mapping
        tab = self._tab
        config = tab._prepare_mode_hydration_config(self._mode)
        previous = tab._loading
        tab._loading = True
        try:
            load_spec_mode_settings(tab, self._mode, config)
            slider = tab._get_visualizer_preset_slider(self._mode)
            if slider is not None:
                slider.set_preset_index(resolve_preset_index_from_mapping(self._mode, config))
        finally:
            tab._loading = previous


def _scroll_bar(tab):
    area = getattr(tab, "_scroll_area", None)
    return area.verticalScrollBar() if area is not None else None


def open_mode_studio(tab, mode_id: str, *, adapter=None, surface_factory=None, presence=None):
    """Open (or raise) the single Studio for ``mode_id`` from its Settings owner."""
    from ui.studio.controller import StudioController
    from ui.studio.presence import WindowPresence
    from ui.studio.theme import studio_theme, subscribe_studio_theme
    active = StudioController.active()
    if active is not None:
        active.raise_surface()
        return active
    dialog = tab.window()
    store = VisualizerSettingsStore(tab, mode_id)
    if presence is None:
        bar = _scroll_bar(tab)
        presence = WindowPresence(dialog, capture_view=(lambda: bar.value()) if bar is not None else None,
                                  restore_view=(lambda value: bar.setValue(int(value))) if bar is not None else None,
                                  refresh=store.refresh_settings)
    if surface_factory is None:
        from ui.studio.surface import StudioWindowSurface
        anchor = dialog.frameGeometry()
        surface_factory = lambda controller: StudioWindowSurface(controller, anchor=anchor)  # noqa: E731
    def switcher(target: str):
        """Settings edits one mode page at a time: select that mode's page (the same as its pill),
        then hand the Studio a canonical store for it."""
        tab._select_mode_page(target)
        return studio_adapter(target), VisualizerSettingsStore(tab, target)

    def modes():
        from ui.studio.registry import studio_modes
        enabled = set(getattr(getattr(tab, "_vis_body_host", None), "enabled_modes", ()) or ())
        return tuple((entry.mode_id, entry.title) for entry in studio_modes()
                     if not enabled or entry.mode_id in enabled)

    controller = StudioController(adapter or studio_adapter(mode_id), store, presence, surface_factory,
                                  theme_provider=studio_theme, mode_switcher=switcher, modes=modes)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    unsubscribe = subscribe_studio_theme(
        lambda theme: controller.bridge.set_theme(theme) if controller.bridge is not None else None)

    def finished(*_args) -> None:
        unsubscribe()
        try:
            dialog.destroyed.disconnect(controller.close)
        except (RuntimeError, TypeError, AttributeError):
            pass
        if app is not None:
            try:
                app.aboutToQuit.disconnect(controller.close)
            except (RuntimeError, TypeError):
                pass
        if getattr(tab, "_studio_controller", None) is controller:
            tab._studio_controller = None

    def report(message: str) -> None:
        finished()
        logger.error("[STUDIO] %s", message)
        try:
            from ui.styled_popup import StyledPopup
            StyledPopup(dialog, "Studio Unavailable", f"The Studio could not open.\n{message}",
                        icon_type="error", buttons=[("OK", "ok")]).exec()
        except Exception:
            logger.exception("[STUDIO] Could not show the Studio error")

    controller.closed.connect(finished)
    controller.failed.connect(report)
    try:
        dialog.destroyed.connect(controller.close)
    except (RuntimeError, TypeError, AttributeError):
        pass
    tab._studio_controller = controller
    if app is not None:
        app.aboutToQuit.connect(controller.close)
    controller.open()
    return controller


__all__ = ["VisualizerSettingsStore", "has_mode_studio", "open_mode_studio", "studio_adapter"]
