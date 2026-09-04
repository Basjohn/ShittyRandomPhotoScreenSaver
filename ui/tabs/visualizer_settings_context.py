"""Reusable Settings-side context for Visualizer controls.

V7a extracts the Visualizer-specific owner surface from ``WidgetsTab`` without
moving any presentation.  Both the existing Widgets host and the upcoming
top-level Visualizers tab can own the same builders, preset logic, lazy-body
host and persistence semantics without inheriting the unrelated Widgets UI.

This mixin deliberately does not own runtime Visualizer state or Media
activation.  A concrete Settings tab supplies ``_settings``,
``_widget_section_descriptors``, save scheduling hooks and its scroll area.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    get_preset_slider_attr,
)
from core.settings.visualizer_presets import (
    GLOBAL_ALLOWED_KEYS,
    MODE_KEY_PREFIXES,
    VISUALIZER_CUSTOM_STORAGE_KEY,
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    extract_visualizer_snapshot,
    get_custom_preset_index,
    restore_visualizer_snapshot,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_settings_contract import strip_legacy_global_technical_keys
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_mode_payload,
    normalize_visualizer_section_mapping,
)
from rendering.widget_descriptors import (
    collect_widget_section_save_result,
    load_widget_section,
)
from ui.tabs.media.technical_controls import load_per_mode_technical_controls

logger = get_logger(__name__)

DEFAULT_VISUALIZER_MODE = get_default_visualizer_mode_id()
_DEPRECATED_VISUALIZER_EXPORT_SUFFIXES = ("energy_boost", "use_raw_energy")
_VISUALIZER_ADVANCED_ROOT_ATTRS = {
    "spectrum": ("_spectrum_advanced",),
    "oscilloscope": ("_osc_advanced",),
    "sine_wave": ("_sine_advanced", "_sine_advanced_host"),
    "bubble": ("_bubble_advanced",),
    "devcurve": ("_devcurve_normal", "_devcurve_advanced", "_devcurve_advanced_host"),
    "sphere": ("_sphere_normal", "_sphere_advanced", "_sphere_advanced_host"),
}


class VisualizerSettingsContextMixin:
    """Shared QWidget-side owner contract for Visualizer Settings presentation."""

    _ADV_STATE_KEY = "ui.visualizer_adv_states"
    _TECH_STATE_KEY = "ui.visualizer_tech_states"
    _TECH_BUCKET_STATE_KEY = "ui.visualizer_tech_bucket_states"
    _BUCKET_STATE_KEY = "ui.visualizer_bucket_states"
    _SCROLL_POS_KEY = "ui.visualizer_scroll_positions"

    _RAINBOW_COLORS = [
        "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
        "#0000FF", "#4B0082", "#8F00FF",
    ]

    def _initialize_visualizer_settings_context_state(self) -> None:
        """Initialize only Visualizer Settings UI state from the shared authority."""
        self._visualizer_adv_state = self._load_adv_states()
        self._visualizer_tech_state = self._load_tech_states()
        self._visualizer_tech_bucket_state = self._load_tech_bucket_states()
        self._visualizer_bucket_state = self._load_bucket_states()

    def _widget_default(self, section: str, key: str, fallback: Any) -> Any:
        """Fetch a default value for a widget section/key combo."""
        section_defaults = self._widget_defaults.get(section, {})
        if isinstance(section_defaults, dict) and key in section_defaults:
            return section_defaults[key]
        return fallback

    def _color_from_default(self, section: str, key: str, fallback: list[int]) -> QColor:
        """Return a QColor built from canonical defaults with fallback."""
        value = self._widget_default(section, key, fallback)
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return QColor(*value)
        except Exception:
            logger.debug("[WIDGETS_TAB] Invalid color default for %s.%s", section, key, exc_info=True)
        return QColor(*fallback)

    def _default_int(self, section: str, key: str, fallback: int) -> int:
        """Return widget default coerced to int."""
        value = self._widget_default(section, key, fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    def _default_float(self, section: str, key: str, fallback: float) -> float:
        """Return widget default coerced to float."""
        value = self._widget_default(section, key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    def _default_bool(self, section: str, key: str, fallback: bool) -> bool:
        """Return widget default coerced to bool via SettingsManager helper."""
        value = self._widget_default(section, key, fallback)
        return SettingsManager.to_bool(value, fallback)

    def _default_str(self, section: str, key: str, fallback: str) -> str:
        """Return widget default coerced to string."""
        value = self._widget_default(section, key, fallback)
        if value is None:
            return fallback
        return str(value)

    def _config_bool(self, section: str, config: Mapping[str, Any], key: str, fallback: bool) -> bool:
        default = self._default_bool(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        return SettingsManager.to_bool(raw, default)

    def _config_int(self, section: str, config: Mapping[str, Any], key: str, fallback: int) -> int:
        default = self._default_int(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _config_float(self, section: str, config: Mapping[str, Any], key: str, fallback: float) -> float:
        default = self._default_float(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    def _config_str(self, section: str, config: Mapping[str, Any], key: str, fallback: str) -> str:
        default = self._default_str(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        if raw is None:
            return default
        return str(raw)

    def _merge_visualizer_section_save(
        self,
        existing_widgets: dict[str, Any],
        section_result: Mapping[str, Any] | None,
        *,
        hydrated: bool,
    ) -> tuple[dict[str, Any], str, int]:
        """Merge one Settings-side Visualizer save into the persisted widgets map.

        The Visualizer saver intentionally emits shared + active-mode keys only.
        This method owns the special merge/normalization and Custom snapshot
        transaction so a future top-level Visualizers tab can persist exactly the
        same section without invoking a whole-Widgets save.  An unhydrated/lazy
        owner leaves the stored Visualizer mapping byte-for-byte semantic state
        alone (no normalization or fallback synthesis).
        """
        existing_vis = existing_widgets.get("spotify_visualizer", {})
        if not isinstance(existing_vis, dict):
            existing_vis = {}

        if hydrated:
            if isinstance(section_result, Mapping):
                existing_vis.update(dict(section_result))
            spotify_vis_config = normalize_visualizer_section_mapping(
                existing_vis,
                apply_preset_overlay=False,
            )
            existing_widgets["spotify_visualizer"] = spotify_vis_config
        else:
            spotify_vis_config = dict(existing_vis)

        current_vis_mode = str(
            spotify_vis_config.get("mode", DEFAULT_VISUALIZER_MODE)
            or DEFAULT_VISUALIZER_MODE
        )
        current_preset_index = self._resolve_visualizer_preset_index(
            current_vis_mode, spotify_vis_config
        )
        current_custom_index = get_custom_preset_index(current_vis_mode)
        if hydrated and current_preset_index == current_custom_index:
            snapshot = self._extract_visualizer_snapshot(
                current_vis_mode, spotify_vis_config
            )
            cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
            if not isinstance(cache, dict):
                cache = {}
            cache[current_vis_mode] = snapshot
            self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

        return spotify_vis_config, current_vis_mode, current_preset_index

    def _load_adv_states(self) -> Dict[str, bool]:
        """Load persisted advanced toggle states from SettingsManager."""
        raw = self._settings.get(self._ADV_STATE_KEY, {})
        if isinstance(raw, dict):
            return {k: bool(v) for k, v in raw.items()}
        return {}

    def _load_tech_states(self) -> Dict[str, bool]:
        """Load persisted Technical bucket toggle states from SettingsManager."""
        raw = self._settings.get(self._TECH_STATE_KEY, {})
        if isinstance(raw, dict):
            return {k: bool(v) for k, v in raw.items()}
        return {}

    def _load_tech_bucket_states(self) -> Dict[str, bool]:
        """Load persisted per-mode Technical subsection visibility states."""
        raw = self._settings.get(self._TECH_BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def _load_bucket_states(self) -> Dict[str, bool]:
        """Load persisted per-mode visualizer bucket states."""
        raw = self._settings.get(self._BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def get_visualizer_adv_state(self, mode: str) -> bool:
        """Return remembered expanded state for a visualizer mode."""
        return bool(self._visualizer_adv_state.get(mode, False))

    def set_visualizer_adv_state(self, mode: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a visualizer mode."""
        self._visualizer_adv_state[mode] = bool(expanded)
        try:
            self._settings.set(self._ADV_STATE_KEY, dict(self._visualizer_adv_state))
        except Exception:
            pass

    def get_visualizer_tech_state(self, mode: str) -> bool:
        """Return remembered Technical bucket state for a visualizer mode."""
        return bool(self._visualizer_tech_state.get(mode, True))

    def set_visualizer_tech_state(self, mode: str, expanded: bool) -> None:
        """Persist Technical bucket expanded/collapsed state for a visualizer mode."""
        self._visualizer_tech_state[mode] = bool(expanded)
        try:
            self._settings.set(self._TECH_STATE_KEY, dict(self._visualizer_tech_state))
        except Exception:
            pass

    def get_visualizer_tech_bucket_state(self, mode: str, bucket: str, default: bool = True) -> bool:
        """Return remembered visibility state for a per-mode Technical subsection."""
        states = getattr(self, "_visualizer_tech_bucket_state", {})
        key = f"{mode}:{bucket}"
        return bool(states.get(key, default))

    def set_visualizer_tech_bucket_state(self, mode: str, bucket: str, visible: bool) -> None:
        """Persist visibility state for a per-mode Technical subsection."""
        states = getattr(self, "_visualizer_tech_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._visualizer_tech_bucket_state = states
        states[f"{mode}:{bucket}"] = bool(visible)
        try:
            self._settings.set(self._TECH_BUCKET_STATE_KEY, dict(states))
        except Exception:
            pass

    def get_visualizer_bucket_state(self, mode: str, bucket: str, default: bool = False) -> bool:
        """Return remembered expanded state for a visualizer bucket."""
        states = getattr(self, "_visualizer_bucket_state", {})
        key = f"{mode}:{bucket}"
        return bool(states.get(key, default))

    def set_visualizer_bucket_state(self, mode: str, bucket: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a visualizer bucket."""
        states = getattr(self, "_visualizer_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._visualizer_bucket_state = states
        states[f"{mode}:{bucket}"] = bool(expanded)
        try:
            self._settings.set(self._BUCKET_STATE_KEY, dict(states))
        except Exception:
            pass

    def save_scroll_position(self, mode: str) -> None:
        """Save current scroll position for a visualizer mode."""
        sa = getattr(self, '_scroll_area', None)
        if sa is None:
            return
        vbar = sa.verticalScrollBar()
        if vbar is None:
            return
        positions = self._settings.get(self._SCROLL_POS_KEY, {})
        if not isinstance(positions, dict):
            positions = {}
        positions[mode] = vbar.value()
        try:
            self._settings.set(self._SCROLL_POS_KEY, positions)
        except Exception:
            pass

    def restore_scroll_position(self, mode: str) -> None:
        """Restore saved scroll position for a visualizer mode."""
        sa = getattr(self, '_scroll_area', None)
        if sa is None:
            return
        vbar = sa.verticalScrollBar()
        if vbar is None:
            return
        positions = self._settings.get(self._SCROLL_POS_KEY, {})
        if isinstance(positions, dict) and mode in positions:
            try:
                pos = int(positions[mode])

                def _restore() -> None:
                    vbar.setValue(pos)

                self._schedule_owned_single_shot(0, _restore)
            except Exception:
                pass

    def _snapshot_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> None:
        live_config = self._build_current_spotify_visualizer_config(spotify_vis_config)
        snapshot = build_normalized_custom_snapshot(mode_key, live_config)
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        if not isinstance(cache, dict):
            cache = {}
        cache[mode_key] = snapshot
        self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

    def _restore_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> bool:
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        if not isinstance(cache, dict):
            return False
        payload = cache.get(mode_key)
        if not isinstance(payload, dict):
            return False
        return restore_visualizer_snapshot(mode_key, spotify_vis_config, payload)

    def _extract_visualizer_snapshot(self, mode_key: str, spotify_vis_config: dict) -> dict:
        return extract_visualizer_snapshot(mode_key, spotify_vis_config)

    def build_visualizer_preset_payload(self, mode_key: str) -> dict[str, Any]:
        """Construct a lean curated-preset payload from current settings."""
        widgets_cfg = self._settings.get('widgets', {})
        if not isinstance(widgets_cfg, dict):
            return {}
        spotify_vis_config = widgets_cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_vis_config, dict):
            return {}

        live_config = self._build_current_spotify_visualizer_config(spotify_vis_config)
        normalized_live = normalize_visualizer_section_mapping(
            live_config,
            apply_preset_overlay=False,
        )
        snapshot = self._extract_visualizer_snapshot(mode_key, normalized_live)

        # DEBUG: Log what keys are in the snapshot before filtering
        logger.debug("[VIS_PRESETS_SAVE] Before filtering for %s: %d keys", mode_key, len(snapshot))

        snapshot = normalize_visualizer_mode_payload(mode_key, snapshot)

        # DEBUG: Log what keys remain after filtering
        logger.debug("[VIS_PRESETS_SAVE] After filtering for %s: %d keys - %s", 
                     mode_key, len(snapshot), list(snapshot.keys())[:10])
        prefixes = MODE_KEY_PREFIXES.get(mode_key, [])
        for prefix in prefixes:
            for suffix in _DEPRECATED_VISUALIZER_EXPORT_SUFFIXES:
                snapshot.pop(f"{prefix}{suffix}", None)
        if not snapshot:
            return {}

        preset_index = self._resolve_visualizer_preset_index(mode_key, normalized_live)
        snapshot_copy = deepcopy(snapshot)

        payload: dict[str, Any] = {
            "mode": mode_key,
            "name": f"Custom {mode_key.title()} Preset",
            "preset_index": preset_index,
            "visualizer_preset_override": True,
            "visualizer_preset_mode": mode_key,
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": snapshot_copy,
                },
            },
        }
        return payload

    @staticmethod
    def _is_key_for_mode(key: str, prefixes: list[str]) -> bool:
        if not prefixes:
            return False
        return any(key.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _is_global_visualizer_key(key: str) -> bool:
        if key in GLOBAL_ALLOWED_KEYS:
            return True
        return key in {
            'mode',
            'enabled',
            'visualizers_enabled',
            'monitor',
            'bar_count',
            'ghosting_enabled',
            'ghost_alpha',
            'ghost_decay',
            'rainbow_enabled',
            'rainbow_speed',
        }

    def _build_current_spotify_visualizer_config(
        self,
        base_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a live spotify_visualizer config built from current UI state.

        This preserves any unrelated stored keys while overlaying the current
        widget state exactly as save_visualizer_settings would serialize it.
        """
        config: dict[str, Any] = {}
        if isinstance(base_config, Mapping):
            config.update(strip_legacy_global_technical_keys(deepcopy(dict(base_config))))

        # This helper is used by stack-status/live-preview paths before every
        # lazy-built Media/Visualizer control necessarily exists. In that case,
        # preserve the stored visualizer config instead of logging a misleading
        # preset/runtime failure.
        required_attrs = (
            'vis_enabled_checkbox',
        )
        if any(getattr(self, attr, None) is None for attr in required_attrs):
            return config

        try:
            save_result = collect_widget_section_save_result(
                self,
                "visualizers",
                descriptors=self._widget_section_descriptors,
            )
            if not isinstance(save_result, dict):
                return config
            config.update(deepcopy(save_result))
        except Exception:
            logger.debug("[WIDGETS_TAB] Failed to build live visualizer config", exc_info=True)

        return config

    def cycle_visualizer_preset(self, mode_key: str, direction: int) -> None:
        """Cycle the preset slider for *mode_key* by *direction* (+1/-1)."""
        if not direction:
            return
        slider = self._get_visualizer_preset_slider(mode_key)
        if slider is None:
            return
        if direction > 0:
            slider.cycle_next()
        else:
            slider.cycle_previous()

    def _get_active_visualizer_mode(self) -> str:
        """Return the Settings-active visualizer mode from canonical context state.

        V7 removes the old hidden/visible combo as a selection authority.  The
        top-level Visualizers tab's mode pills update this state directly; the
        runtime/persisted ``mode`` field remains the sole durable authority.
        """
        mode = getattr(self, "_active_visualizer_mode_id", None)
        if isinstance(mode, str) and mode:
            return mode
        return DEFAULT_VISUALIZER_MODE

    def _get_visualizer_preset_slider(self, mode: str):
        """Return the preset slider widget for *mode* using the shared registry."""
        try:
            slider_attr = get_preset_slider_attr(str(mode))
        except Exception:
            return None
        return getattr(self, slider_attr, None)

    def _get_visualizer_advanced_roots(self, mode: str) -> list[QWidget]:
        """Return advanced container roots for *mode*."""
        roots: list[QWidget] = []
        for attr in _VISUALIZER_ADVANCED_ROOT_ATTRS.get(mode, ()):
            root = getattr(self, attr, None)
            if isinstance(root, QWidget):
                roots.append(root)
        return roots

    @staticmethod
    def _resolve_visualizer_preset_index(mode: str, config: Mapping[str, Any] | None) -> int:
        """Resolve a mode preset index through the shared visualizer preset contract."""
        return resolve_preset_index_from_mapping(mode, config)

    def _auto_switch_preset_to_custom(self) -> None:
        """Auto-switch to Custom preset when a visualizer-specific setting changes.

        Only fires when:
        1. The change did NOT come from the preset slider itself.
        2. We are not programmatically loading settings (_loading guard).
        3. The sender widget is a descendant of the current mode's advanced
           container (so clock/weather/etc. changes never trigger this).
        4. The current preset is NOT already Custom.
        """
        if getattr(self, '_preset_slider_changing', False):
            return
        if getattr(self, '_loading', False):
            return

        # Identify the sender and the current mode's advanced container.
        mode = self._get_active_visualizer_mode()
        adv_roots = self._get_visualizer_advanced_roots(mode)
        slider = self._get_visualizer_preset_slider(mode)
        if not adv_roots or slider is None:
            return

        # If already on Custom, nothing to switch.
        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else slider.preset_index()
        if slider.preset_index() == custom_index:
            return

        # Check sender is inside the advanced container
        try:
            sender = self.sender()
        except Exception:
            sender = None

        # Sender-less saves happen during preset application and other
        # programmatic flows. They must never be treated as "advanced edit"
        # signals or we will silently force curated presets back to Custom.
        if sender is None:
            return

        w = sender
        inside_adv = False
        while w is not None:
            if any(w is root for root in adv_roots):
                inside_adv = True
                break
            w = w.parent()
        if not inside_adv:
            return

        slider.set_preset_index(custom_index)

    def _force_visualizer_preset_to_custom(self, mode: str | None = None) -> None:
        """Switch the active visualizer preset to Custom without relying on sender ancestry."""
        if getattr(self, '_preset_slider_changing', False):
            return
        if getattr(self, '_loading', False):
            return

        if mode is None:
            mode = self._get_active_visualizer_mode()

        slider = self._get_visualizer_preset_slider(mode)
        if slider is None:
            return

        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else slider.preset_index()
        if slider.preset_index() == custom_index:
            return
        slider.set_preset_index(custom_index)

    def _on_visualizer_preset_changed(self, mode_key: str, preset_index: int) -> None:
        """Handle preset slider changes by applying curated settings before save."""
        if getattr(self, '_loading', False):
            return

        slider = self._get_visualizer_preset_slider(mode_key)
        if slider is None:
            return

        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else get_custom_preset_index(mode_key)

        widgets_cfg = self._settings.get('widgets', {}) or {}
        spotify_vis_config = widgets_cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_vis_config, dict):
            spotify_vis_config = {}

        prev_index = self._resolve_visualizer_preset_index(mode_key, spotify_vis_config)
        move_to_custom_pending = bool(getattr(slider, "_pending_move_to_custom", False))

        if preset_index == custom_index:
            restored = False
            if move_to_custom_pending:
                self._snapshot_custom_visualizer_mode(mode_key, spotify_vis_config)
                try:
                    setattr(slider, "_pending_move_to_custom", False)
                except Exception:
                    pass
            else:
                restored = self._restore_custom_visualizer_mode(mode_key, spotify_vis_config)
            spotify_vis_config[f"preset_{mode_key}"] = custom_index
            if restored:
                self._loading = True
                try:
                    full_widgets = dict(widgets_cfg)
                    full_widgets['spotify_visualizer'] = dict(spotify_vis_config)
                    load_widget_section(
                        self,
                        "visualizers",
                        full_widgets,
                        descriptors=self._widget_section_descriptors,
                    )
                    load_per_mode_technical_controls(self, spotify_vis_config)
                finally:
                    self._loading = False
            if move_to_custom_pending:
                self._save_settings_now()
            else:
                self._save_settings()
            self._update_rainbow_visibility()
            return

        if move_to_custom_pending:
            try:
                setattr(slider, "_pending_move_to_custom", False)
            except Exception:
                pass

        if prev_index == custom_index:
            self._snapshot_custom_visualizer_mode(mode_key, spotify_vis_config)

        working_config = dict(spotify_vis_config)
        working_config['mode'] = mode_key
        applied = apply_preset_to_config(mode_key, preset_index, working_config)
        # Use REPLACE semantics so stale mode-specific keys do not survive a
        # preset switch when the target payload intentionally omits them.
        restore_visualizer_snapshot(mode_key, spotify_vis_config, applied)
        spotify_vis_config[f"preset_{mode_key}"] = preset_index

        # Push preset values into UI widgets so the debounced save reads
        # the correct (preset) values instead of stale widget state.
        # Pass full widgets dict (with media intact) so load_media_settings
        # doesn't reset unrelated widgets to defaults.
        if applied != working_config:
            full_widgets = dict(widgets_cfg)
            # Pass the full spotify_vis_config (with all global keys) so the
            # media loader doesn't drop unrelated settings when the preset
            # only overrides a per-mode subset.
            full_widgets['spotify_visualizer'] = dict(spotify_vis_config)
            self._loading = True
            try:
                load_widget_section(
                    self,
                    "visualizers",
                    full_widgets,
                    descriptors=self._widget_section_descriptors,
                )
                load_per_mode_technical_controls(self, spotify_vis_config)
            finally:
                self._loading = False

        self._save_settings()
        self._update_rainbow_visibility()

    def _active_visualizer_preset_is_custom(self) -> bool:
        mode = self._get_active_visualizer_mode()
        slider = self._get_visualizer_preset_slider(mode)
        if slider is None:
            return True
        try:
            return slider.preset_index() == slider.custom_index()
        except Exception:
            return True

    def _update_vis_mode_sections(self) -> None:
        """Show/hide per-mode settings containers based on selected visualizer type."""
        try:
            mode = self._get_active_visualizer_mode()
        except Exception:
            mode = DEFAULT_VISUALIZER_MODE

        # V7: construct + hydrate the selected mode's lazy body once before
        # toggling visibility. Every mode, including Spectrum, follows the same
        # cached-body contract, so unsaved edits are never re-hydrated on a normal
        # reselect and unbuilt modes stay dormant until selected. A construction
        # failure is deliberately NOT swallowed — it must stay visible/actionable.
        from ui.tabs.widgets_tab_media import (
            _VIS_MODE_CONTAINER_ATTR,
            ensure_visualizer_mode_body,
        )

        ensure_visualizer_mode_body(self, mode)

        # Save scroll position for the previous mode before switching
        prev_mode = getattr(self, '_last_vis_mode_section', None)
        if prev_mode and prev_mode != mode:
            self.save_scroll_position(prev_mode)
        self._last_vis_mode_section = mode

        containers = {
            mode_id: getattr(self, container_attr, None)
            for mode_id, container_attr in _VIS_MODE_CONTAINER_ATTR.items()
        }
        for m, container in containers.items():
            if container is not None:
                container.setVisible(m == mode)

        # Restore scroll position for the new mode
        if prev_mode != mode:
            self.restore_scroll_position(mode)

        # Rainbow controls are stable presentation-owned widgets. V7 reloads
        # their active-mode state from the same resolved config used to hydrate
        # the selected lazy body; ordinary section visibility must never invent
        # or restore a second cache authority here.
        self._update_rainbow_visibility()

    def _update_rainbow_visibility(self) -> None:
        """Show/hide rainbow speed slider and apply rainbow text easter egg."""
        try:
            enabled = self.rainbow_enabled.isChecked()
            custom_visible = self._active_visualizer_preset_is_custom()
            bucket = getattr(self, '_rainbow_controls_container', None)
            if bucket is not None:
                bucket.setVisible(custom_visible)
            container = getattr(self, '_rainbow_speed_container', None)
            if container is not None:
                container.setVisible(custom_visible and enabled)

            glow_effect = getattr(self, '_rainbow_glow_effect', None)
            if glow_effect is not None:
                glow_effect.setEnabled(custom_visible and enabled)

            plain_label = getattr(self, '_rainbow_plain_label', None)
            if plain_label is not None:
                palette = plain_label.palette()
                color = QColor("#ffffff")
                if custom_visible and enabled:
                    color = QColor("#f7f7f7")
                palette.setColor(plain_label.foregroundRole(), color)
                plain_label.setPalette(palette)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
