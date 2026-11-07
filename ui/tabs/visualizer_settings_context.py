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

from core.logging.logger import get_logger
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.ui_bucket_state import (
    normalize_single_open_bucket_states,
    set_single_open_bucket_state,
    sparse_open_bucket_states,
    visualizer_bucket_scope,
)
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    get_preset_slider_attr,
)
from core.settings.visualizer_presets import (
    MODE_KEY_PREFIXES,
    VISUALIZER_CUSTOM_STORAGE_KEY,
    apply_preset_to_config,
    apply_preset_starting_view,
    build_normalized_custom_snapshot,
    extract_visualizer_snapshot,
    get_custom_preset_index,
    restore_visualizer_snapshot,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_settings_contract import strip_legacy_global_technical_keys
from core.settings.visualizer_settings_snapshot import (
    RETIRED_AUTHORED_TECH_SUFFIXES,
    normalize_visualizer_mode_payload,
    normalize_visualizer_section_mapping,
)
from rendering.widget_descriptors import (
    collect_widget_section_save_result,
    load_widget_section,
)

logger = get_logger(__name__)

DEFAULT_VISUALIZER_MODE = get_default_visualizer_mode_id()


class VisualizerSettingsContextMixin:
    """Shared QWidget-side owner contract for Visualizer Settings presentation."""

    _BUCKET_STATE_KEY = "ui.visualizer_bucket_states"
    _SCROLL_POS_KEY = "ui.visualizer_scroll_positions"

    def _initialize_visualizer_settings_context_state(self) -> None:
        """Initialize Visualizer Settings UI state from canonical profile defaults."""
        defaults = get_default_settings(self._settings.get_application_name())
        ui_defaults = defaults["ui"]
        if not isinstance(ui_defaults, Mapping):
            raise TypeError("Canonical defaults are missing the ui mapping")
        self._visualizer_ui_defaults = deepcopy(dict(ui_defaults))
        self._visualizer_bucket_state = self._load_bucket_states()
        # One open leaf across every mode (the editing path's single context).
        self._visualizer_bucket_state = normalize_single_open_bucket_states(
            tuple(self._visualizer_bucket_state), self._visualizer_bucket_state, scope_for_key=lambda _key: "active",
        )

    def _widget_default(self, section: str, key: str) -> Any:
        """Return one canonical Widget default and fail loudly if schema is incomplete."""
        section_defaults = self._widget_defaults.get(section, {})
        if isinstance(section_defaults, Mapping) and key in section_defaults:
            return deepcopy(section_defaults[key])
        raise KeyError(
            f"Canonical widget defaults are missing persisted product key: "
            f"widgets.{section}.{key}"
        )

    def _monitor_text_from_value(self, section: str, value: object) -> str:
        """Normalize one widget monitor route for a Settings combo.

        Persisted malformed values repair to the canonical widget monitor. The
        helper deliberately owns no ``ALL``/monitor-number product default of
        its own.
        """

        canonical = self._widget_default(section, "monitor")
        candidate = value if isinstance(value, (int, str)) else canonical
        text = str(candidate).strip()
        if not text:
            text = str(canonical).strip()
        if not text:
            raise ValueError(f"Canonical widget monitor is empty: widgets.{section}.monitor")
        return text

    def _monitor_value_from_combo(self, section: str, combo: object) -> int | str:
        """Return a persisted monitor value without inventing a UI fallback."""

        current_text = str(getattr(combo, "currentText")()).strip()
        if not current_text:
            current_text = self._monitor_text_from_value(
                section, self._widget_default(section, "monitor")
            )
        if current_text.upper() == "ALL":
            return "ALL"
        try:
            return int(current_text)
        except (TypeError, ValueError) as exc:
            canonical_text = self._monitor_text_from_value(
                section, self._widget_default(section, "monitor")
            )
            if canonical_text.upper() == "ALL":
                return "ALL"
            try:
                return int(canonical_text)
            except (TypeError, ValueError) as canonical_exc:
                raise ValueError(
                    f"Canonical widget monitor is invalid: widgets.{section}.monitor="
                    f"{canonical_text!r}"
                ) from canonical_exc

    def _combo_data_or_widget_default(self, section: str, key: str, combo: object) -> Any:
        """Return combo data, repairing an impossible empty state canonically."""

        data = getattr(combo, "currentData")()
        if data is not None and (not isinstance(data, str) or data.strip()):
            return data
        return self._widget_default(section, key)

    def _color_from_default(self, section: str, key: str) -> QColor:
        """Return a QColor built strictly from the canonical Widget default."""
        value = self._widget_default(section, key)
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            raise TypeError(f"Canonical widget color default is invalid: widgets.{section}.{key}")
        return QColor(*value)

    def _default_int(self, section: str, key: str) -> int:
        """Return one canonical Widget default coerced to int."""
        try:
            return int(self._widget_default(section, key))
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"Canonical widget int default is invalid: widgets.{section}.{key}"
            ) from exc

    def _default_float(self, section: str, key: str) -> float:
        """Return one canonical Widget default coerced to float."""
        try:
            return float(self._widget_default(section, key))
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"Canonical widget float default is invalid: widgets.{section}.{key}"
            ) from exc

    def _default_bool(self, section: str, key: str) -> bool:
        """Return one canonical Widget bool default."""
        value = self._widget_default(section, key)
        if isinstance(value, bool):
            return value
        raise TypeError(f"Canonical widget bool default is invalid: widgets.{section}.{key}")

    def _default_str(self, section: str, key: str) -> str:
        """Return one canonical Widget string default."""
        value = self._widget_default(section, key)
        if isinstance(value, str):
            return value
        raise TypeError(f"Canonical widget string default is invalid: widgets.{section}.{key}")

    def _config_bool(self, section: str, config: Mapping[str, Any], key: str) -> bool:
        default = self._default_bool(section, key)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        return SettingsManager.to_bool(raw, default)

    def _config_int(self, section: str, config: Mapping[str, Any], key: str) -> int:
        default = self._default_int(section, key)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return int(raw)
        except (TypeError, ValueError, OverflowError):
            return default

    def _config_float(self, section: str, config: Mapping[str, Any], key: str) -> float:
        default = self._default_float(section, key)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return float(raw)
        except (TypeError, ValueError, OverflowError):
            return default

    def _config_str(self, section: str, config: Mapping[str, Any], key: str) -> str:
        default = self._default_str(section, key)
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
                mode = str(section_result.get("mode", existing_vis.get("mode", DEFAULT_VISUALIZER_MODE)))
                selected = self._resolve_visualizer_preset_index(mode, section_result)
                if (selected != get_custom_preset_index(mode)
                        and selected != self._resolve_visualizer_preset_index(mode, existing_vis)):
                    # Orbit/pan are live pose keys, not body controls. Seed them
                    # before normalization; explicit camera edits in this save
                    # then take precedence over the activation's starting view.
                    existing_vis = apply_preset_starting_view(mode, selected, existing_vis)
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
            cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY)
            if not isinstance(cache, dict):
                cache = {}
            cache[current_vis_mode] = snapshot
            self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

        return spotify_vis_config, current_vis_mode, current_preset_index

    def _load_bucket_states(self) -> Dict[str, bool]:
        """Load one remembered open Custom bucket per Visualizer mode page."""
        canonical = self._visualizer_ui_defaults.get("visualizer_bucket_states")
        if not isinstance(canonical, Mapping):
            raise KeyError("Canonical UI defaults are missing ui.visualizer_bucket_states")
        return normalize_single_open_bucket_states(
            canonical.keys(),
            self._settings.get(self._BUCKET_STATE_KEY),
            scope_for_key=visualizer_bucket_scope,
        )

    def retire_bucket_context(self) -> None:
        """Synchronously clear cached Qt bodies and the remembered Custom leaf."""
        from ui.tabs import shared_styles
        shared_styles.collapse_settings_bucket_tree(self)
        if any(self._visualizer_bucket_state.values()):
            for key in self._visualizer_bucket_state:
                self._visualizer_bucket_state[key] = False
            self._settings.set(self._BUCKET_STATE_KEY, {}, emit_change=False)

    def get_visualizer_bucket_state(self, mode: str, bucket: str) -> bool:
        """Return whether this is the remembered open bucket for its mode page."""
        return bool(self._visualizer_bucket_state[f"{mode}:{bucket}"])

    def set_visualizer_bucket_state(self, mode: str, bucket: str, expanded: bool) -> None:
        """Persist this Custom leaf as the one open leaf across every mode."""
        set_single_open_bucket_state(
            self._visualizer_bucket_state, f"{mode}:{bucket}", bool(expanded), scope_for_key=lambda _key: "active",
        )
        self._settings.set(self._BUCKET_STATE_KEY, sparse_open_bucket_states(self._visualizer_bucket_state))

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
                self._restore_scroll_when_reachable(vbar, pos)
            except Exception:
                pass

    def _restore_scroll_when_reachable(self, vbar, pos: int) -> None:
        """Event-driven restore: apply now, or on the first range that reaches ``pos``.

        A freshly built mode body is laid out after this call, so the range may
        still be too small; ``rangeChanged`` reports the real range without a
        timer.  Only the latest request stays connected.
        """
        previous = getattr(self, "_pending_scroll_restore", None)
        if previous is not None:
            try:
                previous[0].rangeChanged.disconnect(previous[1])
            except (RuntimeError, TypeError):
                pass
            self._pending_scroll_restore = None
        if vbar.maximum() >= pos:
            vbar.setValue(pos)
            return

        def _on_range(_minimum: int, maximum: int) -> None:
            if maximum < pos:
                return
            try:
                vbar.rangeChanged.disconnect(_on_range)
            except (RuntimeError, TypeError):
                pass
            self._pending_scroll_restore = None
            vbar.setValue(pos)

        vbar.rangeChanged.connect(_on_range)
        self._pending_scroll_restore = (vbar, _on_range)

    def _snapshot_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> None:
        live_config = self._build_current_spotify_visualizer_config(spotify_vis_config)
        snapshot = build_normalized_custom_snapshot(mode_key, live_config)
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY)
        if not isinstance(cache, dict):
            cache = {}
        cache[mode_key] = snapshot
        self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

    def _restore_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> bool:
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY)
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
        widgets_cfg = self._settings.get('widgets')
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
            for suffix in RETIRED_AUTHORED_TECH_SUFFIXES:
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
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor, get_visualizer_view_pose_keys
        if get_visualizer_mode_descriptor(mode_key).scene_transform_settings:
            from core.settings.visualizer_view_orbit import validate_visualizer_starting_view
            payload["starting_view"] = validate_visualizer_starting_view(
                mode_key, {key: normalized_live[key] for key in get_visualizer_view_pose_keys(mode_key)})
        return payload

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

    @staticmethod
    def _resolve_visualizer_preset_index(mode: str, config: Mapping[str, Any] | None) -> int:
        """Resolve a mode preset index through the shared visualizer preset contract."""
        return resolve_preset_index_from_mapping(mode, config)

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

        widgets_cfg = self._settings.get('widgets') or {}
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
                finally:
                    self._loading = False
            if move_to_custom_pending:
                self._save_settings_now()
            else:
                self._save_settings()
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
        # Admit XYZ and hydrate editors against the target's complete view.
        # Seeding at the later save boundary clamps target XYZ against the old
        # orbit first, and can also overwrite a manual edit before that save.
        spotify_vis_config = apply_preset_starting_view(mode_key, preset_index, spotify_vis_config)

        # Push preset values into UI widgets so the debounced save reads
        # the correct (preset) values instead of stale widget state.
        # Pass full widgets dict (with media intact) so load_media_settings
        # doesn't reset unrelated widgets to defaults.
        if spotify_vis_config != working_config:
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
            finally:
                self._loading = False

        self._save_settings()

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
