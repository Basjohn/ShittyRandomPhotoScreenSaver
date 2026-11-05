"""The single display-power authority: are the console displays on or off?

Nothing else in SRPSS listens for display power. The authority is owned by the
process-scoped ``ScreensaverEngine`` (created in ``initialize``, retired in
``cleanup``), so it outlives every display runtime generation, Settings round trip
and topology rebuild. Consumers subscribe to ``power_changed(on, generation)`` and
query ``is_on`` when a new generation is built.

Event-driven only. A platform backend reports raw states from wherever its system
delivers them (Windows: the GUI thread's message pump; Linux: a D-Bus listener lane);
``deliver`` records the latest state and queues one dispatch onto the authority's
thread. Every state that arrives before that dispatch runs collapses into it
(latest wins), and a dispatch that ends where the authority already is emits
nothing, so an off -> on -> off burst inside one event-loop turn is a single edge
and a burst that returns to the current state is no edge at all. No timer, no
polling, no environment flag.

``generation`` increases by one per emitted edge. A consumer that defers work
compares the generation it was handed with ``generation`` before acting, so a
stale edge can never undo a newer one.

Backends:

* **Windows:** ``core.windows.display_power_notifier`` (``GUID_CONSOLE_DISPLAY_STATE``;
  0 off, 1 on, 2 dimmed, where dimmed counts as on).
* **Linux (basic, not validated on hardware):** GNOME Mutter's
  ``org.gnome.Mutter.DisplayConfig.PowerSaveMode`` over the session bus, watched by
  a blocking ``PropertiesChanged`` listener on a ThreadManager lane (0 on, any other
  value off). Other desktops, or no session bus: the explicit inert backend.
* **Inert:** always reports on, says so once with ``[PLATFORM]``; everything keeps
  running exactly as it did before this authority existed.
"""
from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal

from core.logging.logger import get_logger

logger = get_logger(__name__)


class InertDisplayPowerBackend:
    """No display-power source on this system: the displays always count as on."""

    name = "inert"

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)

    def start(self) -> bool:
        logger.info("[PLATFORM] Display power notifications unavailable (%s); displays always count as on",
                    self.reason)
        return True

    def close(self) -> None:
        return None


MUTTER_BUS_NAME = "org.gnome.Mutter.DisplayConfig"
MUTTER_PATH = "/org/gnome/Mutter/DisplayConfig"
MUTTER_INTERFACE = "org.gnome.Mutter.DisplayConfig"
_DBUS_TIMEOUT_S = 2.0


def mutter_power_save_mode_is_on(value: Any) -> bool | None:
    """Mutter ``PowerSaveMode``: 0 on, 1 standby, 2 suspend, 3 off; -1 (unknown) and junk are None."""

    try:
        mode = int(value)
    except (TypeError, ValueError):
        return None
    if mode < 0:
        return None
    return mode == 0


class LinuxMutterDisplayPowerWatcher:
    """GNOME/Mutter display power over D-Bus: one blocking listener, no wake cadence."""

    name = "linux_mutter_power_save_mode"

    def __init__(self, deliver: Callable[[bool], None], thread_manager: Any) -> None:
        self._deliver = deliver
        self._thread_manager = thread_manager
        self._stop = threading.Event()
        self._lane = None
        self._connection = None

    @staticmethod
    def _properties_address():
        from jeepney import DBusAddress

        return DBusAddress(MUTTER_PATH, bus_name=MUTTER_BUS_NAME, interface="org.freedesktop.DBus.Properties")

    def available(self) -> bool:
        """The session bus answers and Mutter publishes PowerSaveMode."""

        try:
            from jeepney import new_method_call
            from jeepney.io.blocking import open_dbus_connection

            with open_dbus_connection(bus="SESSION") as connection:
                reply = connection.send_and_get_reply(
                    new_method_call(self._properties_address(), "Get", "ss", (MUTTER_INTERFACE, "PowerSaveMode")),
                    timeout=_DBUS_TIMEOUT_S,
                )
            value = reply.body[0][1] if reply.body and isinstance(reply.body[0], tuple) else None
        except Exception as exc:
            logger.info("[DISPLAY_POWER] Mutter PowerSaveMode unavailable: %s", exc)
            return False
        state = mutter_power_save_mode_is_on(value)
        if state is not None:
            self._deliver(state)
        return True

    def start(self) -> bool:
        if self._thread_manager is None:
            return False
        try:
            lane = self._thread_manager.create_affinity_lane(
                lane_id="display_power_mutter_observe",
                category="display_power_observation",
                owner=self,
                worker="display_power_observer",
            )
        except Exception:
            logger.exception("[DISPLAY_POWER] Could not create the Mutter observation lane")
            return False
        self._lane = lane
        if not lane.submit(self._listen):
            self._lane = None
            lane.stop(wait=False)
            return False
        return True

    def _listen(self) -> None:
        from jeepney import MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import open_dbus_connection

        rule = MatchRule(type="signal", interface="org.freedesktop.DBus.Properties",
                         member="PropertiesChanged", path=MUTTER_PATH)
        try:
            with open_dbus_connection(bus="SESSION") as connection:
                self._connection = connection
                if self._stop.is_set():
                    return
                connection.send_and_get_reply(new_method_call(message_bus, "AddMatch", "s", (rule.serialise(),)))
                with connection.filter(rule) as changes:
                    while not self._stop.is_set():
                        try:
                            connection.recv_messages()
                        except (OSError, EOFError, ValueError):
                            if self._stop.is_set():
                                return
                            raise
                        while changes:
                            body = changes.popleft().body
                            if len(body) < 2 or body[0] != MUTTER_INTERFACE:
                                continue
                            changed = body[1].get("PowerSaveMode") if isinstance(body[1], dict) else None
                            value = changed[1] if isinstance(changed, tuple) else changed
                            state = mutter_power_save_mode_is_on(value)
                            if state is not None:
                                self._deliver(state)
        except Exception as exc:
            if not self._stop.is_set():
                logger.warning("[DISPLAY_POWER] Mutter display power observation ended: %s", exc)
        finally:
            self._connection = None

    def close(self) -> None:
        import socket

        self._stop.set()
        connection = self._connection
        if connection is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        lane, self._lane = self._lane, None
        if lane is not None:
            lane.stop(wait=True, timeout=2.0)


