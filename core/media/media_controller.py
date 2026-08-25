"""Centralized media controller for system/Spotify playback.

Provides a thin abstraction over Windows 10/11 Global System Media
Transport Controls (GSMTC) when available, with a safe no-op fallback
when APIs or dependencies are missing.

The controller exposes polling reads, while the Media runtime owner determines
cadence and submits potentially blocking reads through ThreadManager.

On Windows, GSMTC/WinRT calls are treated as potentially blocking IO
and are executed via ThreadManager with a hard timeout so they cannot
stall the UI thread or test runner. All failures are soft (logged at
debug/info) and never raise into the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Optional
import threading

from core.logging.logger import get_logger, is_verbose_logging
from core.media.provider_registry import (
    get_provider_process_exe_names,
    normalize_provider_id,
    provider_matches_source_app_user_model_id,
)

logger = get_logger(__name__)


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
    can_seek: bool = False
    # Optional album artwork bytes (e.g. PNG/JPEG), if available.
    artwork: Optional[bytes] = None
    # Runtime-only identity of the selected GSMTC host. Never persisted.
    source_app_user_model_id: str = ""
    # Runtime-only timeline snapshot captured by the existing GSMTC query.
    # These fields never introduce their own timer or polling cadence.
    position_ms: Optional[int] = None
    duration_ms: Optional[int] = None


class BaseMediaController:
    """Abstract media controller interface.

    Implementations must be safe to call from the UI thread. All
    methods should catch and log their own failures rather than raising.
    """

    def __init__(self, thread_manager=None) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = None
        self._retired = False
        self._task_owner_id = f"{id(self):x}"

    def set_thread_manager(self, thread_manager) -> None:
        """Inject the engine-owned ThreadManager."""
        self._thread_manager = thread_manager

    def set_runtime_generation(self, runtime_generation) -> None:
        """Tag controller work for the owning screensaver runtime generation."""
        self._runtime_generation = runtime_generation

    def retire(self) -> None:
        """Close new command/query admission; in-flight WinRT work may finish fenced."""
        self._retired = True
        self._thread_manager = None

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

    def seek_fraction(self, fraction: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def is_app_process_running(self) -> bool:
        """Lightweight check whether the target media app process exists.

        Used by idle polling to distinguish 'app not running' (deep idle,
        ~30s) from 'app running but no media session' (normal idle, ~5s).
        Default returns False; platform implementations override.
        """
        return False


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

    def seek_fraction(self, fraction: float) -> None:
        logger.debug(
            "[MEDIA] seek_fraction(%s) called on NoOpMediaController", fraction
        )


class WindowsGlobalMediaController(BaseMediaController):
    """Windows 10/11 GSMTC-based controller.

    Uses winrt.windows.media.control if available.

    Implementation note: WinRT awaits may stall and do not always honor
    cancellation. To keep UI polling safe, async calls are executed on
    the ThreadManager IO pool with a hard timeout.
    
    Timeout resilience: When GSMTC times out (common when media is paused),
    returns the last known valid info instead of None to prevent spurious
    widget hiding.
    """

    def __init__(self, thread_manager=None, app_filter: str = "spotify") -> None:
        super().__init__(thread_manager)
        self._provider_id: Optional[str] = normalize_provider_id(app_filter)
        # Retain this attribute for diagnostic compatibility.  It is no longer
        # used as a substring filter.
        self._app_filter: str = self._provider_id or str(app_filter or "").strip().lower()
        self._available: bool = False
        self._MediaManager = None
        self._PlaybackStatus = None
        self._gsmc_inflight = False
        # Transport commands (play/pause/next/previous) are fire-and-forget and
        # must never block the GUI caller, so they get their own inflight guard
        # rather than sharing the query guard: a background status query must not
        # be able to drop a user's transport command, and vice versa.
        self._command_inflight = False
        # Cache last valid info for timeout resilience
        self._last_valid_info: Optional[MediaTrackInfo] = None
        self._last_valid_info_ts: float = 0.0
        self._timeout_cache_ttl: float = 30.0  # Use cached info for up to 30s on timeout
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
        except Exception as _:
            logger.info("[MEDIA] Windows media controls not available: %s", _)
            self._available = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_coro_in_isolated_loop(self, coro_factory) -> object:
        """Run one coroutine to completion in its own event loop; return result.

        Shared by the blocking query path (`_run_coroutine`) and the
        non-blocking command path (`_submit_command`). Never raises: WinRT awaits
        that stall are bounded by an internal timeout and all failures resolve to
        None.
        """

        import asyncio

        try:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)

                async def _runner():
                    try:
                        # Create fresh coroutine inside the loop to avoid reuse errors
                        coro = coro_factory()
                        # Best-effort timeout (WinRT awaits do not always
                        # honour cancellation).
                        return await asyncio.wait_for(coro, timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.debug("[MEDIA] Coroutine timed out, returning None")
                        return None
                    except MemoryError:
                        logger.error("[MEDIA] MemoryError in GSMTC coroutine — returning None")
                        return None

                return loop.run_until_complete(_runner())
            finally:
                try:
                    loop.close()
                except Exception:
                    logger.debug("[MEDIA] Loop close failed")
        except MemoryError:
            logger.error("[MEDIA] MemoryError in GSMTC loop runner — returning None")
            return None
        except Exception:
            logger.debug("[MEDIA] GSMTC loop runner failed", exc_info=True)
            return None

    def _submit_command(self, action_name: str, coro_factory) -> None:
        """Fire-and-forget a transport command on the IO owner.

        The GUI caller never waits for WinRT completion - that synchronous wait
        (via `_run_coroutine`'s `done.wait()`) stalled the GUI event loop on the
        Pause/Play edge, showing up as `dispatch_pending_skips` and a visible
        hitch. The optimistic UI state and control feedback are applied by the
        caller immediately, and normal refresh reconciles the real state later.

        Command dedup is preserved: a duplicate arriving while one command is
        still inflight is dropped, exactly as the old shared inflight guard did -
        but a background status query can no longer drop a user's command.
        """

        if getattr(self, "_retired", False):
            return
        tm = self._thread_manager
        if tm is None:
            logger.warning(
                "[MEDIA] ThreadManager not injected for GSMTC controller; skipping %s",
                action_name,
            )
            return
        if self._command_inflight:
            logger.debug(
                "[MEDIA] Dropping %s: a transport command is already inflight",
                action_name,
            )
            return

        self._command_inflight = True

        def _run_and_clear() -> None:
            try:
                self._run_coro_in_isolated_loop(coro_factory)
            finally:
                # Cleared on the IO worker once the WinRT command really finished.
                self._command_inflight = False

        _run_and_clear._srpss_runtime_generation = getattr(
            self, "_runtime_generation", None
        )

        try:
            from core.threading.manager import TaskPriority
            tm.submit_io_task(
                _run_and_clear,
                task_id=(
                    f"media_cmd_{getattr(self, '_task_owner_id', f'{id(self):x}')}_"
                    f"{action_name}"
                ),
                priority=TaskPriority.HIGH,
            )
        except Exception:
            self._command_inflight = False
            logger.debug("[MEDIA] Failed to submit %s command", action_name, exc_info=True)

    def _run_coroutine(self, coro_factory, *, already_on_io_worker: bool = False):
        """Run an async coroutine in an isolated event loop.

        Args:
            coro_factory: Callable that returns a fresh coroutine object.
                         This prevents "cannot reuse already awaited coroutine" errors.

        This avoids interfering with any existing asyncio usage.
        Failures are logged and result in None.

        IMPORTANT: UI callers are isolated on the ThreadManager IO pool.
        An owner that is already executing on that pool may opt into the
        direct bounded path, avoiding a nested submission/wait cycle.
        Inflight checking prevents query pileup in either path.
        """

        if getattr(self, "_retired", False):
            return None
        tm = self._thread_manager
        if tm is None:
            logger.warning("[MEDIA] ThreadManager not injected for GSMTC controller; skipping coroutine")
            return None

        done = threading.Event()
        holder: dict[str, object] = {"result": None}

        def _run_in_loop() -> object:
            return self._run_coro_in_isolated_loop(coro_factory)

        _run_in_loop._srpss_runtime_generation = getattr(
            self, "_runtime_generation", None
        )

        if already_on_io_worker:
            if self._gsmc_inflight:
                return None
            self._gsmc_inflight = True
            try:
                return _run_in_loop()
            finally:
                self._gsmc_inflight = False

        def _on_done(task_result) -> None:
            try:
                holder["result"] = getattr(task_result, "result", None)
            except Exception as exc:
                logger.debug("[MEDIA] Exception suppressed: %s", exc)
                holder["result"] = None
            finally:
                done.set()

        # Prevent piling up stuck WinRT calls: allow only one inflight query per controller.
        if self._gsmc_inflight:
            return None
        self._gsmc_inflight = True

        try:
            try:
                from core.threading.manager import TaskPriority
                tm.submit_io_task(
                    _run_in_loop,
                    task_id=(
                        "media_gsmtc_query_"
                        f"{getattr(self, '_task_owner_id', f'{id(self):x}')}"
                    ),
                    priority=TaskPriority.HIGH,
                    callback=_on_done,
                )
            except Exception:
                logger.debug("[MEDIA] Failed to submit GSMTC query task", exc_info=True)
                return None

            if not done.wait(timeout=2.5):
                logger.debug("[MEDIA] GSMTC query hard-timeout, returning None")
                return None

            return holder.get("result")
        finally:
            self._gsmc_inflight = False

    @staticmethod
    def _session_source_id(session) -> str:
        try:
            app_id = getattr(session, "source_app_user_model_id", None)
            return app_id if isinstance(app_id, str) else ""
        except Exception:
            return ""

    @classmethod
    def _session_source_id_for_log(cls, session) -> str:
        """Return one bounded source identity for diagnostics only."""

        source_id = cls._session_source_id(session)
        if not source_id:
            return "<none>"
        return source_id[:260]

    @classmethod
    def _session_source_ids_for_log(cls, sessions, *, limit: int = 16) -> list[str]:
        """Return a bounded diagnostic snapshot of enumerated source ids."""

        bounded_limit = max(1, int(limit))
        values = [
            cls._session_source_id_for_log(session)
            for session in sessions[:bounded_limit]
        ]
        remaining = len(sessions) - len(values)
        if remaining > 0:
            values.append(f"<{remaining} more>")
        return values

    def _select_media_session_for_providers(
        self,
        mgr,
        provider_ids: Iterable[str],
    ) -> tuple[Optional[str], object | None]:
        """Select one provider/session from a single GSMTC enumeration.

        Playing sessions win across the primary/fallback chain, with provider
        order breaking ties. If nothing is playing, provider order remains
        authoritative and a matching current session wins within that provider.
        This lets an actively playing browser take over from a stale/paused
        desktop provider without changing single-provider selection semantics.
        """

        providers: list[str] = []
        for value in provider_ids:
            normalized = normalize_provider_id(value)
            if normalized is not None and normalized not in providers:
                providers.append(normalized)
        if not providers:
            logger.debug("[MEDIA] No registered provider supplied for GSMTC selection")
            return None, None

        try:
            get_sessions = getattr(mgr, "get_sessions", None)
            maybe_sessions = get_sessions() if callable(get_sessions) else None
            sessions = list(maybe_sessions) if maybe_sessions is not None else []
        except Exception:
            logger.debug("[MEDIA] Failed to enumerate media sessions", exc_info=True)
            sessions = []

        if is_verbose_logging():
            try:
                logger.debug(
                    "[MEDIA] GSMTC sessions: %s",
                    self._session_source_ids_for_log(sessions),
                )
            except Exception:
                logger.debug("[MEDIA] Failed to describe GSMTC sessions", exc_info=True)

        try:
            get_current_session = getattr(mgr, "get_current_session", None)
            current_session = get_current_session() if callable(get_current_session) else None
        except Exception:
            logger.debug("[MEDIA] Failed to read current media session", exc_info=True)
            current_session = None

        if is_verbose_logging():
            logger.debug(
                "[MEDIA] GSMTC current session: %s",
                self._session_source_id_for_log(current_session),
            )

        def _is_playing(session) -> bool:
            try:
                playback_info = session.get_playback_info()
                return self._map_status(playback_info.playback_status) == MediaPlaybackState.PLAYING
            except Exception:
                return False

        def _matching_sessions(provider_id: str) -> list[object]:
            matches: list[object] = []
            if (
                current_session is not None
                and provider_matches_source_app_user_model_id(
                    provider_id,
                    self._session_source_id(current_session),
                )
            ):
                matches.append(current_session)
            for session in sessions:
                if session is current_session:
                    continue
                if provider_matches_source_app_user_model_id(
                    provider_id,
                    self._session_source_id(session),
                ):
                    matches.append(session)
            return matches

        matches_by_provider = {
            provider_id: _matching_sessions(provider_id)
            for provider_id in providers
        }

        # Active playback outranks a stale/paused higher-priority provider.
        # Provider order remains the tie-breaker when more than one source is
        # actively playing.
        for provider_id in providers:
            playing_sessions = [
                session
                for session in matches_by_provider[provider_id]
                if _is_playing(session)
            ]
            if not playing_sessions:
                continue
            if current_session in playing_sessions:
                return provider_id, current_session
            return provider_id, min(
                playing_sessions,
                key=lambda session: self._session_source_id(session).casefold(),
            )

        # Nothing is playing: preserve the original provider-order/current
        # semantics so a paused configured provider remains stable.
        for provider_id in providers:
            matching_sessions = matches_by_provider[provider_id]
            if not matching_sessions:
                continue
            if current_session in matching_sessions:
                return provider_id, current_session
            return provider_id, min(
                matching_sessions,
                key=lambda session: self._session_source_id(session).casefold(),
            )

        if sessions:
            logger.debug(
                "[MEDIA] No %s session among %d GSMTC sessions: %s",
                "/".join(providers),
                len(sessions),
                self._session_source_ids_for_log(sessions),
            )
        else:
            logger.debug("[MEDIA] No %s GSMTC session found (0 sessions)", "/".join(providers))
        return None, None

    def _select_media_session(self, mgr):
        """Compatibility owner for controls and single-provider callers."""

        _provider, session = self._select_media_session_for_providers(
            mgr,
            (self._provider_id,) if self._provider_id is not None else (),
        )
        return session

    def _map_status(self, status) -> MediaPlaybackState:
        try:
            ps = self._PlaybackStatus
            if ps is None:
                return MediaPlaybackState.UNKNOWN
            # Direct enum comparison (works for Spotify)
            if status == ps.PLAYING:
                return MediaPlaybackState.PLAYING
            if status == ps.PAUSED:
                return MediaPlaybackState.PAUSED
            if status == ps.STOPPED:
                return MediaPlaybackState.STOPPED
            # Value/int fallback (MusicBee GSMTC may report as .value or raw int)
            status_val = getattr(status, "value", None)
            if status_val is None:
                try:
                    status_val = int(status)
                except (TypeError, ValueError):
                    status_val = None
            if status_val is not None:
                for member, mapped in (
                    (ps.PLAYING, MediaPlaybackState.PLAYING),
                    (ps.PAUSED, MediaPlaybackState.PAUSED),
                    (ps.STOPPED, MediaPlaybackState.STOPPED),
                ):
                    ref = getattr(member, "value", None)
                    if ref is None:
                        try:
                            ref = int(member)
                        except (TypeError, ValueError):
                            continue
                    if status_val == ref:
                        return mapped
            logger.debug("[MEDIA] Unknown playback status: %r (type=%s)", status, type(status).__name__)
            return MediaPlaybackState.UNKNOWN
        except Exception as _:
            return MediaPlaybackState.UNKNOWN

    @staticmethod
    def _timespan_to_milliseconds(value) -> Optional[int]:
        """Convert a WinRT TimeSpan/timedelta-like value to milliseconds."""

        total_seconds = getattr(value, "total_seconds", None)
        if not callable(total_seconds):
            return None
        try:
            seconds = float(total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(seconds):
            return None
        return int(round(seconds * 1000.0))

    @classmethod
    def _normalize_timeline(cls, timeline) -> tuple[Optional[int], Optional[int]]:
        """Return a bounded relative position/duration pair from GSMTC."""

        if timeline is None:
            return None, None
        start_ms = cls._timespan_to_milliseconds(getattr(timeline, "start_time", None))
        end_ms = cls._timespan_to_milliseconds(getattr(timeline, "end_time", None))
        position_ms = cls._timespan_to_milliseconds(getattr(timeline, "position", None))
        if start_ms is None or end_ms is None or position_ms is None:
            return None, None
        duration_ms = end_ms - start_ms
        if duration_ms <= 0:
            return None, None
        relative_position_ms = max(0, min(duration_ms, position_ms - start_ms))
        return relative_position_ms, duration_ms

    # ------------------------------------------------------------------
    # BaseMediaController API
    # ------------------------------------------------------------------
    def _get_current_track_for_providers(
        self,
        provider_ids: Iterable[str],
        *,
        already_on_io_worker: bool,
    ) -> tuple[Optional[str], Optional[MediaTrackInfo]]:  # pragma: no cover - requires winrt
        if (
            getattr(self, "_retired", False)
            or not self._available
            or self._MediaManager is None
        ):
            return None, None

        providers = tuple(
            provider_id
            for provider_id in (
                normalize_provider_id(value) for value in provider_ids
            )
            if provider_id is not None
        )
        if not providers:
            return None, None

        async def _query():
            mgr = await self._MediaManager.request_async()
            if mgr is None:
                return None

            try:
                selected_provider, session = self._select_media_session_for_providers(
                    mgr,
                    providers,
                )
            except Exception:
                logger.debug(
                    "[MEDIA] Failed to select %s session",
                    "/".join(providers),
                    exc_info=True,
                )
                selected_provider = None
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
            info.source_app_user_model_id = self._session_source_id(session)
            try:
                timeline = session.get_timeline_properties()
                info.position_ms, info.duration_ms = self._normalize_timeline(timeline)
            except Exception:
                logger.debug("[MEDIA] Failed to read timeline properties", exc_info=True)
            if props is not None:
                try:
                    info.title = (props.title or "").strip()[:256]
                    info.artist = (props.artist or "").strip()[:256]
                    info.album = (getattr(props, "album_title", "") or "").strip()[:256]
                    info.album_artist = (getattr(props, "album_artist", "") or "").strip()[:256]
                except Exception as _:
                    if is_verbose_logging():
                        logger.debug("[MEDIA] Failed to normalize media properties", exc_info=True)

            if status is not None:
                info.state = self._map_status(status)

            try:
                if controls is not None:
                    info.can_play_pause = bool(getattr(controls, "is_play_pause_enabled", False))
                    info.can_next = bool(getattr(controls, "is_next_enabled", False))
                    info.can_previous = bool(getattr(controls, "is_previous_enabled", False))
                    info.can_seek = bool(
                        getattr(controls, "is_playback_position_enabled", False)
                    )
            except Exception:
                logger.debug("[MEDIA] Failed to read control capabilities", exc_info=True)

            # Optional album artwork thumbnail
            try:
                thumb_ref = getattr(props, "thumbnail", None)
                if thumb_ref is not None:
                    try:
                        from winrt.windows.storage.streams import DataReader  # type: ignore[import]
                    except Exception:
                        logger.debug("[MEDIA] DataReader import failed")
                        DataReader = None  # type: ignore[assignment]

                    if DataReader is not None:
                        stream = await thumb_ref.open_read_async()
                        if stream is not None:
                            try:
                                size = int(getattr(stream, "size", 0))
                            except Exception:
                                logger.debug("[MEDIA] Failed to get stream size")
                                size = 0
                            if size > 0:
                                max_bytes = 8 * 1024 * 1024
                                requested = min(size, max_bytes)
                                reader = DataReader(stream)
                                loaded = await reader.load_async(requested)
                                actual = int(loaded) if loaded is not None else 0
                                if actual <= 0:
                                    try:
                                        actual = int(getattr(reader, "unconsumed_buffer_length", 0))
                                    except Exception:
                                        actual = 0
                                logger.debug(
                                    "[MEDIA] Thumbnail stream: reported=%d requested=%d loaded=%d",
                                    size, requested, actual,
                                )
                                if actual > 0:
                                    buf = bytearray(actual)
                                    reader.read_bytes(buf)
                                    info.artwork = bytes(buf)
                                else:
                                    logger.debug("[MEDIA] Thumbnail stream loaded 0 bytes (reported size=%d)", size)
                                try:
                                    reader.close()
                                except Exception:
                                    pass
            except Exception:
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

            return selected_provider, info

        import time
        result = self._run_coroutine(
            lambda: _query(),
            already_on_io_worker=already_on_io_worker,
        )
        
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], MediaTrackInfo)
        ):
            selected_provider, info = result
            # Cache only the controller's own provider. A fallback snapshot is
            # handed to the replacement controller after the UI-side switch.
            if selected_provider == self._provider_id:
                self._last_valid_info = info
                self._last_valid_info_ts = time.monotonic()
            return selected_provider, info
        
        # Result is None (timeout or no session)
        # Check if we have cached info within TTL - return it instead of None
        if self._last_valid_info is not None:
            age = time.monotonic() - self._last_valid_info_ts
            if age < self._timeout_cache_ttl:
                logger.debug("[MEDIA] Using cached info (age=%.1fs) after timeout/None", age)
                return self._provider_id, self._last_valid_info
            else:
                # Cache expired - clear it
                logger.debug("[MEDIA] Cached info expired (age=%.1fs > %.1fs TTL)", age, self._timeout_cache_ttl)
                self._last_valid_info = None
        
        return None, None

    def get_current_track(self) -> Optional[MediaTrackInfo]:  # pragma: no cover - requires winrt
        """Return this controller's provider snapshot from any caller thread."""

        _provider, info = self._get_current_track_for_providers(
            (self._provider_id,) if self._provider_id is not None else (),
            already_on_io_worker=False,
        )
        return info

    def get_current_track_from_io_worker(
        self,
        fallback_providers: Iterable[str] = (),
    ) -> tuple[Optional[str], Optional[MediaTrackInfo]]:
        """Query primary and fallback providers once from an owned IO worker.

        This path performs one bounded WinRT request/session enumeration and
        never submits another task to the same executor.
        """

        provider_ids: list[str] = []
        if self._provider_id is not None:
            provider_ids.append(self._provider_id)
        for value in fallback_providers:
            normalized = normalize_provider_id(value)
            if normalized is not None and normalized not in provider_ids:
                provider_ids.append(normalized)
        return self._get_current_track_for_providers(
            provider_ids,
            already_on_io_worker=True,
        )

    def _invoke_simple_action(self, action_name: str, coro_factory) -> None:
        if (
            getattr(self, "_retired", False)
            or not self._available
            or self._MediaManager is None
        ):
            return

        async def _act():
            mgr = await self._MediaManager.request_async()
            if mgr is None:
                return

            # Send controls to the same provider-filtered session that
            # `get_current_track` uses, not whatever
            # `get_current_session()` happens to return.
            try:
                session = self._select_media_session(mgr)
            except Exception:
                logger.debug("[MEDIA] Failed to select %s session for %s", self._app_filter, action_name, exc_info=True)
                session = None
            if session is None:
                return
            try:
                await coro_factory(session)
            except Exception:
                logger.debug("[MEDIA] %s failed", action_name, exc_info=True)

        # Fire-and-forget: the GUI must not block on WinRT completion.
        self._submit_command(action_name, lambda: _act())

    def play_pause(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("play_pause", lambda s: s.try_toggle_play_pause_async())

    def next(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("next", lambda s: s.try_skip_next_async())

    def previous(self) -> None:  # pragma: no cover - requires winrt
        self._invoke_simple_action("previous", lambda s: s.try_skip_previous_async())

    def seek_fraction(self, fraction: float) -> None:  # pragma: no cover - requires winrt
        """Seek the selected provider session without blocking the GUI caller."""

        try:
            parsed_fraction = float(fraction)
        except (TypeError, ValueError):
            return
        if not math.isfinite(parsed_fraction):
            return
        bounded_fraction = max(0.0, min(1.0, parsed_fraction))

        async def _seek(session):
            try:
                timeline = session.get_timeline_properties()
                start_ms = self._timespan_to_milliseconds(
                    getattr(timeline, "start_time", None)
                )
                end_ms = self._timespan_to_milliseconds(
                    getattr(timeline, "end_time", None)
                )
                if start_ms is None or end_ms is None or end_ms <= start_ms:
                    return False
                target_ms = start_ms + int(
                    round((end_ms - start_ms) * bounded_fraction)
                )
                # WinRT playback positions use 100 ns ticks.
                return await session.try_change_playback_position_async(
                    target_ms * 10_000
                )
            except Exception:
                logger.debug("[MEDIA] seek failed", exc_info=True)
                return False

        self._invoke_simple_action("seek", _seek)

    # ------------------------------------------------------------------
    # Process detection (lightweight, no GSMTC overhead)
    # ------------------------------------------------------------------
    def is_app_process_running(self) -> bool:
        """Check if the target media app is running via Windows process snapshot.

        Uses CreateToolhelp32Snapshot (ctypes) — fast, zero-dependency,
        does not touch GSMTC. Safe to call from IO thread.
        """
        process_names = get_provider_process_exe_names(self._provider_id)
        if not process_names:
            return False
        try:
            return _win_any_process_exists(process_names)
        except Exception:
            logger.debug("[MEDIA] Process detection failed", exc_info=True)
            return False


def _win_process_exists(exe_name: str) -> bool:
    """Return True if a process matching *exe_name* (case-insensitive) exists.

    Compatibility wrapper over the one-snapshot multi-name owner.
    """

    return _win_any_process_exists((exe_name,))


def _win_any_process_exists(exe_names: Iterable[str]) -> bool:
    """Return True if any exact process name exists using one Toolhelp snapshot.

    Uses the Windows Toolhelp32 API via ctypes — no external dependencies.
    """
    import ctypes
    import ctypes.wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("cntThreads", ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase", ctypes.wintypes.LONG),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return False

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    targets = {
        str(exe_name).strip().casefold()
        for exe_name in exe_names
        if str(exe_name).strip()
    }
    if not targets:
        kernel32.CloseHandle(snapshot)
        return False

    try:
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
            return False
        while True:
            if pe.szExeFile.casefold() in targets:
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                return False
    finally:
        kernel32.CloseHandle(snapshot)


def create_media_controller(thread_manager=None, app_filter: str = "spotify") -> BaseMediaController:
    """Factory that returns the best available media controller.

    On Windows this prefers the GSMTC-based controller and falls back
    to a NoOp controller when unavailable so that callers never have to
    branch on platform or dependency details.

    Args:
        thread_manager: Engine-owned ThreadManager for async IO.
        app_filter: Registered media-provider id.
    """

    try:
        controller = WindowsGlobalMediaController(thread_manager=thread_manager, app_filter=app_filter)
        if getattr(controller, "_available", False):
            return controller
    except Exception:
        logger.debug("[MEDIA] Failed to initialize WindowsGlobalMediaController", exc_info=True)

    logger.info("[MEDIA] Falling back to NoOpMediaController")
    controller = NoOpMediaController(thread_manager=thread_manager)
    return controller
