"""Spotify-specific volume controller built on Windows Core Audio via pycaw.

This module provides a small, best-effort helper for reading and adjusting the
per-application volume of the Spotify session only. It is safe to import and
construct even when ``pycaw`` (and its COM dependencies) are not available: in
that case the controller reports ``is_available() == False`` and all methods
become cheap no-ops that never raise.

All methods are synchronous and intended to be called from short-lived worker
tasks scheduled via :mod:`core.threading.manager`. Callers should avoid
invoking them directly from the UI thread in tight loops.
"""
from __future__ import annotations

from typing import Any, Optional

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)

try:  # pragma: no cover - pycaw is optional at runtime
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume  # type: ignore[import]
except Exception:  # ImportError or COM initialisation issues
    AudioUtilities = None  # type: ignore[assignment]
    ISimpleAudioVolume = None  # type: ignore[assignment]
    _PYCAW_AVAILABLE = False
else:
    _PYCAW_AVAILABLE = True


class SpotifyVolumeController:
    """Best-effort per-session volume controller for Spotify.

    The controller searches Core Audio sessions for ones whose process name
    contains ``"spotify"`` and exposes a minimal API to read and write that
    session's master volume via ``ISimpleAudioVolume``. It deliberately does
    not touch the system/master volume.
    """

    def __init__(self) -> None:
        self._available: bool = bool(_PYCAW_AVAILABLE)
        self._last_pid: Optional[int] = None

        if not self._available:
            logger.info(
                "[SPOTIFY_VOL] pycaw/Core Audio not available; Spotify volume control disabled"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when pycaw/Core Audio integration is available."""

        return self._available

    def get_volume(self) -> Optional[float]:
        """Return the current Spotify session volume in ``[0.0, 1.0]``.

        Returns ``None`` when Spotify is not running, no matching audio
        session exists, or when pycaw/Core Audio is unavailable.
        """

        volume_iface = self._find_spotify_volume_iface()
        if volume_iface is None:
            return None

        try:
            value = float(volume_iface.GetMasterVolume())  # type: ignore[attr-defined]
        except Exception:
            logger.debug("[SPOTIFY_VOL] GetMasterVolume failed", exc_info=True)
            return None

        # Clamp defensively into a proper [0.0, 1.0] range.
        value = max(0.0, min(1.0, value))
        self._last_pid = getattr(getattr(volume_iface, "_session", None), "ProcessId", None)
        return value

    def set_volume(self, level: float) -> bool:
        """Set the Spotify session volume to ``level`` in ``[0.0, 1.0]``.

        Returns ``True`` on apparent success, ``False`` when Spotify is not
        running, no suitable Core Audio session is found, or when pycaw is
        unavailable.
        """

        volume_iface = self._find_spotify_volume_iface()
        if volume_iface is None:
            return False

        clamped = float(max(0.0, min(1.0, level)))
        try:
            volume_iface.SetMasterVolume(clamped, None)  # type: ignore[attr-defined]
            if is_verbose_logging():
                logger.debug("[SPOTIFY_VOL] Set volume to %.3f", clamped)
            self._last_pid = getattr(getattr(volume_iface, "_session", None), "ProcessId", None)
            return True
        except Exception:
            logger.debug("[SPOTIFY_VOL] SetMasterVolume failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_spotify_volume_iface(self) -> Optional[Any]:
        """Locate an ``ISimpleAudioVolume`` for the Spotify session.

        This call is intentionally resilient: any failures in enumerating
        sessions or querying COM interfaces are logged at debug level and
        treated as "no session" rather than raising.
        
        Searches ALL audio devices, not just the default, to handle cases
        where Spotify outputs to a non-default device (headphones, DAC, etc.).
        """

        if not self._available or AudioUtilities is None or ISimpleAudioVolume is None:
            return None

        # Search all sessions on the default device
        # Note: Spotify only appears as an audio session when actively playing audio.
        # If Spotify is paused or stopped, no session will be found.
        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception:
            logger.debug("[SPOTIFY_VOL] GetAllSessions failed", exc_info=True)
            return None
        
        result = self._search_sessions_for_spotify(sessions)
        if result is not None:
            return result
        
        # Log available sessions for debugging
        if is_verbose_logging():
            session_names = []
            for s in sessions:
                try:
                    if s.Process:
                        session_names.append(s.Process.name())
                except Exception:
                    pass
            logger.debug("[SPOTIFY_VOL] No Spotify session found. Active sessions: %s", session_names)
        
        return None
    
    def _search_sessions_for_spotify(self, sessions) -> Optional[Any]:
        """Search a list of audio sessions for Spotify."""
        if not sessions:
            return None
        
        for session in sessions:
            proc = None
            try:
                proc = getattr(session, "Process", None)
            except Exception:
                proc = None

            if proc is None:
                continue

            try:
                name = proc.name()
            except Exception:
                name = None

            if not isinstance(name, str):
                continue

            if "spotify" not in name.lower():
                continue

            # We have a Spotify session – try to obtain its ISimpleAudioVolume.
            try:
                ctl = getattr(session, "_ctl", None)
                if ctl is None:
                    continue
                volume = ctl.QueryInterface(ISimpleAudioVolume)  # type: ignore[call-arg]
                return volume
            except Exception:
                logger.debug(
                    "[SPOTIFY_VOL] Failed to obtain ISimpleAudioVolume for %r", name, exc_info=True
                )
                continue
        
        return None
