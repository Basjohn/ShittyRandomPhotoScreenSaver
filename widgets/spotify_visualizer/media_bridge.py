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

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)

# The visualizer no longer debounces its own visible playback state.
#
# A 700 ms confirm timer used to sit between a paused/stopped media update and
# `_spotify_playing`, and any wobbling update re-armed it - the installed run
# shows deferred pause messages at 13:15:14, :16, :17, :19, :23 with the engine
# only settling at :24, which is the multi-second "limbo" the operator sees on
# pause/resume.
#
# It was never needed to protect capture: `SpotifyBeatEngine` already holds
# `_capture_keepalive_grace = 6.0s` and warm-resumes inside that window. So the
# two concerns are now split - the logical/presentation playback target follows
# the trusted MediaWidget state promptly, and capture lifetime stays engine
# policy. No replacement timer was introduced.
_SHARED_SEED_SOURCES = {"runtime_current_info"}


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
    """Seed playback state from the anchor's neutral owner or local mirror."""
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
        try:
            current_getter = getattr(anchor, "current_media_info", None)
            if callable(current_getter):
                _consider(
                    current_getter(),
                    source="runtime_current_info",
                    source_rank=3,
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to read Media runtime snapshot", exc_info=True)

        # Transitional E1 edge: keep the presenter's accepted mirror available
        # to standalone/test anchors that do not expose the neutral service yet.
        _consider(getattr(anchor, "_last_info", None), source="anchor._last_info", source_rank=2)

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
        # This used to be a third hard-coded set that omitted Oscilloscope and
        # never learned about Spectrum's idle scene, so a provisional paused seed
        # could block a startup the other owners considered legal.
        from widgets.spotify_visualizer import mode_capabilities

        idle_capable_mode = mode_capabilities.allows_idle_reveal(
            getattr(widget, "_vis_mode_str", "")
        )
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
    """Drop any retained pending-pause state.

    Nothing arms a pending pause any more, but lifecycle owners (engine
    acquire/release, edit suspend/resume, staged startup) still call this to
    guarantee a clean slate, and it stays cheap and safe.
    """
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

    if is_playing != prev:
        try:
            widget._reset_latency_diagnostics()
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to reset latency diagnostics for playback epoch",
                exc_info=True,
            )

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

    widget._last_committed_playback_state = state
    widget.sync_visibility_with_anchor()


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
        # Prompt in both directions. The visualizer trusts the canonical
        # MediaWidget state and begins its authored move toward idle now;
        # absorbing provider wobble is the media state owner's job, and keeping
        # capture warm across a short pause is the engine's.
        clear_pending_playback_pause(widget)
        # Idempotent: a provider repeating "paused" must not redo the idle
        # commit and its visibility sync, while paused -> stopped still commits.
        if prev or getattr(widget, "_last_committed_playback_state", None) != state:
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

    if source == "seed" and state in {"paused", "stopped"} and seed_source in _SHARED_SEED_SOURCES:
        logger.debug(
            "[SPOTIFY_VIS] Provisional non-playing startup seed retained until live media confirms state (source=%s)",
            seed_source,
        )


def _scene_needs_reveal(widget: Any) -> bool:
    """Whether an anchor sync should start a reveal.

    A mode transition owns its own fade-out/fade-in sequence, so an ordinary
    media update in the middle of one must not restart the reveal underneath it.
    """
    from widgets.spotify_visualizer.startup_staging import scene_needs_reveal

    try:
        if int(getattr(widget, "_mode_transition_phase", 0) or 0) != 0:
            return False
        if str(getattr(widget, "_mode_teardown_state", "idle") or "idle") != "idle":
            return False
    except Exception:
        logger.debug("[SPOTIFY_VIS] Mode transition state unavailable", exc_info=True)

    # Narrow on purpose: this path only rescues the case the single-surface
    # migration created - a scene that WAS revealed and has since faded to zero
    # while its logical widget stayed shown. A visualizer that has never been
    # revealed is the staged startup owner's business, not an anchor sync's.
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    try:
        fade = ensure_presentation_fade(widget)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Scene fade unavailable", exc_info=True)
        return False
    if not fade.has_started():
        return False
    return scene_needs_reveal(widget)


def _fade_out_for_absent_anchor(widget: Any) -> None:
    """Fade the visualizer out through the one compositor fade authority.

    The compositor owns the card and shader pixels now, so hiding the logical
    QWidget removes nothing and dropping the published state would make the card
    disappear in a single frame. The scene fades to zero first, and only then is
    the published state released.

    GL resources are deliberately NOT destroyed: an anchor that comes back must
    not pay for a cold shader/card rebuild.
    """
    from widgets.spotify_visualizer.presentation_fade import ensure_presentation_fade

    fade = ensure_presentation_fade(widget)
    if fade.is_fading_out():
        return

    def _release() -> None:
        try:
            widget.hide()
            widget._clear_gl_overlay()
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to release visualizer after anchor fade-out",
                exc_info=True,
            )

    if fade.progress <= 0.0:
        _release()
        return

    try:
        widget._start_widget_fade_out(on_complete=_release)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Anchor fade-out failed; hiding directly", exc_info=True)
        _release()


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
            if widget._enabled and (not widget.isVisible() or _scene_needs_reveal(widget)):
                widget._start_widget_fade_in()
        elif widget.isVisible():
            _fade_out_for_absent_anchor(widget)
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

    # GL deletion is an ownership boundary. If it fails, retain the overlay and
    # parent reference so full display teardown can fail loudly and retry.
    if hasattr(overlay, "cleanup_gl"):
        overlay.cleanup_gl()

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
