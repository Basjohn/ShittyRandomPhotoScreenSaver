"""Settings -> Studio wiring for spec-built Visualizer modes (mode-neutral).

``VisualizerSettingsStore`` is the Studio's canonical store over the existing
Visualizers Settings owner: it hydrates from the same resolved mode config the
mode body loads, and commits by loading the values into that body and running the
body's own Custom transition and save (``_force_visualizer_preset_to_custom`` then
``_save_settings_now``). No settings map is written directly; the one preset-file write is the
explicit, confirmed Save To <Preset> (:meth:`VisualizerSettingsStore.save_to_preset`) through the
shape-preserving preset-file owner (``core.settings.visualizer_preset_file``).
"""
from __future__ import annotations

import weakref

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


def live_card_extent(widgets, mode_id: str, screens=()) -> tuple[float, float] | None:
    """The live card's CUSTOM world extent, resolved with production's own resolver.

    The card lives on the display the visualizer is routed to, which is usually NOT the screen
    Settings is on (5 Nov: a Settings-screen-only lookup missed the operator's TV card, so the
    Studio fell back to the 420x280 baseline: aperture 1 instead of ~3.6, a 3.6x magnification).
    ``screens`` are tried first, then every connected screen; when no connected screen matches
    (the card's display is off), a single saved display bucket for this mode is still the card."""
    try:
        from PySide6.QtGui import QGuiApplication
        from rendering.custom_layout_contract import (get_screen_signature_aliases, get_widget_layout_variant_payload,
                                                      load_custom_layout_map)
        from rendering.custom_layout_session import normalize_viewport_extent
        from rendering.quick.custom_layout_hydration import resolve_visualizer_custom_entry_for_aliases
        from core.settings.visualizer_mode_registry import get_visualizer_layout_profile
        if not isinstance(widgets, dict):
            return None
        seen = set()
        for candidate in [*screens, *QGuiApplication.screens()]:
            if candidate is None or id(candidate) in seen:
                continue
            seen.add(id(candidate))
            entry = resolve_visualizer_custom_entry_for_aliases(widgets, get_screen_signature_aliases(candidate),
                                                                mode_id)
            if entry is not None:
                extent = normalize_viewport_extent(entry.size_payload.get("viewport_extent"))
                if extent is not None:
                    return extent
        section = widgets.get("spotify_visualizer", {})
        if not isinstance(section, dict) or str(section.get("position", "")).lower() != "custom":
            return None
        profile = get_visualizer_layout_profile(mode_id)
        displays = load_custom_layout_map(widgets).get("displays", {})
        extents = []
        for bucket in displays.values() if isinstance(displays, dict) else ():
            payload = (get_widget_layout_variant_payload(bucket, "spotify_visualizer", profile)
                           if isinstance(bucket, dict) else None)
            if payload is not None:
                size = payload.get("size_payload", {})
                extent = normalize_viewport_extent(size.get("viewport_extent")) if isinstance(size, dict) else None
                if extent is not None:
                    extents.append(extent)
        return extents[0] if len(extents) == 1 else None
    except Exception:
        logger.debug("[STUDIO] No live card extent", exc_info=True)
        return None


