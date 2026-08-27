"""Shared presentation-neutral Gmail runtime ownership (Phase E1 slice 7).

``GmailBackend.instance()`` remains the process-wide backend/auth authority.  A
screensaver runtime may create one Gmail presenter per display, but those
presenters must not each bootstrap that singleton, read/write the same cache,
poll the same inbox, decide the same notification, or dispatch duplicate
message actions.

``GmailRuntimeService`` is the per-display lease stored by that display's
``WidgetRuntimeManager``.  Production leases in one runtime generation join one
``_SharedGmailRuntimeOwner``. Directly constructed isolated services remain
available for focused backend/runtime tests.

The owner deliberately contains no QWidget, QPixmap, layout, transition, menu,
or hit-testing code.  Presenters receive immutable raw-email snapshots and own
their independent visible projections.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
import threading
import time
import weakref
from typing import Any, Mapping

from core.audio.sound_paths import default_notification_sound_path
from core.gmail.gmail_backend import GmailBackend, GmailBackendMode
from core.gmail.gmail_client import EmailMetadata, GmailFetchCancelled, GmailLabel
from core.gmail.gmail_preparation import (
    PreparedGmailStartup,
    load_gmail_startup_snapshot,
    reserve_gmail_cache_write,
    write_gmail_email_cache,
)
from core.logging.logger import get_logger
from core.performance import record_widget_timer_result
from core.runtime_flags import automatic_service_updates_enabled
from core.settings.storage_paths import resolve_app_data_dir
from core.settings.widget_capacity_policy import LIST_WIDGET_MAX_CAPACITY
from core.threading.manager import ThreadManager
from widgets.overlay_timers import OverlayTimerHandle, create_overlay_timer
from widgets.service_widget_runtime import get_automatic_startup_refresh_decision

logger = get_logger(__name__)


CACHE_MAX_AGE_HOURS = 24 * 14
CACHE_DIR = resolve_app_data_dir() / "cache"
CACHE_PATH = CACHE_DIR / "gmail_cache.json"


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value)


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


@dataclass(frozen=True)
class GmailRuntimeConfig:
    """Presentation-neutral Gmail cadence/cache/notification configuration."""

    refresh_minutes: int = 5
    fetch_window_capacity: int = LIST_WIDGET_MAX_CAPACITY
    filter_label: str = GmailLabel.INBOX.value
    play_sound_on_new_mail: bool = False
    sound_file_path: str = field(default_factory=default_notification_sound_path)
    sound_volume_percent: int = 50
    cache_path: Path = CACHE_PATH

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "GmailRuntimeConfig":
        config = value if isinstance(value, Mapping) else {}
        return cls(
            refresh_minutes=_bounded_int(
                config.get("refresh_minutes", 5), 5, 1, 24 * 60
            ),
            # Fetching a stable shared window keeps presenter limit changes from
            # changing provider I/O cardinality.
            fetch_window_capacity=LIST_WIDGET_MAX_CAPACITY,
            filter_label=str(config.get("filter_label", GmailLabel.INBOX.value)),
            play_sound_on_new_mail=_to_bool(
                config.get("play_sound_on_new_mail", False), False
            ),
            sound_file_path=str(
                config.get("sound_file_path", default_notification_sound_path()) or ""
            ),
            sound_volume_percent=_bounded_int(
                config.get("sound_volume_percent", 50), 50, 0, 100
            ),
            cache_path=CACHE_PATH,
        )

    def normalized(self) -> "GmailRuntimeConfig":
        return replace(
            self,
            refresh_minutes=_bounded_int(self.refresh_minutes, 5, 1, 24 * 60),
            fetch_window_capacity=_bounded_int(
                self.fetch_window_capacity,
                LIST_WIDGET_MAX_CAPACITY,
                1,
                LIST_WIDGET_MAX_CAPACITY,
            ),
            filter_label=str(self.filter_label or GmailLabel.INBOX.value),
            play_sound_on_new_mail=bool(self.play_sound_on_new_mail),
            sound_file_path=str(self.sound_file_path or ""),
            sound_volume_percent=_bounded_int(
                self.sound_volume_percent, 50, 0, 100
            ),
            cache_path=Path(self.cache_path),
        )


@dataclass(frozen=True)
class GmailRuntimeSnapshot:
    """One coherent accepted Gmail model revision for every presenter."""

    revision: int
    emails: tuple[EmailMetadata, ...]
    unread_count: int
    error: str | None
    refreshing: bool
    source: str


_SHARED_GMAIL_OWNERS: dict[tuple[str, object], "_SharedGmailRuntimeOwner"] = {}


def _shared_owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    if runtime_generation is not None:
        return ("runtime", runtime_generation)
    return ("thread_manager", id(thread_manager))


def _drop_shared_owner(
    key: tuple[str, object], owner: "_SharedGmailRuntimeOwner"
) -> None:
    if _SHARED_GMAIL_OWNERS.get(key) is owner:
        _SHARED_GMAIL_OWNERS.pop(key, None)


def shared_gmail_owner_count() -> int:
    """Read-only diagnostic used by focused cardinality regressions."""

    return len(_SHARED_GMAIL_OWNERS)


def reset_shared_gmail_runtime_for_tests() -> None:
    """Retire shared Gmail owners without resetting the backend singleton."""

    for owner in list(_SHARED_GMAIL_OWNERS.values()):
        owner.retire()
    _SHARED_GMAIL_OWNERS.clear()


class _SharedGmailRuntimeOwner:
    """One runtime-generation Gmail cadence/model/action authority."""

    def __init__(
        self,
        *,
        config: GmailRuntimeConfig,
        thread_manager: Any,
        runtime_generation: Any,
        backend: GmailBackend | Any | None = None,
        registry_key: tuple[str, object] | None = None,
    ) -> None:
        self._config = config.normalized()
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._backend = backend if backend is not None else GmailBackend.instance()
        self._registry_key = registry_key

        self._leases: weakref.WeakSet[GmailRuntimeService] = weakref.WeakSet()
        self._active_leases: weakref.WeakSet[GmailRuntimeService] = weakref.WeakSet()
        self._running = False
        self._retired = False

        self._owner_generation = 0
        self._backend_request_id = 0
        self._backend_initializing = False
        self._backend_ready = bool(getattr(self._backend, "is_initialized", False))
        self._pending_fetch_after_backend_ready = False

        self._fetch_lock = threading.Lock()
        self._fetch_in_progress = False
        self._fetch_request_id = 0
        self._startup_cache_request_id = 0
        self._content_revision = 0

        self._action_in_progress = False
        self._action_request_id = 0

        self._update_timer_handle: OverlayTimerHandle | None = None

        self._emails: tuple[EmailMetadata, ...] = ()
        self._unread_count = 0
        self._last_error: str | None = None
        self._has_valid_data = False
        self._refreshing = False
        self._revision = 0
        self._last_source = "initial"

        self._seen_message_ids: set[str] = set()
        self._seen_initialised = False

    # ------------------------------------------------------------------
    # Diagnostics / accepted model
    # ------------------------------------------------------------------
    @property
    def config(self) -> GmailRuntimeConfig:
        return self._config

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    @property
    def fetch_request_id(self) -> int:
        return self._fetch_request_id

    @property
    def backend_request_id(self) -> int:
        return self._backend_request_id

    @property
    def backend_ready(self) -> bool:
        return self._backend_ready

    @property
    def refresh_in_progress(self) -> bool:
        return self._fetch_in_progress

    @property
    def action_in_progress(self) -> bool:
        return self._action_in_progress

    @property
    def update_timer_handle(self) -> OverlayTimerHandle | None:
        return self._update_timer_handle

    @property
    def backend_mode(self) -> GmailBackendMode | Any:
        return getattr(self._backend, "mode", GmailBackendMode.OAUTH)

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    def active_consumer_count(self) -> int:
        return sum(1 for lease in list(self._active_leases) if lease._consumer_alive())

    def attached_consumer_count(self) -> int:
        return sum(1 for lease in list(self._leases) if lease._consumer_alive())

    def current_snapshot(self) -> GmailRuntimeSnapshot | None:
        if self._revision <= 0:
            return None
        return GmailRuntimeSnapshot(
            revision=self._revision,
            emails=self._emails,
            unread_count=self._unread_count,
            error=self._last_error,
            refreshing=self._refreshing,
            source=self._last_source,
        )

    # ------------------------------------------------------------------
    # Consumer accounting
    # ------------------------------------------------------------------
    def attach(self, lease: "GmailRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to a retired Gmail owner")
        if self._thread_manager is None and lease._thread_manager is not None:
            self._thread_manager = lease._thread_manager
        elif (
            lease._thread_manager is not None
            and self._thread_manager is not None
            and lease._thread_manager is not self._thread_manager
        ):
            raise RuntimeError("shared Gmail consumers must use one ThreadManager")
        if (
            self._runtime_generation is not None
            and lease.runtime_generation is not None
            and lease.runtime_generation != self._runtime_generation
        ):
            raise RuntimeError("shared Gmail consumer runtime generation mismatch")
        if lease.config != self._config:
            logger.warning(
                "[GMAIL_RUNTIME] Joining shared owner with non-canonical duplicate config; "
                "the first runtime-generation config remains authoritative"
            )
        self._leases.add(lease)

    def detach(self, lease: "GmailRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not list(self._leases):
            self.retire()

    def activate(self, lease: "GmailRuntimeService") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active_leases.add(lease)
        if self._running:
            snapshot = self.current_snapshot()
            if snapshot is not None:
                lease._deliver_snapshot(snapshot)
            return True
        if self._thread_manager is None:
            logger.error("[GMAIL_RUNTIME] Cannot start without ThreadManager")
            self._active_leases.discard(lease)
            return False

        try:
            self._running = True
            self._owner_generation += 1
            self._backend_ready = bool(
                getattr(self._backend, "is_initialized", False)
            )
            if automatic_service_updates_enabled():
                self._start_poll_timer()
                if self._update_timer_handle is None:
                    raise RuntimeError("Gmail poll timer was not created")
            else:
                logger.info(
                    "[GMAIL] Automatic updates disabled via --noupdates; manual refresh only"
                )

            snapshot = self.current_snapshot()
            if snapshot is not None:
                self._broadcast_snapshot(snapshot)
            self._begin_backend_initialization()
            self._begin_startup_cache_load()
            return True
        except Exception:
            self._active_leases.discard(lease)
            self.stop()
            logger.error(
                "[GMAIL_RUNTIME] Shared owner activation failed closed",
                exc_info=True,
            )
            return False

    def deactivate(self, lease: "GmailRuntimeService") -> None:
        self._active_leases.discard(lease)
        if not list(self._active_leases):
            self.stop()

    # ------------------------------------------------------------------
    # Timer/bootstrap/startup cache
    # ------------------------------------------------------------------
    def _start_poll_timer(self) -> None:
        self._stop_poll_timer()
        interval_ms = int(self._config.refresh_minutes * 60 * 1000)
        self._update_timer_handle = create_overlay_timer(
            self,
            interval_ms,
            self.refresh,
            description="gmail_refresh",
        )

    def _stop_poll_timer(self) -> None:
        handle = self._update_timer_handle
        self._update_timer_handle = None
        if handle is not None:
            handle.stop()

    def _begin_backend_initialization(self) -> None:
        if self._retired or not self._running or self._backend_initializing:
            return
        if bool(getattr(self._backend, "is_initialized", False)):
            self._backend_ready = True
            if self._pending_fetch_after_backend_ready:
                self._pending_fetch_after_backend_ready = False
                self.refresh()
            return

        self._backend_initializing = True
        self._backend_request_id += 1
        request_id = self._backend_request_id
        owner_generation = self._owner_generation
        owner_ref = weakref.ref(self)

        def _ready(success: bool) -> None:
            owner = owner_ref()
            if owner is not None:
                owner._commit_backend_initialization(
                    owner_generation, request_id, bool(success)
                )

        _ready._srpss_runtime_generation = self._runtime_generation
        try:
            admitted = self._backend.ensure_initialized(self._thread_manager, _ready)
        except Exception:
            admitted = False
            logger.error("[GMAIL_RUNTIME] Backend bootstrap dispatch failed", exc_info=True)
        if not admitted:
            self._backend_initializing = False

    def _commit_backend_initialization(
        self, owner_generation: int, request_id: int, success: bool
    ) -> None:
        if not self._accepts(owner_generation) or request_id != self._backend_request_id:
            return
        self._backend_initializing = False
        self._backend_ready = bool(
            success and getattr(self._backend, "is_initialized", False)
        )
        if not self._backend_ready:
            logger.warning("[GMAIL_RUNTIME] Backend bootstrap did not complete")
            return
        if self._pending_fetch_after_backend_ready:
            self._pending_fetch_after_backend_ready = False
            self.refresh()

    def _begin_startup_cache_load(self) -> None:
        if self._retired or not self._running or self._thread_manager is None:
            return
        self._startup_cache_request_id += 1
        request_id = self._startup_cache_request_id
        content_revision = self._content_revision
        owner_generation = self._owner_generation
        cache_path = self._config.cache_path
        owner_ref = weakref.ref(self)

        def _load_snapshot() -> PreparedGmailStartup:
            return load_gmail_startup_snapshot(
                cache_path,
                max_age_hours=CACHE_MAX_AGE_HOURS,
            )

        _load_snapshot._srpss_runtime_generation = self._runtime_generation

        def _on_result(result: Any) -> None:
            snapshot: PreparedGmailStartup | None = None
            error: str | None = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedGmailStartup):
                    snapshot = candidate
                else:
                    error = "No Gmail startup snapshot returned"
            else:
                error = str(
                    getattr(result, "error", None)
                    or "Gmail startup cache load failed"
                )

            def _deliver() -> None:
                owner = owner_ref()
                if owner is None:
                    return
                if snapshot is not None:
                    owner._commit_startup_cache(
                        owner_generation,
                        request_id,
                        content_revision,
                        snapshot,
                    )
                else:
                    owner._commit_startup_cache_error(
                        owner_generation,
                        request_id,
                        content_revision,
                        str(error),
                    )

            _deliver._srpss_runtime_generation = self._runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(
                _load_snapshot,
                callback=_on_result,
                category="gmail_startup_cache",
            )
        except Exception as exc:
            self._commit_startup_cache_error(
                owner_generation,
                request_id,
                content_revision,
                str(exc),
            )

    def _commit_startup_cache(
        self,
        owner_generation: int,
        request_id: int,
        content_revision: int,
        snapshot: PreparedGmailStartup,
    ) -> None:
        if (
            not self._accepts(owner_generation)
            or request_id != self._startup_cache_request_id
            or content_revision != self._content_revision
        ):
            return
        if snapshot.emails:
            self._emails = tuple(snapshot.emails)
            self._unread_count = sum(1 for email in self._emails if email.is_unread)
            self._last_error = None
            self._has_valid_data = True
            self._publish("cache")
            logger.info("[GMAIL] Loaded %d cached emails", len(self._emails))
        elif snapshot.state == "stale":
            logger.debug(
                "[GMAIL] Cache stale (>%dh), ignoring", CACHE_MAX_AGE_HOURS
            )
        self._complete_startup_refresh(snapshot.cache_timestamp)

    def _commit_startup_cache_error(
        self,
        owner_generation: int,
        request_id: int,
        content_revision: int,
        error: str,
    ) -> None:
        if (
            not self._accepts(owner_generation)
            or request_id != self._startup_cache_request_id
            or content_revision != self._content_revision
        ):
            return
        logger.warning("[CACHE][GMAIL] Startup cache snapshot failed: %s", error)
        self._complete_startup_refresh(None)

    def _complete_startup_refresh(self, cache_timestamp: datetime | None) -> None:
        if not automatic_service_updates_enabled():
            return
        decision = get_automatic_startup_refresh_decision(
            cache_timestamp=cache_timestamp
        )
        logger.info(
            "[CACHE][GMAIL] Startup refresh %s (%s%s)",
            "allowed" if decision.run else "skipped",
            decision.reason,
            (
                f", cache_age_s={decision.age.total_seconds():.1f}"
                if decision.age is not None
                else ""
            ),
        )
        if decision.run:
            self.refresh()

    # ------------------------------------------------------------------
    # Fetch / accepted state
    # ------------------------------------------------------------------
    def refresh(self) -> bool:
        started = time.perf_counter()
        try:
            if self._retired or not self._running:
                return False
            if not self._backend_ready or not bool(
                getattr(self._backend, "is_initialized", False)
            ):
                self._pending_fetch_after_backend_ready = True
                self._begin_backend_initialization()
                return True
            with self._fetch_lock:
                if self._fetch_in_progress:
                    logger.debug("[GMAIL] Fetch already in progress, skipping")
                    return False
                self._fetch_in_progress = True
                self._fetch_request_id += 1
                request_id = self._fetch_request_id

            owner_generation = self._owner_generation
            self._set_refreshing(True, source="refreshing")
            client = (
                self._backend.client
                if bool(getattr(self._backend, "is_authenticated", False))
                else None
            )
            if client is None:
                self._end_fetch(request_id)
                self._refreshing = False
                # Authentication is an actionable state, unlike a transient
                # network error, and historically replaces cached pixels.
                self._last_error = "auth"
                self._publish("auth")
                return False

            def _fetch() -> None:
                self._fetch_emails_async(
                    client, owner_generation, request_id
                )

            _fetch._srpss_runtime_generation = self._runtime_generation
            try:
                self._thread_manager.submit_io_task(
                    _fetch,
                    category="gmail_fetch",
                )
            except Exception as exc:
                self._end_fetch(request_id)
                self._refreshing = False
                logger.error(
                    "[GMAIL] Fetch IO dispatch failed; request dropped: %s", exc
                )
                self._publish("dispatch_error")
                return False
            return True
        finally:
            record_widget_timer_result(
                "GmailRuntime",
                "gmail.refresh.dispatch",
                (time.perf_counter() - started) * 1000.0,
                None,
            )

    def _fetch_is_retired(self, owner_generation: int, request_id: int) -> bool:
        return bool(
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or request_id != self._fetch_request_id
        )

    def _fetch_emails_async(
        self, client: Any, owner_generation: int, request_id: int
    ) -> None:
        try:
            if self._fetch_is_retired(owner_generation, request_id):
                return
            try:
                emails = client.list_messages(
                    max_results=self._config.fetch_window_capacity,
                    label_ids=[self._config.filter_label],
                    should_cancel=lambda: self._fetch_is_retired(
                        owner_generation, request_id
                    ),
                )
            except TypeError as exc:
                if "should_cancel" not in str(exc):
                    raise
                logger.warning(
                    "[GMAIL_RUNTIME][COMPAT] Client lacks cancellation seam; "
                    "using generation-fenced network compatibility path"
                )
                emails = self._fetch_emails_async_uncancellable(
                    client, owner_generation, request_id
                )
                if emails is None:
                    return
            if self._fetch_is_retired(owner_generation, request_id):
                return
            accepted = tuple(emails)
            unread = sum(1 for email in accepted if email.is_unread)
            owner_ref = weakref.ref(self)

            def _deliver() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._commit_fetch(
                        owner_generation, request_id, accepted, unread
                    )

            _deliver._srpss_runtime_generation = self._runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)
        except GmailFetchCancelled:
            logger.debug(
                "[GMAIL_RUNTIME] Fetch abandoned for retired generation=%s request=%s",
                owner_generation,
                request_id,
            )
        except Exception as exc:
            logger.error("[GMAIL] Fetch failed: %s", exc)
            error_message = str(exc)
            owner_ref = weakref.ref(self)

            def _deliver_error() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._commit_fetch_error(
                        owner_generation, request_id, error_message
                    )

            _deliver_error._srpss_runtime_generation = self._runtime_generation
            try:
                ThreadManager.run_on_ui_thread(_deliver_error)
            except Exception:
                logger.critical(
                    "[GMAIL_RUNTIME] run_on_ui_thread failed, dropping fetch error"
                )
        finally:
            self._end_fetch(request_id)

    def _fetch_emails_async_uncancellable(
        self, client: Any, owner_generation: int, request_id: int
    ) -> tuple[EmailMetadata, ...] | None:
        if self._fetch_is_retired(owner_generation, request_id):
            return None
        emails = tuple(
            client.list_messages(
                max_results=self._config.fetch_window_capacity,
                label_ids=[self._config.filter_label],
            )
        )
        if self._fetch_is_retired(owner_generation, request_id):
            return None
        return emails

    def _end_fetch(self, request_id: int) -> None:
        with self._fetch_lock:
            if request_id == self._fetch_request_id:
                self._fetch_in_progress = False

    def _commit_fetch(
        self,
        owner_generation: int,
        request_id: int,
        emails: tuple[EmailMetadata, ...],
        unread_count: int,
    ) -> None:
        if not self._accepts_fetch(owner_generation, request_id):
            return
        self._refreshing = False
        if (
            self._has_valid_data
            and not emails
        ):
            logger.warning(
                "[GMAIL] Empty fetch result received; keeping cached/displayed content visible"
            )
            self._publish("empty_fallback")
            return
        if (
            self._has_valid_data
            and self._last_error is None
            and emails == self._emails
            and unread_count == self._unread_count
        ):
            logger.debug(
                "[GMAIL] Fetched mail unchanged; skipping cache write and content repaint"
            )
            self._publish("unchanged")
            return

        self._content_revision += 1
        self._startup_cache_request_id += 1
        self._emails = emails
        self._unread_count = int(unread_count)
        self._last_error = None
        self._detect_new_mail(emails)
        if emails:
            self._has_valid_data = True
            self._write_email_cache_deferred(emails)
        self._publish("live")

    def _commit_fetch_error(
        self, owner_generation: int, request_id: int, error: str
    ) -> None:
        if not self._accepts_fetch(owner_generation, request_id):
            return
        self._refreshing = False
        if self._has_valid_data and self._emails:
            logger.warning(
                "[GMAIL] Fetch failed but keeping cached/displayed content visible: %s",
                error,
            )
            self._publish("error_fallback")
            return
        self._last_error = str(error)
        logger.warning("[GMAIL] Displaying error state: %s", error)
        self._publish("error")

    def _accepts(self, owner_generation: int) -> bool:
        return bool(
            not self._retired
            and self._running
            and owner_generation == self._owner_generation
        )

    def _accepts_fetch(self, owner_generation: int, request_id: int) -> bool:
        return self._accepts(owner_generation) and request_id == self._fetch_request_id

    def _set_refreshing(self, value: bool, *, source: str) -> None:
        value = bool(value)
        if value == self._refreshing:
            return
        self._refreshing = value
        self._publish(source)

    def _publish(self, source: str) -> GmailRuntimeSnapshot:
        self._revision += 1
        self._last_source = str(source)
        snapshot = GmailRuntimeSnapshot(
            revision=self._revision,
            emails=self._emails,
            unread_count=self._unread_count,
            error=self._last_error,
            refreshing=self._refreshing,
            source=self._last_source,
        )
        self._broadcast_snapshot(snapshot)
        return snapshot

    def _broadcast_snapshot(self, snapshot: GmailRuntimeSnapshot) -> None:
        for lease in list(self._active_leases):
            lease._deliver_snapshot(snapshot)

    # ------------------------------------------------------------------
    # Cache persistence / notification / actions
    # ------------------------------------------------------------------
    def _write_email_cache_deferred(
        self, emails: tuple[EmailMetadata, ...]
    ) -> None:
        if self._thread_manager is None:
            logger.warning(
                "[GMAIL] Cache persistence skipped because shared I/O dispatch was unavailable"
            )
            return
        cache_path = self._config.cache_path
        cache_emails = tuple(emails)
        runtime_generation = self._runtime_generation
        try:
            write_id = reserve_gmail_cache_write(cache_path)
        except Exception as exc:
            logger.warning("[GMAIL] Cache persistence reservation failed: %s", exc)
            return

        def _persist() -> None:
            started = time.perf_counter()
            try:
                write_gmail_email_cache(
                    cache_path,
                    cache_emails,
                    write_id=write_id,
                )
            finally:
                record_widget_timer_result(
                    "GmailRuntime",
                    "gmail.cache.write",
                    (time.perf_counter() - started) * 1000.0,
                    None,
                )

        # Accepted persistence is intentionally detached from leases: once
        # reserved it may finish after the last presenter retires.
        _persist._srpss_runtime_generation = runtime_generation
        try:
            self._thread_manager.submit_io_task(
                _persist,
                category="gmail_cache_persist",
            )
        except Exception as exc:
            logger.warning("[GMAIL] Cache persistence dispatch failed: %s", exc)

    def _detect_new_mail(self, emails: tuple[EmailMetadata, ...]) -> None:
        current_unread_ids = {
            email.id for email in emails if getattr(email, "is_unread", False)
        }
        if not self._seen_initialised:
            self._seen_message_ids = current_unread_ids
            self._seen_initialised = True
            return
        new_ids = current_unread_ids - self._seen_message_ids
        self._seen_message_ids = current_unread_ids
        if not new_ids or not self._config.play_sound_on_new_mail:
            return
        try:
            from core.audio.notification_sound import NotificationSoundPlayer

            player = NotificationSoundPlayer.instance()
            if player.file_path != self._config.sound_file_path:
                player.set_file_path(self._config.sound_file_path)
            if player.volume_percent != self._config.sound_volume_percent:
                player.set_volume(self._config.sound_volume_percent)
            player.play()
            logger.info(
                "[GMAIL] New mail detected (%d new) - sound played", len(new_ids)
            )
        except Exception as exc:
            logger.warning("[GMAIL] Notification sound failed: %s", exc)

    def dispatch_action(self, action: str, message_id: str) -> bool:
        if self._retired or not self._running or self._action_in_progress:
            if self._action_in_progress:
                logger.debug("[GMAIL_RUNTIME] Action already in progress; ignoring duplicate")
            return False
        client = (
            self._backend.client
            if bool(getattr(self._backend, "is_authenticated", False))
            else None
        )
        if client is None or self._thread_manager is None:
            return False
        method_name = {
            "mark_read": "mark_as_read",
            "mark_unread": "mark_as_unread",
            "archive": "archive_message",
            "spam": "spam_message",
            "trash": "trash_message",
        }.get(str(action))
        method = getattr(client, method_name, None) if method_name is not None else None
        if not callable(method):
            logger.warning("[GMAIL_RUNTIME] Unsupported action: %s", action)
            return False

        self._action_in_progress = True
        self._action_request_id += 1
        request_id = self._action_request_id
        owner_generation = self._owner_generation
        owner_ref = weakref.ref(self)

        def _execute() -> None:
            success = False
            error: str | None = None
            try:
                success = bool(method(message_id))
            except Exception as exc:
                error = str(exc)

            def _deliver() -> None:
                owner = owner_ref()
                if owner is not None:
                    owner._commit_action(
                        owner_generation,
                        request_id,
                        str(action),
                        str(message_id),
                        success,
                        error,
                    )

            _deliver._srpss_runtime_generation = self._runtime_generation
            try:
                admitted = ThreadManager.run_on_ui_thread(_deliver)
            except Exception:
                logger.critical(
                    "[GMAIL_RUNTIME] run_on_ui_thread failed, dropping action completion"
                )
                owner = owner_ref()
                if owner is not None:
                    owner._release_dropped_action(owner_generation, request_id)
            else:
                if admitted is False:
                    logger.critical(
                        "[GMAIL_RUNTIME] UI dispatcher declined action completion"
                    )
                    owner = owner_ref()
                    if owner is not None:
                        owner._release_dropped_action(owner_generation, request_id)

        _execute._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(
                _execute,
                category="gmail_action",
            )
            return True
        except Exception as exc:
            self._action_in_progress = False
            logger.error("[GMAIL_RUNTIME] Action dispatch failed: %s", exc)
            return False

    def _commit_action(
        self,
        owner_generation: int,
        request_id: int,
        action: str,
        message_id: str,
        success: bool,
        error: str | None,
    ) -> None:
        if (
            not self._accepts(owner_generation)
            or request_id != self._action_request_id
        ):
            return
        self._action_in_progress = False
        if not success:
            logger.warning(
                "[GMAIL_RUNTIME] Action %s failed for %s%s",
                action,
                message_id,
                f": {error}" if error else "",
            )
            return
        logger.info("[GMAIL_RUNTIME] Action %s completed for %s", action, message_id)
        self.refresh()

    def _release_dropped_action(
        self, owner_generation: int, request_id: int
    ) -> None:
        """Release serialization when the UI dispatcher rejects completion."""

        if (
            self._accepts(owner_generation)
            and request_id == self._action_request_id
        ):
            self._action_in_progress = False

    def start_auth_flow(self) -> bool:
        try:
            return bool(self._backend.start_oauth_flow())
        except Exception:
            logger.error("[GMAIL] Auth flow failed", exc_info=True)
            return False

    def open_message_in_browser(self, message_id: str) -> bool:
        client = (
            self._backend.client
            if bool(getattr(self._backend, "is_authenticated", False))
            else None
        )
        opener = getattr(client, "open_message_in_browser", None)
        if not callable(opener):
            return False
        try:
            opener(message_id)
            return True
        except Exception:
            logger.debug("[GMAIL_RUNTIME] Message open failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Configuration / retirement
    # ------------------------------------------------------------------
    def configure(self, config: GmailRuntimeConfig) -> None:
        if self._retired:
            return
        normalized = config.normalized()
        old = self._config
        self._config = normalized
        if self._running and old.refresh_minutes != normalized.refresh_minutes:
            if automatic_service_updates_enabled():
                self._start_poll_timer()
            else:
                self._stop_poll_timer()

    def stop(self) -> None:
        if not self._running and self._update_timer_handle is None:
            return
        self._running = False
        self._owner_generation += 1
        self._backend_request_id += 1
        self._startup_cache_request_id += 1
        self._fetch_request_id += 1
        self._action_request_id += 1
        self._backend_initializing = False
        self._backend_ready = False
        self._pending_fetch_after_backend_ready = False
        with self._fetch_lock:
            self._fetch_in_progress = False
        self._action_in_progress = False
        self._refreshing = False
        self._stop_poll_timer()

    def retire(self) -> None:
        if self._retired:
            return
        self.stop()
        self._retired = True
        self._active_leases.clear()
        self._leases.clear()
        self._seen_message_ids.clear()
        self._seen_initialised = False
        self._emails = ()
        self._last_error = None
        self._has_valid_data = False
        self._thread_manager = None
        # GmailBackend is a process singleton. Never shut it down or reset it
        # when a display/runtime-generation lease retires.
        self._backend = None
        if self._registry_key is not None:
            _drop_shared_owner(self._registry_key, self)


class GmailRuntimeService:
    """Per-display neutral lease/projection to a Gmail family owner."""

    def __init__(
        self,
        *,
        config: GmailRuntimeConfig | None = None,
        shared: bool = True,
        backend: GmailBackend | Any | None = None,
        runtime_generation: Any = None,
    ) -> None:
        if shared and backend is not None:
            raise ValueError("backend injection is isolated-standalone only")
        self._config = (config or GmailRuntimeConfig()).normalized()
        self._shared = bool(shared)
        self._backend = backend
        self._runtime_generation = runtime_generation
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedGmailRuntimeOwner | None = None
        self._running = False
        self._retired = False

    @property
    def config(self) -> GmailRuntimeConfig:
        owner = self._owner
        return owner.config if owner is not None else self._config

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    @property
    def shared_owner(self) -> _SharedGmailRuntimeOwner | None:
        return self._owner

    @property
    def backend_mode(self) -> GmailBackendMode | Any:
        owner = self._owner
        return owner.backend_mode if owner is not None else GmailBackendMode.OAUTH

    def is_imap_backend(self) -> bool:
        mode = self.backend_mode
        if mode == GmailBackendMode.IMAP:
            return True
        return str(getattr(mode, "value", mode)).strip().lower() == "imap"

    def current_snapshot(self) -> GmailRuntimeSnapshot | None:
        owner = self._owner
        return owner.current_snapshot() if owner is not None else None

    def is_running(self) -> bool:
        return bool(
            self._running
            and not self._retired
            and self._owner is not None
            and self._owner.is_running()
        )

    def is_retired(self) -> bool:
        return self._retired

    def is_refresh_in_progress(self) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.refresh_in_progress)

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager
        owner = self._owner
        if owner is not None:
            if owner._thread_manager is None:
                owner._thread_manager = thread_manager
            elif thread_manager is not None and owner._thread_manager is not thread_manager:
                raise RuntimeError("shared Gmail lease cannot replace ThreadManager")

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach consumer to retired Gmail service")
        current = self._consumer()
        if current is not None and current is not consumer:
            raise RuntimeError("Gmail lease already belongs to another consumer")
        if self._owner is not None:
            if current is consumer:
                return
            raise RuntimeError("Gmail lease already has an owner")
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                generation = getattr(consumer.parent(), "_runtime_generation", None)
            except Exception:
                generation = None
        if generation is not None:
            self._runtime_generation = generation
        if self._thread_manager is None:
            self._thread_manager = getattr(consumer, "_thread_manager", None)

        owner_created = False
        if self._shared:
            if self._runtime_generation is None and self._thread_manager is None:
                self._consumer_ref = None
                raise RuntimeError(
                    "shared Gmail lease requires runtime generation or ThreadManager"
                )
            key = _shared_owner_key(self._runtime_generation, self._thread_manager)
            owner = _SHARED_GMAIL_OWNERS.get(key)
            if owner is None or owner.is_retired():
                owner = _SharedGmailRuntimeOwner(
                    config=self._config,
                    thread_manager=self._thread_manager,
                    runtime_generation=self._runtime_generation,
                    registry_key=key,
                )
                _SHARED_GMAIL_OWNERS[key] = owner
                owner_created = True
        else:
            owner = _SharedGmailRuntimeOwner(
                config=self._config,
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                backend=self._backend,
            )
            owner_created = True
        try:
            owner.attach(self)
        except Exception:
            self._consumer_ref = None
            if owner_created:
                owner.retire()
            raise
        self._owner = owner

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer()
        if consumer is not None and current is not consumer:
            return
        owner = self._owner
        if owner is not None:
            owner.detach(self)
        self._owner = None
        self._consumer_ref = None
        self._running = False

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_gmail_consumer_alive())
        except Exception:
            return False

    def _deliver_snapshot(self, snapshot: GmailRuntimeSnapshot) -> None:
        consumer = self._consumer()
        if not self._running or consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_gmail_runtime_snapshot(snapshot)
        except Exception:
            logger.debug("[GMAIL_RUNTIME] Snapshot delivery failed", exc_info=True)

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        if self._running:
            return True
        self._running = True
        try:
            activated = self._owner.activate(self)
        except Exception:
            logger.error("[GMAIL_RUNTIME] Lease activation failed closed", exc_info=True)
            activated = False
        if not activated:
            self._running = False
            return False
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._owner is not None:
            self._owner.deactivate(self)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.detach_consumer()
        self._thread_manager = None

    def refresh(self) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.refresh())

    def dispatch_action(self, action: str, message_id: str) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.dispatch_action(action, message_id))

    def start_auth_flow(self) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.start_auth_flow())

    def open_message_in_browser(self, message_id: str) -> bool:
        owner = self._owner
        return bool(owner is not None and owner.open_message_in_browser(message_id))

    def configure(self, config: GmailRuntimeConfig) -> None:
        self._config = config.normalized()
        if self._owner is not None:
            self._owner.configure(self._config)
