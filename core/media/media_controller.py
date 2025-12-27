"""Centralized media controller for system/Spotify playback.

Provides a thin abstraction over Windows 10/11 Global System Media
Transport Controls (GSMTC) when available, with a safe no-op fallback
when APIs or dependencies are missing.

The controller is intentionally polling-based and side-effect free
for reads. Callers may poll from the UI thread.

On Windows, GSMTC/WinRT calls are treated as potentially blocking IO
and are executed via ThreadManager with a hard timeout so they cannot
stall the UI thread or test runner. All failures are soft (logged at
debug/info) and never raise into the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)


_media_tm = None
_media_tm_lock = None


class MediaPlaybackState(Enum):
    """Normalized playback state used by the UI.

    Values are deliberately coarse so we can map different platform
    enums into a consistent set.
    """

    UNKNOWN = "unknown"
    STOPPED = "stopped"
    PAUSED = "paused"
    PLAYING = "playing"


@dataclass
class MediaTrackInfo:
    """Snapshot of the current media track/state."""

    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    state: MediaPlaybackState = MediaPlaybackState.UNKNOWN
    can_play_pause: bool = False
    can_next: bool = False
    can_previous: bool = False
    # Optional album artwork bytes (e.g. PNG/JPEG), if available.
    artwork: Optional[bytes] = None


class BaseMediaController:
    """Abstract media controller interface.

    Implementations must be safe to call from the UI thread. All
    methods should catch and log their own failures rather than raising.
    """

    def get_current_track(self) -> Optional[MediaTrackInfo]:  # pragma: no cover - interface
        """Return a snapshot of the current track or None if unavailable."""

        raise NotImplementedError

    # Control methods are best-effort; implementations should swallow
    # errors and only log at debug level.
    def play_pause(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def next(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def previous(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class NoOpMediaController(BaseMediaController):
    """Fallback controller used when no platform integration is available."""

    def get_current_track(self) -> Optional[MediaTrackInfo]:
        return None

    def play_pause(self) -> None:
        # Intentionally a no-op
        logger.debug("[MEDIA] play_pause called on NoOpMediaController")

    def next(self) -> None:
        logger.debug("[MEDIA] next called on NoOpMediaController")

    def previous(self) -> None:
        logger.debug("[MEDIA] previous called on NoOpMediaController")


class WindowsGlobalMediaController(BaseMediaController):
    """Windows 10/11 GSMTC-based controller.

    Uses winrt.windows.media.control if available.

    Implementation note: WinRT awaits may stall and do not always honor
    cancellation. To keep UI polling safe, async calls are executed on
    the ThreadManager IO pool with a hard timeout.
    """

    def __init__(self) -> None:
        self._available: bool = False
        self._MediaManager = None
        self._PlaybackStatus = None
        self._init_winrt()

    def _init_winrt(self) -> None:
        try:  # pragma: no cover - exercised indirectly via widget tests
            # Warm up dependent WinRT namespaces so that frozen builds
            # (e.g. Nuitka onefile) include the full dependency tree.
            try:
                import winrt.windows.foundation  # type: ignore[import]  # noqa: F401
            except Exception:
                # Absence of the foundation namespace will be handled by the
                # main import block below, which falls back to a no-op
                # controller when WinRT is not available.
                pass

            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
            )

            self._MediaManager = MediaManager
            self._PlaybackStatus = PlaybackStatus
            self._available = True
            logger.info("[MEDIA] Windows GSMTC controller initialized")
        except Exception as exc:  # ImportError or runtime load failure
            logger.info("[MEDIA] Windows media controls not available: %s", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _run_coroutine(coro):
        """Run an async coroutine in an isolated event loop.

        This avoids interfering with any existing asyncio usage.
        Failures are logged and result in None.

        IMPORTANT: This function must never block the UI thread on a
        potentially-stuck WinRT await. We therefore run the loop on the
        ThreadManager IO pool and enforce a hard timeout; after a hard
        timeout we disable GSMTC queries for the remainder of the session.
        """

        import asyncio
        import threading

        # Lazily provision a shared ThreadManager for media IO.
        global _media_tm, _media_tm_lock
        if _media_tm_lock is None:
            _media_tm_lock = threading.Lock()
        if _media_tm is None:
            with _media_tm_lock:
                if _media_tm is None:
                    try:
                        from core.threading.manager import ThreadManager

                        _media_tm = ThreadManager()
                    except Exception:
                        logger.debug("[MEDIA] Failed to create ThreadManager for GSMTC", exc_info=True)
                        _media_tm = None

        def _close_coro() -> None:
            try:
                close = getattr(coro, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass

        tm = _media_tm
        if tm is None:
            _close_coro()
            return None

        if getattr(tm, "_srpss_media_disabled", False):
            _close_coro()
            return None

        done = threading.Event()
        holder: dict[str, object] = {"result": None}

        def _run_in_loop() -> object:
            try:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)

                    async def _runner():
                        try:
                            # Best-effort timeout (WinRT awaits do not always
                            # honour cancellation).
                            return await asyncio.wait_for(coro, timeout=2.0)
                        except asyncio.TimeoutError:
                            logger.debug("[MEDIA] Coroutine timed out, returning None")
                            return None

                    return loop.run_until_complete(_runner())
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass
            except Exception:
                logger.debug("[MEDIA] GSMTC loop runner failed", exc_info=True)
                return None

        def _on_done(task_result) -> None:
            try:
                holder["result"] = getattr(task_result, "result", None)
            except Exception:
                holder["result"] = None
            finally:
                done.set()

        # Prevent piling up stuck WinRT calls: allow only one inflight query.
        inflight = getattr(tm, "_srpss_media_inflight", False)
        if inflight:
            _close_coro()
            return None
        setattr(tm, "_srpss_media_inflight", True)

        try:
            try:
                from core.threading.manager import TaskPriority
                tm.submit_io_task(
                    _run_in_loop,
                    task_id="media_gsmtc_query",
                    priority=TaskPriority.HIGH,
                    callback=_on_done,
                )
            except Exception:
                logger.debug("[MEDIA] Failed to submit GSMTC query task", exc_info=True)
                _close_coro()
                return None

            if not done.wait(timeout=2.5):
                logger.debug("[MEDIA] GSMTC query hard-timeout, returning None")
                try:
                    setattr(tm, "_srpss_media_disabled", True)
                except Exception:
                    pass
                _close_coro()
                return None

            return holder.get("result")
        finally:
            try:
                setattr(tm, "_srpss_media_inflight", False)
            except Exception:
                pass

    def _select_spotify_session(self, mgr):
        """Select the Spotify media session from a GSMTC manager.

        This prefers sessions whose ``source_app_user_model_id`` contains
        "spotify" (case-insensitive). If no such session is found, this
        returns ``None`` so that the Spotify-specific widget treats the
        situation as "no media" rather than showing some other player.
        """

        sessions = []
        try:
            get_sessions = getattr(mgr, "get_sessions", None)
            if callable(get_sessions):
                maybe_sessions = get_sessions()
                if maybe_sessions is not None:
                    sessions = list(maybe_sessions)
        except Exception:
            logger.debug("[MEDIA] Failed to enumerate media sessions", exc_info=True)
            sessions = []

        if not sessions:
            if is_verbose_logging():
                logger.debug("[MEDIA] No GSMTC sessions available")
        else:
            if is_verbose_logging():
                try:
                    logger.debug("[MEDIA] GSMTC sessions: %s", [
                        getattr(s, "source_app_user_model_id", None) for s in sessions
                    ])
                except Exception:
                    logger.debug("[MEDIA] Failed to describe GSMTC sessions", exc_info=True)

        for session in sessions:
            try:
                app_id = getattr(session, "source_app_user_model_id", None)
            except Exception:
                app_id = None
            if isinstance(app_id, str) and "spotify" in app_id.lower():
                if is_verbose_logging():
                    logger.debug("[MEDIA] Selected Spotify session: %r", app_id)
                return session

        # No Spotify-specific session; for this widget we treat this as
        # "no media" rather than falling back to another player.
        logger.debug("[MEDIA] No Spotify GSMTC session found")
        return None

    def _map_status(self, status) -> MediaPlaybackState:
        try:
            ps = self._PlaybackStatus
            if ps is None:
                return MediaPlaybackState.UNKNOWN
            if status == ps.PLAYING:
                return MediaPlaybackState.PLAYING
            if status == ps.PAUSED:
                return MediaPlaybackState.PAUSED
            if status == ps.STOPPED:
                return MediaPlaybackState.STOPPED
            return MediaPlaybackState.UNKNOWN
        except Exception:
            return MediaPlaybackState.UNKNOWN

    # ------------------------------------------------------------------
    # BaseMediaController API
    # ------------------------------------------------------------------
    def get_current_track(self) -> Optional[MediaTrackInfo]:  # pragma: no cover - requires winrt
        if not self._available or self._MediaManager is None:
            return None

        async def _query():
            mgr = await self._MediaManager.request_async()
            if mgr is None:
                return None

            try:
                session = self._select_spotify_session(mgr)
            except Exception:
                logger.debug("[MEDIA] Failed to select Spotify session", exc_info=True)
                session = None

            if session is None:
                return None

            props = None
            try:
                props = await session.try_get_media_properties_async()
            except Exception:
                logger.debug("[MEDIA] Failed to get media properties", exc_info=True)

            if props is not None and is_verbose_logging():
                try:
                    logger.debug(
                        "[MEDIA] Raw media properties: title=%r, artist=%r, album=%r",
                        getattr(props, "title", None),
                        getattr(props, "artist", None),
                        getattr(props, "album_title", None),
                    )
                except Exception:
                    logger.debug("[MEDIA] Failed to log media properties", exc_info=True)

            try:
                playback_info = session.get_playback_info()
                status = playback_info.playback_status
                controls = getattr(playback_info, "controls", None)
            except Exception:
                logger.debug("[MEDIA] Failed to read playback info", exc_info=True)
                status = None
                controls = None

            info = MediaTrackInfo()
            if props is not None:
                try:
                    info.title = (props.title or "").strip()[:256]
                    info.artist = (props.artist or "").strip()[:256]
                    info.album = (getattr(props, "album_title", "") or "").strip()[:256]
                    info.album_artist = (getattr(props, "album_artist", "") or "").strip()[:256]
                except Exception:
                    if is_verbose_logging():
                        logger.debug("[MEDIA] Failed to normalize media properties", exc_info=True)

            if status is not None:
                info.state = self._map_status(status)

            try:
                if controls is not None:
                    info.can_play_pause = bool(getattr(controls, "is_play_pause_enabled", False))
                    info.can_next = bool(getattr(controls, "is_next_enabled", False))
                    info.can_previous = bool(getattr(controls, "is_previous_enabled", False))
            except Exception:
                if is_verbose_logging():
                    logger.debug("[MEDIA] Failed to read control capabilities", exc_info=True)

            # Optional album artwork thumbnail
            try:
                thumb_ref = getattr(props, "thumbnail", None)
                if thumb_ref is not None:
                    try:
                        from winrt.windows.storage.streams import DataReader  # type: ignore[import]
                    except Exception:
                        DataReader = None  # type: ignore[assignment]

                    if DataReader is not None:
                        stream = await thumb_ref.open_read_async()
                        if stream is not None:
                            try:
                                size = int(getattr(stream, "size", 0))
                            except Exception:
                                size = 0
                            if size > 0:
                                max_bytes = 512 * 1024
                                size = min(size, max_bytes)
                                reader = DataReader(stream)
                                await reader.load_async(size)
                                buf = bytearray(size)
                                reader.read_bytes(buf)
                                reader.close()
                                info.artwork = bytes(buf)
            except Exception:
                if is_verbose_logging():
                    logger.debug("[MEDIA] Failed to read artwork thumbnail", exc_info=True)

            if is_verbose_logging():
                try:
                    state_val = info.state.value if isinstance(info.state, MediaPlaybackState) else str(info.state)
                    logger.debug(
                        "[MEDIA] Track snapshot: state=%s, title=%r, artist=%r, album=%r",
                        state_val,
                        getattr(info, "title", None),
                        getattr(info, "artist", None),
                        getattr(info, "album", None),
                    )
                except Exception:
                    logger.debug("[MEDIA] Failed to log track snapshot", exc_info=True)

            return info

        result = self._run_coroutine(_query())
        if isinstance(result, MediaTrackInfo):
            return result
        return None

    def _invoke_simple_action(self, action_name: str, coro_factory) -> None:
        if not self._available or self._MediaManager is None:
            return

        async def _act():
            mgr = await self._MediaManager.request_async()
            if mgr is None:
                return

            # For the Spotify widget we must send controls to the same
            # Spotify-specific session that `get_current_track` uses,
            # rather than whatever `get_current_session()` happens to
            # return (which might be another player).
            try:
                session = self._select_spotify_session(mgr)
            except Exception:
                logger.debug("[MEDIA] Failed to select Spotify session for %s", action_name, exc_info=True)
                session = None
            if session is None:
                return
            try:
                await coro_factory(session)
            except Exception:
                logger.debug("[MEDIA] %s failed", action_name, exc_info=True)

        result = self._run_coroutine(_act())
        if isinstance(result, Exception):
            logger.debug("[MEDIA] %s coroutine raised: %s", action_name, result, exc_info=True)

    def play_pause(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("play_pause", lambda s: s.try_toggle_play_pause_async())

    def next(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("next", lambda s: s.try_skip_next_async())

    def previous(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("previous", lambda s: s.try_skip_previous_async())


def create_media_controller() -> BaseMediaController:
    """Factory that returns the best available media controller.

    On Windows this prefers the GSMTC-based controller and falls back
    to a NoOp controller when unavailable so that callers never have to
    branch on platform or dependency details.
    """

    try:
        controller = WindowsGlobalMediaController()
        if getattr(controller, "_available", False):
            return controller
    except Exception:
        logger.debug("[MEDIA] Failed to initialize WindowsGlobalMediaController", exc_info=True)

    logger.info("[MEDIA] Falling back to NoOpMediaController")
    return NoOpMediaController()