class VisualizerSettingsStore:
    """CanonicalStore over a VisualizersTab-like Settings owner for one mode."""

    def __init__(self, tab, mode_id: str) -> None:
        self._tab = tab
        self._mode = mode_id
        # Save To <Preset>: the curated slot this session's Custom values came from (opened on it, a
        # Studio edit or Move To Custom from it), and the keys edited since. Opened on Custom: unknown.
        self._origin: int | None = None
        self._edited: set[str] = set()
        # Studio edits made on a curated preset are held here, in Settings' widgets, and never saved until the user
        # chooses at the close prompt (or saves them explicitly): Settings stays on the preset (operator, 6 Nov).
        self._draft = False
        self._set_origin(self._curated_index())

    def _curated_index(self) -> int | None:
        lookup = getattr(self._tab, "_get_visualizer_preset_slider", None)
        slider = lookup(self._mode) if callable(lookup) else None
        if slider is None:
            return None
        index = int(slider.preset_index())
        return index if 0 <= index < slider.custom_index() else None

    def _set_origin(self, index: int | None) -> None:
        """A curated slot becomes the new origin (edits start afresh); None keeps the current one."""
        if index is not None:
            self._origin = index
            self._edited = set()

    def _spec(self):
        from core.settings.visualizer_mode_settings import require_mode_settings
        return require_mode_settings(self._mode)

    def snapshot(self) -> dict[str, Any]:
        """The resolved section exactly as the mode body hydrates from it, controls admitted (a held draft: as
        saving it would store it, without saving)."""
        from core.settings.visualizer_mode_settings import read_control_value
        tab = self._tab
        tab.flush_pending_changes()
        config = self._draft_config() if self._draft else dict(tab._prepare_mode_hydration_config(self._mode))
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
        curated = self._curated_index()
        if curated is not None and curated != self._origin:
            self._set_origin(curated)
        self._edited |= set(changed)
        config = dict(values)
        self._load_into_settings(config)
        camera = spec_for_mode(self._mode)
        if camera is not None:
            aimed = {camera.key("turn"), camera.key("tilt")} & set(changed)
            if aimed:
                # Persist the exact previewed orbit through the camera editor's own pose authority.
                pose = getattr(tab, fce.pose_attr(self._mode))
                for key in (camera.key("turn"), camera.key("tilt")):
                    pose[key] = config[key]
                setattr(tab, fce.aim_dirty_attr(self._mode), True)
        if curated is not None:
            # On a curated preset the edit is held, not saved: no automatic switch to Custom.
            self._draft = True
            return self.snapshot()
        tab._force_visualizer_preset_to_custom(self._mode)
        tab._save_settings_now()
        return self.snapshot()

    def _load_into_settings(self, config: Mapping[str, Any]) -> None:
        """Load ``config`` into the mode body, its technical controls and shared families with signals blocked
        (loading saves nothing)."""
        from ui.tabs.media.spec_mode_builder import load_spec_mode_settings
        from ui.tabs.media.technical_controls import load_per_mode_technical_controls
        tab = self._tab
        previous = tab._loading
        tab._loading = True
        try:
            load_spec_mode_settings(tab, self._mode, dict(config))
            load_per_mode_technical_controls(tab, dict(config), only_mode=self._mode)
            self._load_families(config)
        finally:
            tab._loading = previous

    # ------------------------------------------------------------------ the held draft (edits on a curated preset)
    def holds_draft(self) -> bool:
        """Studio edits on a curated preset that nothing has saved yet."""
        return self._draft

    def _draft_config(self) -> dict[str, Any]:
        """The section saving Settings' widgets *would* store, read as Custom (the widgets' own values), without
        writing anything: the held draft exactly as the canonical save would admit it."""
        from copy import deepcopy
        from core.settings.visualizer_presets import apply_preset_to_config, get_custom_preset_index
        from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
        from ui.tabs.widgets_tab_media import save_visualizer_settings
        tab = self._tab
        widgets = tab._settings.get("widgets")
        widgets = deepcopy(widgets) if isinstance(widgets, dict) else {}
        section, _mode, _index = tab._merge_visualizer_section_save(widgets, save_visualizer_settings(tab),
                                                                    hydrated=True)
        section = dict(section)
        section["mode"] = self._mode
        section["mode_activation"] = build_visualizer_mode_activation(tab._vis_body_host.enabled_modes)
        return apply_preset_to_config(self._mode, get_custom_preset_index(self._mode), section)

    def _pending_preset_changes(self):
        """(changes, starting_view) between this session's edited keys and what the origin preset resolves."""
        from core.settings import visualizer_preset_file as preset_file
        from core.settings.visualizer_presets import get_presets
        tab = self._tab
        tab.flush_pending_changes()
        payload = tab.build_visualizer_preset_payload(self._mode)
        changes = preset_file.preset_setting_changes(self._mode, self._origin, payload, self._edited)
        starting_view = None
        if self.include_view() and "starting_view" in payload:
            from core.settings.visualizer_view_orbit import get_visualizer_view_pose_keys
            if self._edited & set(get_visualizer_view_pose_keys(self._mode)) \
                    and payload["starting_view"] != get_presets(self._mode)[self._origin].starting_view:
                starting_view = payload["starting_view"]
        return changes, starting_view

    def discard_draft(self) -> None:
        """Drop the held edits: Settings' widgets go back to the saved preset; nothing is written."""
        from ui.tabs.media import framed_camera_editor as fce
        from core.settings.framed_camera import spec_for_mode
        if not self._draft:
            return
        self._draft = False
        tab = self._tab
        config = tab._prepare_mode_hydration_config(self._mode)
        self._load_into_settings(config)
        camera = spec_for_mode(self._mode)
        if camera is not None:
            pose = getattr(tab, fce.pose_attr(self._mode))
            for key in (camera.key("turn"), camera.key("tilt")):
                if key in config:
                    pose[key] = config[key]
            setattr(tab, fce.aim_dirty_attr(self._mode), False)
        self._edited = set()
        self.refresh_settings()
        logger.info("[STUDIO] draft discarded mode=%s", self._mode)

    def draft_to_custom(self) -> None:
        """Place the held edits in the Custom slot (what every Studio edit on a preset used to do at once)."""
        if not self._draft:
            return
        self._draft = False
        self._tab._force_visualizer_preset_to_custom(self._mode)
        self._tab._save_settings_now()
        logger.info("[STUDIO] draft placed in Custom mode=%s", self._mode)

    def resolve_draft(self, *, interactive: bool = True) -> bool:
        """Settle held edits before the session ends or leaves this preset.

        Interactive: ask with Settings' prompt (Overwrite <Preset>, Save As New Preset, Place In Custom, Discard);
        closing the prompt means "not yet" and the Studio stays. Not interactive (application quit, Settings going
        away, a programmatic close): place them in Custom, so nothing is lost. False only when the user stays."""
        from core.settings import visualizer_preset_file as preset_file
        from core.settings.visualizer_presets import get_preset_file_path, get_preset_names
        if not self._draft:
            return True
        changes, starting_view = self._pending_preset_changes()
        if not changes and starting_view is None:
            self.discard_draft()                    # back where the preset already is: nothing to keep
            return True
        if not interactive:
            self.draft_to_custom()
            return True
        name = get_preset_names(self._mode)[self._origin]
        path = get_preset_file_path(self._mode, self._origin)
        writable = path is not None and preset_file.preset_file_writable(path)
        count = len(changes) + (starting_view is not None)
        plural = "s" if count != 1 else ""
        while True:
            buttons = ([(f"Overwrite {name}", "overwrite")] if writable else []) + [
                ("Save As New Preset", "new"), ("Place In Custom", "custom"), ("Discard", "discard")]
            lines = [f"You changed {count} setting{plural} of {name} in the Studio without saving."]
            if not writable:
                lines.append(f"{name}'s preset file cannot be changed here, so it cannot be overwritten.")
            lines.append("What should happen to these changes?")
            answer = self._popup("Unsaved Preset Changes", "\n".join(lines), "question", buttons=buttons,
                                 default_button_index=len(buttons) - 2)
            if answer is None:
                return False
            if answer == "discard":
                self.discard_draft()
                return True
            if answer == "custom":
                self.draft_to_custom()
                return True
            if answer == "overwrite":
                if self._write_preset(changes, starting_view):
                    return True
                writable = False                    # it could not be written after all: ask again without it
                continue
            if answer == "new" and self.save_as_new_preset():
                return True

    def _write_preset(self, changes, starting_view) -> bool:
        """Write the session's changes into the origin preset's own file (shape preserved, nothing else touched),
        reload the presets and settle the draft. Failures are shown with Settings' prompt."""
        from core.settings import visualizer_preset_file as preset_file
        from core.settings.visualizer_presets import get_preset_names
        name = get_preset_names(self._mode)[self._origin]
        try:
            result = preset_file.save_changes_to_preset(self._mode, self._origin, changes,
                                                        starting_view=starting_view)
        except preset_file.PresetFileReadOnly as exc:
            self._popup("Preset Is Read-Only", self._read_only_text(exc.path), "error")
            return False
        except Exception as exc:
            logger.exception("[STUDIO] Save To %s failed", name)
            self._popup("Save Failed", f"Could not save into {name}.\n{exc}", "error")
            return False
        logger.info("[STUDIO] saved to preset mode=%s index=%d path=%s keys=%s",
                    self._mode, self._origin, result.path, ",".join(result.changed))
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is not None:
            slider.refresh_preset_catalog(reload=False)    # the owner reloaded it; the slot stays as it is
        self._draft = False
        self._edited = set()
        return True

    def save_as_new_preset(self) -> bool:
        """Settings' own Save Preset As (its file dialog, into the presets folder); the new preset is then selected,
        so Settings ends on it. False when the dialog was cancelled or the write failed."""
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        action = getattr(slider, "_save_custom_preset_as", None)
        if not callable(action):
            return False
        index = action(select_saved=True)
        if index is None:
            return False
        self._draft = False
        self._set_origin(index)
        self._tab.flush_pending_changes()       # the selection is on disk before Settings is refreshed from it
        self._tab._save_settings_now()
        return True

    def _load_families(self, config: Mapping[str, Any]) -> None:
        """The mode's shared setting families Settings keeps outside the mode body (shown on its page, stored per
        mode): the bar Fill / Border / Border Opacity rows and the rainbow toggle and speed, loaded into their
        owning Settings widgets so the tab's own save collects them. A mode owning neither is a no-op."""
        from PySide6.QtCore import QSignalBlocker
        from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
        tab = self._tab
        shared = get_owned_mode_setting_keys(self._mode, "shared_bar")
        if shared and all(key in config for key in shared.values()) and hasattr(tab, "vis_border_opacity"):
            from ui.tabs.widgets_tab_media import load_shared_visualizer_appearance_settings
            blocker = QSignalBlocker(tab.vis_border_opacity)
            try:
                load_shared_visualizer_appearance_settings(tab, dict(config), self._mode)
            finally:
                del blocker
        rainbow = get_owned_mode_setting_keys(self._mode, "rainbow")
        enabled_key, speed_key = rainbow.get("rainbow_enabled"), rainbow.get("rainbow_speed")
        if enabled_key in config and speed_key in config and hasattr(tab, "rainbow_enabled"):
            enabled = bool(config[enabled_key])
            speed = max(1, min(100, int(round(float(config[speed_key]) * 100.0))))
            cache = dict(getattr(tab, "_rainbow_per_mode", {}) or {})
            cache[self._mode] = (enabled, speed)
            tab._rainbow_per_mode = cache
            blockers = [QSignalBlocker(tab.rainbow_enabled)]
            slider = getattr(tab, "rainbow_speed_slider", None)
            if slider is not None:
                blockers.append(QSignalBlocker(slider))
            try:
                tab.rainbow_enabled.setChecked(enabled)
                if slider is not None:
                    slider.setValue(speed)
                label = getattr(tab, "rainbow_speed_label", None)
                if label is not None:
                    label.setText(f"{speed / 100.0:.2f}")
            finally:
                del blockers
            refresh = getattr(tab, "_update_rainbow_visibility", None)
            if callable(refresh):
                refresh()

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
        # Viewing a curated preset is a new starting point; returning to Custom keeps where it came from.
        self._set_origin(self._curated_index())

    def preset_label(self) -> str:
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is None:
            return "Custom"
        from core.settings.visualizer_presets import get_preset_names
        names = get_preset_names(self._mode)
        index = slider.preset_index()
        return names[index] if 0 <= index < len(names) else "Custom"

    def card_extent(self, screen=None) -> tuple[float, float] | None:
        """The live card's CUSTOM world extent (see :func:`live_card_extent`)."""
        try:
            widgets = self._tab._settings.get("widgets")
        except Exception:
            return None
        screens = [screen] if screen is not None else []
        try:
            screens.append(self._tab.window().screen())
        except Exception:
            pass
        return live_card_extent(widgets, self._mode, screens)

    def environment_image(self):
        """What a reflecting mode mirrors: the saver's first source image (``ui.studio.environment``)."""
        from ui.studio.environment import environment_image
        try:
            folders = self._tab._settings.get("sources.folders") or []
        except Exception:
            folders = []
        return environment_image(folders if isinstance(folders, (list, tuple)) else [folders])

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
            if self._draft:
                self.draft_to_custom()          # the held edits are what moves into Custom
                return
            self._set_origin(self._curated_index())
            slider._move_to_custom()
            self._tab._save_settings_now()

    def save_target_label(self) -> str:
        """The curated preset Save To <Preset> writes into ("": not offered). Offered while this session holds
        unsaved edits of a curated preset, and on Custom when this session's Custom values came from a curated
        preset; only when that preset's file exists."""
        from core.settings.visualizer_presets import get_preset_file_path, get_preset_names
        slider = self._tab._get_visualizer_preset_slider(self._mode)
        if slider is None or self._origin is None:
            return ""
        if not self._draft and slider.preset_index() != slider.custom_index():
            return ""
        names = get_preset_names(self._mode)
        if not 0 <= self._origin < len(names) - 1 or get_preset_file_path(self._mode, self._origin) is None:
            return ""
        return names[self._origin]

    def save_to_preset(self) -> str:
        """Save To <Preset>: after an explicit confirmation, write the settings edited in this session that
        differ from the origin curated preset into that preset's own file (shape preserved, nothing else
        touched), then reload the presets. Returns a notice for the Studio ("" when nothing was done)."""
        from core.settings import visualizer_preset_file as preset_file
        from core.settings.visualizer_presets import get_preset_file_path
        name = self.save_target_label()
        if not name:
            return ""
        changes, starting_view = self._pending_preset_changes()
        if not changes and starting_view is None:
            return f"{name} already holds these settings"
        path = get_preset_file_path(self._mode, self._origin)
        if path is None:
            return ""
        if not preset_file.preset_file_writable(path):
            self._popup("Preset Is Read-Only", self._read_only_text(path), "error")
            return ""
        count = len(changes) + (starting_view is not None)
        plural = "s" if count != 1 else ""
        answer = self._popup(
            f"Save To {name}",
            f"Write {count} changed setting{plural} into {name}'s preset file?\n{path}\n"
            "Everything else in the file stays exactly as it is.",
            "question", buttons=[("Save", "save"), ("Cancel", "cancel")], default_button_index=1)
        if answer != "save" or not self._write_preset(changes, starting_view):
            return ""
        return f"Saved {count} setting{plural} into {name}"

    @staticmethod
    def _read_only_text(path) -> str:
        return (f"This preset's file cannot be changed here:\n{path}\n"
                "Use Save Preset As… to keep these settings as a new preset.")

    def _popup(self, title: str, message: str, icon: str, *, buttons=(("OK", "ok"),),
               default_button_index: int = 0) -> str | None:
        """Settings' own prompt (it stays on top of the Studio); returns the chosen button's value."""
        from ui.styled_popup import StyledPopup
        popup = StyledPopup(self._tab, title, message, icon_type=icon, buttons=list(buttons),
                            default_button_index=default_button_index)
        popup.exec()
        return popup.result_value

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
    # Everything below outlives the session's own references (theme listeners, and slots Qt holds strongly on the
    # controller's own signals), so it holds the controller weakly: a strong closure over it is a cycle through Qt
    # connections that the garbage collector cannot see, and kept every closed Studio alive for the process.
    session = weakref.ref(controller)

    def set_theme(theme) -> None:
        current = session()
        if current is not None and current.bridge is not None:
            current.bridge.set_theme(theme)
    unsubscribe = subscribe_studio_theme(set_theme)

    def finished(*_args) -> None:
        unsubscribe()
        current = session()
        if current is None:
            return
        try:
            dialog.destroyed.disconnect(current.close_for_settings_gone)
        except (RuntimeError, TypeError, AttributeError):
            pass
        if app is not None:
            try:
                app.aboutToQuit.disconnect(current.close_for_quit)
            except (RuntimeError, TypeError):
                pass
        if getattr(tab, "_studio_controller", None) is current:
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
        dialog.destroyed.connect(controller.close_for_settings_gone)
    except (RuntimeError, TypeError, AttributeError):
        pass
    tab._studio_controller = controller
    if app is not None:
        app.aboutToQuit.connect(controller.close_for_quit)
    controller.open()
    return controller


__all__ = ["VisualizerSettingsStore", "has_mode_studio", "open_mode_studio", "studio_adapter"]
