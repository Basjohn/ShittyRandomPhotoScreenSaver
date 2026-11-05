"""Linux media controller over MPRIS (D-Bus), the counterpart of Windows GSMTC.

Linux players (Spotify, browsers, most desktop players) publish
``org.mpris.MediaPlayer2.<name>`` on the session bus. This controller fills the
same ``BaseMediaController`` contract as ``WindowsGlobalMediaController``:

* **Provider identity.** Each player's bus-name suffix (``spotify``,
  ``firefox.instance_1_42`` -> ``firefox``, ``chromium.instance123`` -> ``chrome``)
  is matched through ``core.media.provider_registry`` exactly like a GSMTC source
  id, so persisted provider settings mean the same thing on both systems. Among
  matching players a Playing one wins.
* **Queries** run on the caller's IO worker (``get_current_track_from_io_worker``)
  over one locked blocking connection; nothing here owns a cadence or poll.
* **Commands** are fire-and-forget on the owner's media lane (or the IO pool),
  reporting ``MediaCommandResult`` like GSMTC, with the same inflight de-dup.
* **Event observation** listens for ``PropertiesChanged`` on a dedicated
  ThreadManager affinity worker and only hands a reason string to ``on_dirty``.
* **Artwork** comes from ``mpris:artUrl``: ``file://`` read locally, ``http(s)``
  through ``core.network.bounded_request``; bounded size, reused by track identity.

D-Bus transport: ``jeepney`` (pure Python). PySide6's QtDBus cannot demarshal the
``a{sv}`` maps MPRIS uses. When no session bus is reachable the factory returns
the NoOp controller and says so once with ``[PLATFORM]``.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import unquote, urlparse

from core.logging.logger import get_logger
from core.media.media_controller import (
    BaseMediaController,
    MediaCommandResult,
    MediaPlaybackState,
    MediaTrackInfo,
    media_track_identity,
)
from core.media.provider_registry import normalize_provider_id, provider_matches_source_app_user_model_id

logger = get_logger(__name__)

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
_ARTWORK_MAX_BYTES = 4 * 1024 * 1024
_CALL_TIMEOUT_S = 2.0
# MPRIS bus names that differ from the GSMTC host identity the registry matches.
_PLAYER_ALIASES = {
    "chromium": "chrome",
    "google-chrome": "chrome",
    "google_chrome": "chrome",
    "microsoft-edge": "msedge",
    "microsoft_edge": "msedge",
    "brave-browser": "brave",
}
_STATUS = {
    "playing": MediaPlaybackState.PLAYING,
    "paused": MediaPlaybackState.PAUSED,
    "stopped": MediaPlaybackState.STOPPED,
}


def mpris_source_id(bus_name: str) -> str:
    """Return the registry-matchable identity of one MPRIS bus name."""

    base = bus_name[len(MPRIS_PREFIX):] if bus_name.startswith(MPRIS_PREFIX) else bus_name
    base = base.split(".instance", 1)[0].strip().casefold()
    return _PLAYER_ALIASES.get(base, base)


def _unwrap(value):
    """Strip jeepney's ``(signature, value)`` variant tuples recursively."""

    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        return _unwrap(value[1])
    if isinstance(value, dict):
        return {key: _unwrap(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unwrap(item) for item in value]
    return value


class JeepneySessionBus:
    """Blocking session-bus access for MPRIS; one lock serialises the connection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection = None

    def _conn(self):
        if self._connection is None:
            from jeepney.io.blocking import open_dbus_connection

            self._connection = open_dbus_connection(bus="SESSION")
        return self._connection

    def available(self) -> bool:
        try:
            with self._lock:
                self._conn()
            return True
        except Exception as exc:
            logger.info("[MEDIA] MPRIS session bus unavailable: %s", exc)
            return False

    def list_players(self) -> list[str]:
        from jeepney import message_bus, new_method_call

        with self._lock:
            reply = self._conn().send_and_get_reply(new_method_call(message_bus, "ListNames"), timeout=_CALL_TIMEOUT_S)
        return sorted(name for name in reply.body[0] if name.startswith(MPRIS_PREFIX))

    def player_properties(self, bus_name: str) -> dict:
        from jeepney import DBusAddress, new_method_call

        address = DBusAddress(MPRIS_PATH, bus_name=bus_name, interface="org.freedesktop.DBus.Properties")
        with self._lock:
            reply = self._conn().send_and_get_reply(
                new_method_call(address, "GetAll", "s", (PLAYER_INTERFACE,)), timeout=_CALL_TIMEOUT_S
            )
        return _unwrap(reply.body[0])

    def call_player(self, bus_name: str, method: str, signature: str | None = None, args: tuple = ()) -> bool:
        from jeepney import DBusAddress, MessageType, new_method_call

        address = DBusAddress(MPRIS_PATH, bus_name=bus_name, interface=PLAYER_INTERFACE)
        with self._lock:
            reply = self._conn().send_and_get_reply(
                new_method_call(address, method, signature, args), timeout=_CALL_TIMEOUT_S
            )
        return reply.header.message_type == MessageType.method_return

    def listen_for_changes(self, on_change: Callable[[str], None], stop: threading.Event) -> None:
        """Block until *stop*, calling ``on_change(reason)`` for each player property change."""

        from jeepney import MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import open_dbus_connection

        rule = MatchRule(
            type="signal",
            interface="org.freedesktop.DBus.Properties",
            member="PropertiesChanged",
            path=MPRIS_PATH,
        )
        owners = MatchRule(type="signal", interface="org.freedesktop.DBus", member="NameOwnerChanged")
        with open_dbus_connection(bus="SESSION") as connection:
            for match in (rule, owners):
                connection.send_and_get_reply(new_method_call(message_bus, "AddMatch", "s", (match.serialise(),)))
            with connection.filter(rule) as changes, connection.filter(owners) as names:
                while not stop.is_set():
                    try:
                        connection.recv_messages(timeout=0.25)
                    except TimeoutError:
                        continue
                    while changes:
                        message = changes.popleft()
                        if message.body and message.body[0] == PLAYER_INTERFACE:
                            on_change("mpris_properties")
                    while names:
                        message = names.popleft()
                        if message.body and str(message.body[0]).startswith(MPRIS_PREFIX):
                            on_change("mpris_players")


class LinuxMprisMediaController(BaseMediaController):
    """MPRIS implementation of the presentation-neutral media controller."""

    def __init__(self, thread_manager=None, app_filter: str = "spotify", bus=None) -> None:
        super().__init__(thread_manager=thread_manager)
        self._provider_id = normalize_provider_id(app_filter)
        self._bus = bus if bus is not None else JeepneySessionBus()
        self._available = bool(self._bus.available())
        self._selected_bus_name: str | None = None
        self._last_valid_info: MediaTrackInfo | None = None
        self._last_track_id: str | None = None
        self._artwork_cache: tuple[str, bytes | None] | None = None
        self._command_inflight = False
        self._observation_lane = None
        self._observation_stop: threading.Event | None = None
        self._observation_active = False

    # -- queries -------------------------------------------------------
    def _select_player(self, provider_ids: Iterable[str]) -> tuple[str | None, str | None, dict]:
        players = self._bus.list_players()
        for provider_id in provider_ids:
            matched: list[tuple[str, dict]] = []
            for bus_name in players:
                if not provider_matches_source_app_user_model_id(provider_id, mpris_source_id(bus_name)):
                    continue
                try:
                    matched.append((bus_name, self._bus.player_properties(bus_name)))
                except Exception:
                    logger.debug("[MEDIA] MPRIS player %s did not answer", bus_name, exc_info=True)
            if matched:
                playing = [item for item in matched if str(item[1].get("PlaybackStatus", "")).casefold() == "playing"]
                bus_name, properties = (playing or matched)[0]
                return provider_id, bus_name, properties
        return None, None, {}

    def _artwork(self, url: str) -> bytes | None:
        cached = self._artwork_cache
        if cached is not None and cached[0] == url:
            return cached[1]
        data: bytes | None = None
        try:
            parsed = urlparse(url)
            if parsed.scheme == "file":
                path = Path(unquote(parsed.path))
                if path.is_file() and path.stat().st_size <= _ARTWORK_MAX_BYTES:
                    data = path.read_bytes()
            elif parsed.scheme in ("http", "https"):
                from core.network.http import bounded_request

                response = bounded_request(
                    "GET", url, timeout=4.0, stream=True, should_continue=lambda: not self._retired
                )
                try:
                    if response.ok:
                        chunks, size = [], 0
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > _ARTWORK_MAX_BYTES:
                                chunks = []
                                break
                            chunks.append(chunk)
                        data = b"".join(chunks) or None
                finally:
                    response.close()
        except Exception:
            logger.debug("[MEDIA] MPRIS artwork unavailable url=%s", url, exc_info=True)
        self._artwork_cache = (url, data)
        return data

    def _info(self, bus_name: str, properties: dict, reuse_identity) -> MediaTrackInfo:
        metadata = properties.get("Metadata") or {}

        def text(key: str) -> str:
            value = metadata.get(key)
            if isinstance(value, list):
                return ", ".join(str(item) for item in value if item)
            return str(value or "")

        length = metadata.get("mpris:length")
        position = properties.get("Position")
        can_play = bool(properties.get("CanPlay"))
        can_pause = bool(properties.get("CanPause"))
        info = MediaTrackInfo(
            title=text("xesam:title"),
            artist=text("xesam:artist"),
            album=text("xesam:album"),
            album_artist=text("xesam:albumArtist"),
            state=_STATUS.get(str(properties.get("PlaybackStatus", "")).casefold(), MediaPlaybackState.UNKNOWN),
            can_play_pause=can_play or can_pause,
            can_play=can_play,
            can_pause=can_pause,
            can_toggle_play_pause=can_play and can_pause,
            can_next=bool(properties.get("CanGoNext")),
            can_previous=bool(properties.get("CanGoPrevious")),
            can_seek=bool(properties.get("CanSeek")) and isinstance(length, int) and length > 0,
            source_app_user_model_id=mpris_source_id(bus_name),
            position_ms=int(position) // 1000 if isinstance(position, int) else None,
            duration_ms=int(length) // 1000 if isinstance(length, int) and length > 0 else None,
        )
        art_url = text("mpris:artUrl")
        if art_url and media_track_identity(info) != reuse_identity:
            info.artwork = self._artwork(art_url)
        self._last_track_id = str(metadata.get("mpris:trackid") or "") or None
        return info

    def _query(self, provider_ids: list[str], reuse_identity=None) -> tuple[Optional[str], Optional[MediaTrackInfo]]:
        if self._retired or not self._available:
            return None, None
        try:
            provider_id, bus_name, properties = self._select_player(provider_ids)
        except Exception:
            logger.debug("[MEDIA] MPRIS query failed", exc_info=True)
            return None, None
        self._selected_bus_name = bus_name
        if bus_name is None:
            return None, None
        info = self._info(bus_name, properties, reuse_identity)
        self._last_valid_info = info
        return provider_id, info

    def get_current_track(self) -> Optional[MediaTrackInfo]:
        return self._query([self._provider_id] if self._provider_id else [])[1]

    def get_current_track_from_io_worker(
        self,
        fallback_providers: Iterable[str] = (),
        *,
        reuse_artwork_identity: tuple[str, str, str, str, str] | None = None,
    ) -> tuple[Optional[str], Optional[MediaTrackInfo]]:
        provider_ids = [self._provider_id] if self._provider_id else []
        for value in fallback_providers:
            normalized = normalize_provider_id(value)
            if normalized is not None and normalized not in provider_ids:
                provider_ids.append(normalized)
        return self._query(provider_ids, reuse_artwork_identity)

    # -- commands ------------------------------------------------------
    def _submit_command(self, action: str, operation: str, method: str, signature=None, args: tuple = ()) -> bool:
        if self._retired or not self._available or self._command_inflight:
            return False
        result_handler = self._command_result_handler

        def _run() -> None:
            error = ""
            provider_result: bool | None = None
            try:
                bus_name = self._selected_bus_name
                if bus_name is None:
                    self._query([self._provider_id] if self._provider_id else [])
                    bus_name = self._selected_bus_name
                provider_result = bool(bus_name) and self._bus.call_player(bus_name, method, signature, args)
            except Exception as exc:
                error = str(exc)
            finally:
                self._command_inflight = False
            result = MediaCommandResult(
                action=action,
                operation=operation,
                succeeded=provider_result is True,
                provider_result=provider_result,
                error=error,
            )
            level = logger.info if result.succeeded else logger.warning
            level("[MEDIA] MPRIS command action=%s operation=%s result=%r error=%s",
                  action, operation, provider_result, error or "none")
            if callable(result_handler) and not self._retired:
                result_handler(result)

        _run._srpss_runtime_generation = self._runtime_generation
        self._command_inflight = True
        try:
            if self._work_executor is not None:
                submitted = bool(self._work_executor(_run))
            elif self._thread_manager is not None:
                from core.threading.manager import TaskPriority

                self._thread_manager.submit_io_task(
                    _run, task_id=f"media_cmd_{self._task_owner_id}_{action}",
                    priority=TaskPriority.HIGH, category="media_command",
                )
                submitted = True
            else:
                submitted = False
        except Exception:
            logger.debug("[MEDIA] MPRIS command submission failed", exc_info=True)
            submitted = False
        if not submitted:
            self._command_inflight = False
        return submitted

    def play_pause(self, desired_state: MediaPlaybackState | None = None) -> bool:
        info = self._last_valid_info
        if desired_state == MediaPlaybackState.PLAYING and (info is None or info.can_play):
            return self._submit_command("play_pause", "play", "Play")
        if desired_state == MediaPlaybackState.PAUSED and (info is None or info.can_pause):
            return self._submit_command("play_pause", "pause", "Pause")
        return self._submit_command("play_pause", "toggle", "PlayPause")

    def next(self) -> bool:
        return self._submit_command("next", "next", "Next")

    def previous(self) -> bool:
        return self._submit_command("previous", "previous", "Previous")

    def seek_fraction(self, fraction: float) -> bool:
        info = self._last_valid_info
        track_id = self._last_track_id
        if info is None or not info.can_seek or not info.duration_ms or not track_id:
            return False
        position_us = int(max(0.0, min(1.0, float(fraction))) * info.duration_ms * 1000)
        return self._submit_command("seek", "seek", "SetPosition", "ox", (track_id, position_us))

    # -- event observation --------------------------------------------
    def supports_event_observation(self) -> bool:
        return bool(self._available and not self._retired and self._thread_manager is not None)

    def is_event_observation_active(self) -> bool:
        return bool(self._observation_active and not self._retired)

    def start_event_observation(
        self,
        on_dirty: Callable[[str], None],
        on_established: Callable[[bool, str], None] | None = None,
    ) -> bool:
        if not self.supports_event_observation():
            return False
        if self._observation_lane is not None:
            return self._observation_active
        stop = threading.Event()
        try:
            lane = self._thread_manager.create_affinity_lane(
                lane_id=f"media_mpris_observe_{self._task_owner_id}",
                category="media_event_observation",
                runtime_generation=self._runtime_generation,
                owner=self,
                worker="media_mpris_observer",
            )
        except Exception:
            logger.exception("[MEDIA_EVENT] failed to create MPRIS observation lane")
            return False

        def _listen() -> None:
            self._observation_active = True
            if callable(on_established):
                on_established(True, "mpris")
            try:
                self._bus.listen_for_changes(lambda reason: stop.is_set() or on_dirty(reason), stop)
            except Exception as exc:
                logger.warning("[MEDIA_EVENT] MPRIS observation ended: %s", exc)
                if callable(on_established) and not stop.is_set():
                    on_established(False, f"mpris: {exc}")
            finally:
                self._observation_active = False

        self._observation_lane, self._observation_stop = lane, stop
        if not lane.submit(_listen):
            self._observation_lane = self._observation_stop = None
            lane.stop(wait=False)
            return False
        return True

    def stop_event_observation(self) -> None:
        lane, stop = self._observation_lane, self._observation_stop
        self._observation_lane = self._observation_stop = None
        if stop is not None:
            stop.set()
        if lane is not None:
            lane.stop(wait=True, timeout=2.0)


_UNAVAILABLE_ANNOUNCED = False


def create_mpris_controller(thread_manager=None, app_filter: str = "spotify") -> BaseMediaController:
    """Return the MPRIS controller, or the NoOp controller with one loud reason."""

    from core.media.media_controller import NoOpMediaController

    try:
        import jeepney  # noqa: F401
    except ImportError:
        reason = "jeepney is not installed"
    else:
        controller = LinuxMprisMediaController(thread_manager=thread_manager, app_filter=app_filter)
        if controller._available:
            return controller
        reason = "no D-Bus session bus"
    global _UNAVAILABLE_ANNOUNCED
    if not _UNAVAILABLE_ANNOUNCED:
        _UNAVAILABLE_ANNOUNCED = True
        logger.warning("[PLATFORM] Linux media control (MPRIS) unavailable: %s; media widget shows no session", reason)
    return NoOpMediaController(thread_manager=thread_manager)


__all__ = ["JeepneySessionBus", "LinuxMprisMediaController", "create_mpris_controller", "mpris_source_id"]