def create_display_power_backend(deliver_console_state: Callable[[int], None],
                                 deliver_on: Callable[[bool], None], *, thread_manager: Any = None):
    """Select this platform's backend; unavailable sources become the explicit inert backend."""

    if sys.platform == "win32":
        from core.windows.display_power_notifier import WindowsDisplayPowerNotifier

        return WindowsDisplayPowerNotifier(deliver_console_state)
    if sys.platform.startswith("linux"):
        try:
            import jeepney  # noqa: F401
        except ImportError:
            return InertDisplayPowerBackend("jeepney is not installed")
        watcher = LinuxMutterDisplayPowerWatcher(deliver_on, thread_manager)
        if thread_manager is not None and watcher.available():
            return watcher
        return InertDisplayPowerBackend("no GNOME Mutter PowerSaveMode on the session bus")
    return InertDisplayPowerBackend(f"no display power source for {sys.platform}")


class DisplayPowerAuthority(QObject):
    """Process-scoped console display power truth with coalesced, generation-fenced edges."""

    power_changed = Signal(bool, int)
    _dispatch_requested = Signal()

    def __init__(self, *, backend_factory: Callable[..., Any] | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend_factory = backend_factory or create_display_power_backend
        self._backend = None
        self._lock = threading.Lock()
        self._on = True
        self._pending: bool | None = None
        self._dispatch_queued = False
        self._generation = 0
        self._coalesced = 0
        self._started = False
        self._retired = False
        # Explicitly queued even for same-thread delivery: the Windows window
        # procedure runs inside the GUI pump and must not re-enter consumers.
        self._dispatch_requested.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def backend_name(self) -> str:
        return str(getattr(self._backend, "name", "none"))

    @property
    def backend(self) -> Any:
        return self._backend

    def start(self, *, thread_manager: Any = None) -> bool:
        """Create and start the platform backend once (GUI thread)."""

        if self._retired:
            raise RuntimeError("display power authority is retired")
        if self._started:
            return True
        backend = self._backend_factory(self.deliver_console_state, self.deliver, thread_manager=thread_manager)
        try:
            started = bool(backend.start())
        except Exception:
            logger.exception("[DISPLAY_POWER] Backend %s failed to start",
                             getattr(backend, "name", type(backend).__name__))
            started = False
        if not started:
            try:
                backend.close()
            except Exception:
                logger.debug("[DISPLAY_POWER] Failed backend close raised", exc_info=True)
            backend = InertDisplayPowerBackend("the platform source could not be registered")
            backend.start()
        self._backend = backend
        self._started = True
        logger.info("[DISPLAY_POWER] Authority started backend=%s", self.backend_name)
        return True

    def deliver_console_state(self, state: int) -> None:
        """A raw console display state (Windows numbering): 0 off, 1 on, 2 dimmed (counts as on)."""

        self.deliver(int(state) != 0)

    def deliver(self, on: bool) -> None:
        """Record the latest state from any thread and queue one dispatch for it."""

        with self._lock:
            if self._retired:
                return
            self._pending = bool(on)
            if self._dispatch_queued:
                self._coalesced += 1
                return
            self._dispatch_queued = True
        self._dispatch_requested.emit()

    def _dispatch(self) -> None:
        with self._lock:
            self._dispatch_queued = False
            state, self._pending = self._pending, None
            if self._retired or state is None:
                return
            if state == self._on:
                self._coalesced += 1
                return
            self._on = state
            self._generation += 1
            generation = self._generation
        logger.info("[DISPLAY_POWER] Displays %s (generation=%d backend=%s)",
                    "ON" if state else "OFF", generation, self.backend_name)
        self.power_changed.emit(state, generation)

    def retire(self) -> None:
        """Unregister the platform source; later deliveries are ignored."""

        with self._lock:
            if self._retired:
                return
            self._retired = True
            self._pending = None
        backend, self._backend = self._backend, None
        if backend is not None:
            try:
                backend.close()
            except Exception:
                logger.exception("[DISPLAY_POWER] Backend close failed")
        logger.info("[DISPLAY_POWER] Authority retired")

    @property
    def is_retired(self) -> bool:
        return self._retired

    def describe(self) -> dict[str, Any]:
        return {"on": self._on, "generation": self._generation, "backend": self.backend_name,
                "coalesced": self._coalesced, "retired": self._retired}


__all__ = [
    "DisplayPowerAuthority",
    "InertDisplayPowerBackend",
    "LinuxMutterDisplayPowerWatcher",
    "create_display_power_backend",
    "mutter_power_save_mode_is_on",
]
