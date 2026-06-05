"""Media state tracking and GL overlay lifecycle for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument (except
media_info_to_payload which is a pure helper).

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

import time
from dataclasses import asdict, is_dataclass
from typing import Any, Optional
from PySide6.QtCore import QTimer

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)

_PLAYBACK_PAUSE_CONFIRM_MS = 700
_SHARED_SEED_SOURCES = {"shared_valid_info", "shared_last_valid_info"}


def _payload_state_rank(payload: Optional[dict]) -> int:
    """Rank media payloads so live playing seeds outrank retained paused snapshots."""
    if not isinstance(payload, dict):
        return -1
    state = str(payload.get("state", "") or "").lower()
    if state == "playing":
        return 2
    if state == "paused":
        return 1
    if state == "stopped":
        return 0
    return -1


def media_info_to_payload(info: object) -> Optional[dict]:
    """Convert cached media info objects into the payload shape used by updates."""
    if info is None:
        return None
    if isinstance(info, dict):
        payload = dict(info)
    else:
        payload: dict[str, object] = {}
        try:
            if is_dataclass(info):
                payload = asdict(info)
            else:
                for attr in ("title", "artist", "album", "app_name", "artwork", "artwork_url", "state"):
                    if hasattr(info, attr):
                        payload[attr] = getattr(info, attr)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to build media seed payload", exc_info=True)
            return None

    state = payload.get("state")
    try:
        if hasattr(state, "value"):
            payload["state"] = state.value
        elif state is not None:
            payload["state"] = str(state)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to normalize media seed state", exc_info=True)
    return payload or None


def seed_playback_state_from_anchor(
    widget: Any,
    *,
    reason: str,
    request_refresh_if_missing: bool,
) -> bool:
    """Seed playback state from the anchor media widget or its shared cache."""
    anchor = widget._anchor_media
    best_payload: Optional[dict] = None
    best_source = "<none>"
    best_score = (-1, -1)

    def _consider(candidate: object, *, source: str, source_rank: int) -> None:
        nonlocal best_payload, best_source, best_score
        payload = media_info_to_payload(candidate)
        if payload is None:
            return
        candidate_score = (_payload_state_rank(payload), source_rank)
        if candidate_score > best_score:
            best_payload = payload
            best_source = source
            best_score = candidate_score

    if anchor is not None:
        _consider(getattr(anchor, "_last_info", None), source="anchor._last_info", source_rank=2)

        try:
            shared_getter = getattr(type(anchor), "_get_shared_valid_info", None)
            if callable(shared_getter):
                _consider(shared_getter(), source="shared_valid_info", source_rank=3)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to read shared media cache", exc_info=True)

        try:
            _consider(
                getattr(type(anchor), "_shared_last_valid_info", None),
                source="shared_last_valid_info",
                source_rank=1,
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to read legacy shared media cache", exc_info=True)

    payload = best_payload
    if payload is not None:
        state = str(payload.get("state", "") or "").lower()
        provisional_nonplaying_seed = (
            state in {"paused", "stopped"}
            and best_source in _SHARED_SEED_SOURCES
        )
        widget.handle_media_update(
            payload,
            source="seed",
            seed_source=best_source,
        )
        idle_capable_mode = str(getattr(widget, "_vis_mode_str", "") or "").lower() in {
            "bubble",
            "sine_wave",
            "devcurve",
        }
        widget._startup_idle_reveal_requires_authoritative_media = (
            provisional_nonplaying_seed and not idle_capable_mode
        )
        widget._startup_has_authoritative_media_update = False
        logger.debug(
            "[SPOTIFY_VIS] Seeded playback state from anchor (%s source=%s state=%s)",
            reason,
            best_source,
            payload.get("state"),
        )
        if provisional_nonplaying_seed and anchor is not None:
            refresher = getattr(anchor, "refresh_playback_state", None)
            if callable(refresher):
                try:
                    refresher()
                    logger.debug(
                        "[SPOTIFY_VIS] Requested anchor playback refresh (%s provisional_nonplaying_seed)",
                        reason,
                    )
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to request anchor playback refresh for provisional non-playing seed",
                        exc_info=True,
                    )
        return True

    if request_refresh_if_missing and anchor is not None:
        refresher = getattr(anchor, "refresh_playback_state", None)
        if callable(refresher):
            try:
                refresher()
                logger.debug("[SPOTIFY_VIS] Requested anchor playback refresh (%s)", reason)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to request anchor playback refresh", exc_info=True)
    return False


def clear_pending_playback_pause(widget: Any) -> None:
    """Cancel any pending deferred non-playing commit."""
    timer = getattr(widget, "_pending_playback_pause_timer", None)
    if timer is not None:
        try:
            timer.stop()
            timer.deleteLater()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to clear pending pause timer", exc_info=True)
    widget._pending_playback_pause_timer = None
    widget._pending_playback_pause_state = None


def _commit_playback_state(widget: Any, *, state: str, reason: str) -> None:
    prev = bool(getattr(widget, "_spotify_playing", False))
    is_playing = state == "playing"
    widget._spotify_playing = is_playing
    widget._last_media_state_ts = time.time()
    widget._fallback_logged = False
    if is_playing:
        widget._startup_require_playing_before_reveal = False

    if is_playing and not prev:
        widget._trigger_wake(reason=reason)

    try:
        if widget._engine is not None:
            widget._engine.set_playback_state(is_playing)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to set beat engine playback state", exc_info=True)

    if (
        widget._spotify_playing
        and widget._startup_reveal_pending
        and widget._startup_hot_start_started
        and not widget._waiting_for_fresh_frame
    ):
        widget._finish_staged_startup_reveal(reason="play_state_ready")

    widget.sync_visibility_with_anchor()


def _schedule_nonplaying_commit(widget: Any, *, state: str) -> None:
    clear_pending_playback_pause(widget)
    widget._pending_playback_pause_state = state

    timer = QTimer(widget)
    timer.setSingleShot(True)
    timer.setInterval(_PLAYBACK_PAUSE_CONFIRM_MS)

    def _on_timeout() -> None:
        widget._pending_playback_pause_timer = None
        pending_state = getattr(widget, "_pending_playback_pause_state", None)
        widget._pending_playback_pause_state = None
        if pending_state not in {"paused", "stopped"}:
            return
        _commit_playback_state(widget, state=pending_state, reason="play_state_pause_confirmed")

    timer.timeout.connect(_on_timeout)
    widget._pending_playback_pause_timer = timer
    try:
        register_resource = getattr(widget, "_register_resource", None)
        if callable(register_resource):
            register_resource(timer, "visualizer pending playback pause timer")
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to register pending pause timer", exc_info=True)
    timer.start()


def handle_media_update(
    widget: Any,
    payload: dict,
    *,
    source: str = "live",
    seed_source: str | None = None,
) -> None:
    """Receive media state from MediaWidget.

    Expects payload from MediaWidget.media_updated with a ``state``
    field of "playing"/"paused"/"stopped". When not playing, the
    visualizer decays to idle even if other apps are producing audio.
    Contract: this is provider-neutral and follows whichever media
    provider is currently active (Spotify or MusicBee).
    """

    try:
        state = str(payload.get("state", "")).lower()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        state = ""
    widget._last_media_state_ts = time.time()
    widget._fallback_logged = False
    prev = bool(getattr(widget, "_spotify_playing", False))
    if source == "live":
        widget._startup_has_authoritative_media_update = True
        widget._startup_idle_reveal_requires_authoritative_media = False

    if state == "playing":
        clear_pending_playback_pause(widget)
        if not prev:
            _commit_playback_state(widget, state="playing", reason="play_state_transition")
        else:
            widget._spotify_playing = True
            widget._startup_require_playing_before_reveal = False
    elif state in {"paused", "stopped"}:
        if prev:
            _schedule_nonplaying_commit(widget, state=state)
        else:
            clear_pending_playback_pause(widget)
            _commit_playback_state(widget, state=state, reason="play_state_nonplaying")
    else:
        clear_pending_playback_pause(widget)

    # WAKE TRIGGER: Artwork changed (indicates track change, possibly during pause)
    artwork_url = payload.get("artwork_url", "")
    artwork_hash = hash(artwork_url) if artwork_url else 0
    if artwork_hash != getattr(widget, "_last_artwork_hash", 0):
        widget._last_artwork_hash = artwork_hash
        if not widget._spotify_playing:
            # Artwork changed while paused - likely a wake event
            widget._trigger_wake(reason="paused_artwork_change")

    first_media = not widget._has_seen_media
    if first_media:
        # Track that we have seen at least one Spotify media state update
        # so later calls can focus purely on bar gating.
        widget._has_seen_media = True

    if is_verbose_logging():
        try:
            logger.debug(
                "[SPOTIFY_VIS] handle_media_update: state=%r (prev_playing=%s, now_playing=%s)",
                state,
                prev,
                widget._spotify_playing,
            )
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    if state in {"paused", "stopped"} and prev and getattr(widget, "_pending_playback_pause_timer", None) is not None:
        logger.debug(
            "[SPOTIFY_VIS] Deferring %s media state for %dms to absorb playback-state wobble",
            state,
            _PLAYBACK_PAUSE_CONFIRM_MS,
        )
    elif source == "seed" and state in {"paused", "stopped"} and seed_source in _SHARED_SEED_SOURCES:
        logger.debug(
            "[SPOTIFY_VIS] Provisional non-playing startup seed retained until live media confirms state (source=%s)",
            seed_source,
        )


def sync_visibility_with_anchor(widget: Any) -> None:
    """Show/hide based on anchor media widget visibility."""
    parent = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    if getattr(widget, "_custom_layout_shell_active", False) or getattr(parent, "_custom_layout_edit_active", False):
        return
    try:
        anchor_visible = widget._is_anchor_visible()
        if anchor_visible:
            if widget._enabled and widget._startup_secondary_stage_pending:
                if not widget._is_parent_secondary_stage_ready():
                    logger.debug("[SPOTIFY_VIS] Waiting for centralized secondary-stage startup deadline")
                    return
                widget.begin_spotify_secondary_stage()
                return
            if widget._startup_reveal_pending:
                return
            if widget._enabled and not widget.isVisible():
                widget._start_widget_fade_in()
        elif widget.isVisible():
            widget.hide()
            widget._clear_gl_overlay()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def destroy_parent_overlay(widget: Any, *, reason: str) -> None:
    """Destroy the GL bars overlay and clean up its resources."""
    parent = widget.parent()
    if parent is None:
        logger.warning("[SPOTIFY_VIS] Overlay destroy requested without parent (reason=%s)", reason)
        return

    overlay = getattr(parent, "_spotify_bars_overlay", None)
    if overlay is None:
        logger.debug("[SPOTIFY_VIS] No overlay to destroy (reason=%s)", reason)
        return

    logger.debug(
        "[SPOTIFY_VIS] Destroying SpotifyBarsGLOverlay (reason=%s id=%s)",
        reason,
        hex(id(overlay)),
    )

    pixel_shift_manager = getattr(parent, "_pixel_shift_manager", None)
    if pixel_shift_manager is not None:
        try:
            pixel_shift_manager.unregister_widget(overlay)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to unregister overlay from PixelShiftManager", exc_info=True)

    try:
        overlay.hide()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to hide overlay before destroy", exc_info=True)

    try:
        if hasattr(overlay, "clear_overlay_buffer"):
            overlay.clear_overlay_buffer()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to blank overlay buffer before destroy", exc_info=True)

    try:
        overlay.update()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule overlay update before destroy", exc_info=True)

    try:
        if hasattr(overlay, "cleanup_gl"):
            overlay.cleanup_gl()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to cleanup overlay GL state", exc_info=True)

    try:
        overlay.deleteLater()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule overlay delete", exc_info=True)

    try:
        setattr(parent, "_spotify_bars_overlay", None)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to clear parent overlay reference", exc_info=True)

    # Clear transient opacity state before waiting for the fresh GL frame.
    widget._pending_shadow_cache_invalidation = True
    widget._invalidate_shadow_cache_if_needed()
    widget._shadow_config_missing = True
    widget._waiting_for_fresh_frame = True


def clear_parent_overlay_runtime(widget: Any, *, reason: str) -> None:
    """Blank and hide the GL bars overlay without destroying the GL object.

    This preserves the expensive GL/shader setup across mode and preset
    resets while still forcing the same cold runtime handoff before the next
    visible frame can commit.
    """
    parent = widget.parent()
    if parent is None:
        logger.warning("[SPOTIFY_VIS] Overlay clear requested without parent (reason=%s)", reason)
        return

    overlay = getattr(parent, "_spotify_bars_overlay", None)
    if overlay is None:
        logger.debug("[SPOTIFY_VIS] No overlay to clear (reason=%s)", reason)
        return

    logger.debug(
        "[SPOTIFY_VIS] Clearing SpotifyBarsGLOverlay runtime state (reason=%s id=%s)",
        reason,
        hex(id(overlay)),
    )

    try:
        if hasattr(overlay, "request_mode_reset"):
            overlay.request_mode_reset(widget._vis_mode_str)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to request overlay mode reset during clear", exc_info=True)

    try:
        overlay.hide()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to hide overlay during clear", exc_info=True)

    try:
        if hasattr(overlay, "clear_overlay_buffer"):
            overlay.clear_overlay_buffer()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to blank overlay buffer during clear", exc_info=True)

    try:
        overlay.update()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to schedule overlay update during clear", exc_info=True)

    widget._pending_shadow_cache_invalidation = True
    widget._invalidate_shadow_cache_if_needed()
    widget._shadow_config_missing = True
    widget._waiting_for_fresh_frame = True


def request_overlay_mode_reset(widget: Any, *, mode: Optional[str] = None, reason: str = "widget_reset") -> None:
    """Ask the GL overlay (if present) to cold-reset its per-mode state."""

    parent = widget.parent()
    if parent is None or not hasattr(parent, "push_spotify_visualizer_frame"):
        return
    overlay = getattr(parent, "_spotify_bars_overlay", None)
    if overlay is None or not hasattr(overlay, "request_mode_reset"):
        return
    try:
        target = mode or widget._vis_mode_str
        overlay.request_mode_reset(target)
        logger.debug("[SPOTIFY_VIS] Requested overlay mode reset: mode=%s reason=%s", target, reason)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to request overlay mode reset", exc_info=True)
