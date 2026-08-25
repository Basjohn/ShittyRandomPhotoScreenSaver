"""Gmail overlay widget for screensaver."""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QWidget
from shiboken6 import Shiboken

from core.gmail.gmail_client import EmailMetadata, GmailLabel
from core.gmail.gmail_deeplinks import gmail_inbox_url
from core.logging.logger import get_logger
from core.performance import widget_paint_sample, widget_timer_sample
from core.settings.widget_capacity_policy import (
    LIST_WIDGET_MIN_CAPACITY,
    clamp_list_capacity,
)
from core.audio.sound_paths import default_notification_sound_path
from core.threading.manager import ThreadManager
from core.windows.secure_url_launcher import open_url
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition, WidgetLifecycleState
from widgets.gmail_components import (
    DisplayRow,
    GmailPosition,
    clean_sender_name,
    format_email_date,
    group_emails,
    shorten_subject,
    smart_title_case_subject,
)
from widgets.service_widget_runtime import (
    defer_refresh_if_transition,
    defer_value_if_transition,
    ensure_single_shot_timer,
    parent_transition_running,
    preserve_visible_fallback,
    reset_deferred_runtime_state,
    stop_qtimer_attr,
    sync_refresh_spinner_for_transition,
)
from widgets.gmail_runtime import (
    CACHE_DIR as CACHE_DIR,
    CACHE_MAX_AGE_HOURS as CACHE_MAX_AGE_HOURS,
    CACHE_PATH,
    GmailRuntimeConfig,
    GmailRuntimeService,
    GmailRuntimeSnapshot,
)
from widgets.shadow_utils import (
    ShadowFadeProfile,
    draw_rounded_rect_border,
    draw_text_with_shadow,
    text_shadows_enabled,
)

logger = get_logger(__name__)


GMAIL_IMAGE_ASSETS = (
    "images/google-gmail.png",
    "images/gmail-envelope.png",
    "images/gmail-read.png",
    "images/gmail-archive.svg",
    "images/gmail-spam.png",
    "images/gmail-trash.png",
)
GMAIL_ACTION_ICON_PATHS = {
    "read": ("images/gmail-read.png",),
    "unread": ("images/gmail-envelope.png",),
    "archive": ("images/gmail-archive.svg",),
    "spam": ("images/gmail-spam.png",),
    "trash": ("images/gmail-trash.png",),
}


def _gmail_asset_path(relative_path: str) -> Path:
    """Resolve Gmail widget assets in script, onedir, and onefile builds."""
    rel = Path(relative_path)
    candidates = [
        Path.cwd() / rel,
        Path(getattr(sys, "argv", [""])[0]).resolve().parent / rel,
        Path(__file__).resolve().parents[1] / rel,
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return candidates[-1]


class GmailWidget(BaseOverlayWidget):
    """Gmail overlay widget showing recent emails."""

    email_clicked = Signal(str)
    unread_count_changed = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: GmailPosition = GmailPosition.TOP_CENTER,
        settings: Optional[Any] = None,
        *,
        build_default_runtime: bool = True,
    ) -> None:
        overlay_pos = OverlayPosition.from_string(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="gmail")
        self._gmail_position = position

        # Runtime/model ownership is attached after settings are normalized.
        # Production suppresses the convenience owner and receives a lease from
        # WidgetRuntimeManager before lifecycle start.
        self._runtime_service: Optional[GmailRuntimeService] = None
        self._owns_runtime_service = False
        self._emails: List[EmailMetadata] = []
        self._display_rows: List[DisplayRow] = []
        self._unread_count = 0
        self._has_displayed_valid_data = False
        self._last_error: Optional[str] = None

        self._configured_capacity = LIST_WIDGET_MIN_CAPACITY
        self._effective_visible_capacity = self._configured_capacity
        self._refresh_interval = timedelta(minutes=5)
        self._group_threads = False
        self._show_sender = True
        self._show_subject = True
        self._show_envelope_icon = True
        self._show_three_dot_menu = True
        self._show_refresh_spiral = True
        self._show_timestamp = True
        self._date_display_mode = "relative"
        self._show_separators = True
        self._auto_title_case = True
        self._clean_sender_names = True
        self._max_sender_words = 3
        self._sender_subject_ratio = 35
        self._max_subject_words = 4
        self._show_unread_count_in_header = True
        self._desaturate_when_no_unread = True
        self._account_slot = "0"

        self._separator_color = QColor(200, 200, 200, 40)
        self._separator_thickness = 1
        self._boundary_separator_color = QColor(180, 180, 180, 80)
        self._boundary_separator_thickness = 2

        self._width = 600
        self._content_padding_left = 0
        self._content_padding_right = 0
        self._content_padding_top = 0
        self._show_header_border = True
        self._header_frame_pad_x = 10
        self._header_frame_pad_y = 6
        self._header_logo_gap = 8
        self._header_logo_y_offset = 2
        self._header_content_y_offset = -1

        self._header_logo_px_adjust = 0
        self._header_font_pt = max(6, int(self._font_size * 1.2))
        self._header_logo_size = max(12, int(self._header_font_pt * 1.3))
        self._row_vertical_spacing = 2

        self._brand_pixmap: Optional[QPixmap] = None
        self._brand_pixmap_desaturated: Optional[QPixmap] = None
        self._envelope_pixmap: Optional[QPixmap] = None
        self._envelope_pixmap_dim: Optional[QPixmap] = None
        self._envelope_read_pixmap: Optional[QPixmap] = None
        self._action_icons: Dict[str, Optional[QPixmap]] = {}
        self._cached_content_pixmap: Optional[QPixmap] = None
        self._cached_content_identity: Optional[Tuple[int, int, float, int]] = None
        self._cache_invalidated = True
        self._cache_revision = 0
        self._cache_prepare_scheduled = False

        self._header_hit_rect: Optional[QRect] = None
        self._refresh_hit_rect: Optional[QRect] = None
        self._row_hit_rects: List[Tuple[QRect, str, str]] = []
        self._action_hit_rects: List[Tuple[QRect, str]] = []
        self._active_action_menu: Optional[QMenu] = None

        self._cancelled = False
        self._refreshing = False
        self._last_received_runtime_revision = 0
        self._last_applied_runtime_revision = 0
        self._refresh_spin_angle = 0
        self._refresh_spin_timer: Optional[QTimer] = None
        self._refresh_spinner_suspended_for_transition = False
        self._deferred_fetch_timer: Optional[QTimer] = None
        self._deferred_refresh_timer: Optional[QTimer] = None
        self._pending_refresh_after_transition = False
        self._deferred_fetch_result: Optional[Tuple[List[EmailMetadata], int, Optional[int]]] = None
        self._deferred_fetch_error: Optional[Tuple[str, Optional[int]]] = None

        self._play_sound_on_new_mail: bool = False
        self._sound_file_path: str = default_notification_sound_path()
        self._sound_volume_percent: int = 50

        if settings is not None:
            self.apply_settings(settings)
        self._setup_ui()
        self._load_brand_pixmap()
        self._load_envelope_pixmap()
        self._load_action_icons()
        self._invalidate_content_cache()

        if build_default_runtime:
            self.set_runtime_service(
                GmailRuntimeService(
                    config=self._gmail_runtime_config(cache_path=CACHE_PATH),
                    shared=False,
                    runtime_generation=getattr(self, "_runtime_generation", None),
                ),
                owns_service=True,
            )

    # ------------------------------------------------------------------
    # Presentation-neutral Gmail runtime consumer boundary
    # ------------------------------------------------------------------
    def _gmail_runtime_config(
        self,
        *,
        cache_path: Path = CACHE_PATH,
        filter_label: str | None = None,
    ) -> GmailRuntimeConfig:
        return GmailRuntimeConfig(
            refresh_minutes=max(
                1, int(self._refresh_interval.total_seconds() // 60)
            ),
            filter_label=(
                filter_label
                if filter_label is not None
                else GmailLabel.INBOX.value
            ),
            play_sound_on_new_mail=self._play_sound_on_new_mail,
            sound_file_path=self._sound_file_path,
            sound_volume_percent=self._sound_volume_percent,
            cache_path=cache_path,
        ).normalized()

    def _sync_runtime_config(self) -> None:
        service = self._runtime_service
        if service is None:
            return
        service.configure(
            self._gmail_runtime_config(
                cache_path=service.config.cache_path,
                filter_label=service.config.filter_label,
            )
        )

    def set_thread_manager(self, manager: "ThreadManager") -> None:
        super().set_thread_manager(manager)
        service = self._runtime_service
        if service is not None:
            service.set_thread_manager(manager)

    def set_runtime_service(
        self,
        service: Optional[GmailRuntimeService],
        *,
        owns_service: bool = False,
    ) -> None:
        """Attach the neutral Gmail lease before lifecycle activation."""

        previous = self._runtime_service
        previous_owned = self._owns_runtime_service
        if previous is service:
            owns_service = previous_owned or owns_service
        if previous is not None and previous is not service:
            if previous_owned:
                previous.retire()
            else:
                previous.detach_consumer(self)

        self._runtime_service = service
        self._owns_runtime_service = bool(service is not None and owns_service)
        if service is None:
            return
        try:
            tm = getattr(self, "_thread_manager", None)
            if tm is not None:
                service.set_thread_manager(tm)
            service.attach_consumer(self)
        except Exception:
            self._runtime_service = None
            self._owns_runtime_service = False
            if owns_service:
                service.retire()
            raise

    def _release_runtime_service(self) -> None:
        service = self._runtime_service
        owns_service = self._owns_runtime_service
        self._runtime_service = None
        self._owns_runtime_service = False
        if service is None:
            return
        if owns_service:
            service.retire()
        else:
            service.detach_consumer(self)

    def is_gmail_consumer_alive(self) -> bool:
        return bool(Shiboken.isValid(self))

    def on_gmail_runtime_snapshot(self, snapshot: GmailRuntimeSnapshot) -> None:
        """Project one accepted neutral snapshot into this display's pixels."""

        if not Shiboken.isValid(self) or self._cancelled:
            return
        if snapshot.revision <= self._last_received_runtime_revision:
            return
        self._last_received_runtime_revision = snapshot.revision
        self._set_refreshing(snapshot.refreshing)
        if snapshot.source in {"refreshing", "dispatch_error"}:
            # Cadence feedback is presentation state, but it is not an accepted
            # empty inbox revision and must never trigger the first-show fade.
            return
        if snapshot.error is not None:
            self._on_fetch_error(
                snapshot.error,
                snapshot.revision,
                defer_for_transition=True,
            )
            return
        self._on_emails_fetched(
            list(snapshot.emails),
            snapshot.unread_count,
            snapshot.revision,
            defer_for_transition=True,
        )

    def _setup_ui(self) -> None:
        self._apply_base_styling()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(False)
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setContentsMargins(20, 12, 20, 12)
        self._apply_width()
        self.setMinimumHeight(120)

    def _apply_width(self) -> None:
        width = max(200, min(1200, int(self._width)))
        self._width = width
        applied_width = self._resolve_custom_locked_width(width)
        self.setMinimumWidth(applied_width)
        self.setMaximumWidth(applied_width)

        if self._active_custom_layout_rect() is not None:
            self.updateGeometry()
            self._schedule_custom_layout_geometry_reapply()
            self.update()
            return

        if self.width() != applied_width:
            self.resize(applied_width, self.height())
        self._update_position()

    def _update_stylesheet(self) -> None:
        super()._update_stylesheet()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        hint = super().sizeHint()
        width = self._width
        height = max(self.minimumHeight(), hint.height())
        return QSize(width, height)

    def _load_brand_pixmap(self) -> None:
        path = _gmail_asset_path("images/google-gmail.png")
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._brand_pixmap = pm.scaled(
                    self._header_logo_size, self._header_logo_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._brand_pixmap_desaturated = self._desaturate_pixmap(self._brand_pixmap)
                return
        logger.warning("[GMAIL] Brand PNG missing: %s", path)
        self._brand_pixmap = None
        self._brand_pixmap_desaturated = None

    @staticmethod
    def _desaturate_pixmap(pixmap: QPixmap) -> Optional[QPixmap]:
        if pixmap.isNull():
            return None
        grayscale = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        return QPixmap.fromImage(grayscale)

    def _sync_header_metrics(self) -> None:
        base_font = max(6, int(self._font_size))
        media_header_font = max(6, int(base_font * 1.2))
        header_font = max(6, media_header_font + int(round(int(self._header_logo_px_adjust) / 1.3)))
        logo_size = max(12, int(header_font * 1.3))
        self._header_logo_size = logo_size
        self._header_font_pt = header_font

    def _load_envelope_pixmap(self) -> None:
        unread_path = _gmail_asset_path("images/gmail-envelope.png")
        read_path = _gmail_asset_path("images/gmail-read.png")
        target = 16

        if unread_path.exists():
            pm = QPixmap(str(unread_path))
            if not pm.isNull():
                self._envelope_pixmap = pm.scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        if read_path.exists():
            read_pm = QPixmap(str(read_path))
            if not read_pm.isNull():
                self._envelope_read_pixmap = read_pm.scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        if self._envelope_read_pixmap is None and unread_path.exists():
            pm = QPixmap(str(unread_path))
            if not pm.isNull():
                dim_img = pm.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                self._envelope_pixmap_dim = QPixmap.fromImage(dim_img).scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._envelope_read_pixmap = self._envelope_pixmap_dim
        else:
            self._envelope_pixmap_dim = self._envelope_read_pixmap

        if self._envelope_pixmap is None:
            logger.warning("[GMAIL] Envelope PNG missing: %s", unread_path)
        if self._envelope_read_pixmap is None:
            logger.warning("[GMAIL] Read envelope PNG missing: %s", read_path)

    def _envelope_for_email(self, email: EmailMetadata) -> Optional[QPixmap]:
        return self._envelope_pixmap if email.is_unread else self._envelope_read_pixmap

    def _ensure_desaturated_brand(self) -> Optional[QPixmap]:
        if self._brand_pixmap is None:
            return None
        return self._brand_pixmap_desaturated

    def _load_action_icons(self) -> None:
        for key, path_options in GMAIL_ACTION_ICON_PATHS.items():
            loaded: Optional[QPixmap] = None
            for path_str in path_options:
                path = _gmail_asset_path(path_str)
                if path.exists():
                    pm = QPixmap(str(path))
                    if not pm.isNull():
                        loaded = pm.scaled(
                            16,
                            16,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        break
            if loaded is None:
                logger.warning("[GMAIL] Action icon missing or unreadable: %s", path_options)
            self._action_icons[key] = loaded

    def _action_icon(self, key: str) -> QIcon:
        pm = self._action_icons.get(key)
        if pm is None or pm.isNull():
            pm = self._fallback_action_pixmap(key)
            self._action_icons[key] = pm
        return QIcon(pm)

    @staticmethod
    def _fallback_action_pixmap(key: str) -> QPixmap:
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(235, 235, 235, 220), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            if key == "archive":
                painter.drawLine(3, 5, 13, 5)
                painter.drawLine(4, 5, 5, 3)
                painter.drawLine(5, 3, 11, 3)
                painter.drawLine(11, 3, 12, 5)
                painter.drawRect(3, 5, 10, 8)
                painter.drawLine(6, 8, 10, 8)
            elif key == "unread":
                painter.drawRect(2, 4, 12, 8)
                painter.drawLine(2, 4, 8, 9)
                painter.drawLine(14, 4, 8, 9)
            else:
                painter.drawEllipse(3, 3, 10, 10)
        finally:
            painter.end()
        return pm

    def _initialize_impl(self) -> None:
        logger.debug("[LIFECYCLE] GmailWidget initialized")

    def _activate_impl(self) -> None:
        self._cancelled = False
        self._update_card_height_from_content(1)
        if not self._ensure_thread_manager("GmailWidget._activate_impl"):
            raise RuntimeError("ThreadManager is not configured")
        service = self._runtime_service
        if service is None:
            raise RuntimeError("Gmail runtime service is not attached")
        service.set_thread_manager(self._thread_manager)
        if not service.start():
            raise RuntimeError("Gmail runtime service failed to start")
        logger.debug("[LIFECYCLE] GmailWidget activated")

    def _deactivate_impl(self) -> None:
        service = self._runtime_service
        if service is not None:
            service.stop()
        self._reset_deferred_runtime_state(delete_qtimers=False)
        self._set_refreshing(False)
        self._cancelled = True
        self._last_received_runtime_revision = 0
        self._last_applied_runtime_revision = 0
        self._emails.clear()
        self._display_rows.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        self._clear_content_cache()
        logger.debug("[LIFECYCLE] GmailWidget deactivated")

    def _cleanup_impl(self) -> None:
        self._deactivate_impl()
        self._release_runtime_service()
        logger.debug("[LIFECYCLE] GmailWidget cleaned up")

    def start(self) -> None:
        if self._lifecycle_state == WidgetLifecycleState.INACTIVE:
            self.activate()

    def stop(self) -> None:
        if self._lifecycle_state == WidgetLifecycleState.ACTIVE:
            self.deactivate()

    def cleanup(self) -> None:
        self._reset_deferred_runtime_state(delete_qtimers=True)
        self._set_refreshing(False)
        super().cleanup()

    def _stop_deferred_timers(self, *, delete_qtimers: bool) -> None:
        for attr_name in ("_deferred_fetch_timer", "_deferred_refresh_timer"):
            stop_qtimer_attr(self, attr_name, delete_qtimers=delete_qtimers)

    def _reset_deferred_runtime_state(self, *, delete_qtimers: bool) -> None:
        reset_deferred_runtime_state(
            self,
            timer_attrs=("_deferred_fetch_timer", "_deferred_refresh_timer"),
            state_attrs=(
                ("_pending_refresh_after_transition", False),
                ("_deferred_fetch_result", None),
                ("_deferred_fetch_error", None),
            ),
            delete_qtimers=delete_qtimers,
        )

    def _fetch_emails(self, *, defer_for_transition: bool = True) -> bool:
        if defer_for_transition and self._defer_refresh_if_transition():
            return True
        service = self._runtime_service
        return bool(service is not None and service.refresh())

    def _set_refreshing(self, refreshing: bool) -> None:
        refreshing = bool(refreshing)
        if refreshing == self._refreshing:
            return
        self._refreshing = refreshing
        if refreshing:
            self._refresh_spinner_suspended_for_transition = self._parent_transition_running()
            if self._refresh_spin_timer is None:
                self._refresh_spin_timer = QTimer(self)
                self._refresh_spin_timer.timeout.connect(self._advance_refresh_spinner)
                self._register_resource(self._refresh_spin_timer, "gmail_refresh_spin_timer")
            if not self._refresh_spinner_suspended_for_transition:
                self._refresh_spin_timer.start(80)
        else:
            self._refresh_spinner_suspended_for_transition = False
            if self._refresh_spin_timer is not None:
                self._refresh_spin_timer.stop()
            self._refresh_spin_angle = 0
        self._update_refresh_button_region()

    def _advance_refresh_spinner(self) -> None:
        if not self._refreshing or self._refresh_spinner_suspended_for_transition or self._parent_transition_running():
            if self._refresh_spin_timer is not None:
                self._refresh_spin_timer.stop()
            self._refresh_spinner_suspended_for_transition = bool(self._refreshing)
            return
        self._refresh_spin_angle = (self._refresh_spin_angle + 30) % 360
        self._update_refresh_button_region()

    def _update_refresh_button_region(self) -> None:
        if self._refresh_hit_rect is not None:
            self.update(self._refresh_hit_rect.adjusted(-2, -2, 2, 2))
        else:
            self.update()

    def _parent_transition_running(self) -> bool:
        return parent_transition_running(self)

    def on_parent_transition_work_pending(self, pending: bool) -> None:
        """Pause live refresh animation as soon as a transition is requested."""
        sync_refresh_spinner_for_transition(
            self,
            pending,
            restart_callback=lambda timer: timer.start(80),
            update_callback=self._update_refresh_button_region,
        )

    def _defer_refresh_if_transition(self) -> bool:
        return defer_refresh_if_transition(
            self,
            pending_attr="_pending_refresh_after_transition",
            schedule_callback=self._schedule_deferred_refresh,
            logger=logger,
            log_message="[GMAIL] Deferred email refresh until active transition finishes",
        )

    def _schedule_deferred_refresh(self) -> None:
        ensure_single_shot_timer(
            self,
            attr_name="_deferred_refresh_timer",
            delay_ms=250,
            timeout_callback=self._flush_deferred_refresh,
            resource_name="gmail_deferred_refresh_timer",
        )

    def _flush_deferred_refresh(self) -> None:
        if self._cancelled:
            self._pending_refresh_after_transition = False
            return
        if not self._pending_refresh_after_transition:
            return
        if self._parent_transition_running():
            self._schedule_deferred_refresh()
            return
        self._pending_refresh_after_transition = False
        self._fetch_emails(defer_for_transition=False)

    def _defer_fetch_result_if_transition(
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int],
    ) -> bool:
        return defer_value_if_transition(
            self,
            attr_name="_deferred_fetch_result",
            value=(list(emails), int(unread_count), generation),
            clear_attrs=("_deferred_fetch_error",),
            schedule_callback=self._schedule_deferred_fetch_flush,
            logger=logger,
            log_message="[GMAIL] Deferred fetched mail apply until active transition finishes",
        )

    def _defer_fetch_error_if_transition(
        self,
        error_msg: str,
        generation: Optional[int],
    ) -> bool:
        return defer_value_if_transition(
            self,
            attr_name="_deferred_fetch_error",
            value=(str(error_msg), generation),
            clear_attrs=("_deferred_fetch_result",),
            schedule_callback=self._schedule_deferred_fetch_flush,
            logger=logger,
            log_message="[GMAIL] Deferred fetch error display until active transition finishes",
        )

    def _schedule_deferred_fetch_flush(self) -> None:
        ensure_single_shot_timer(
            self,
            attr_name="_deferred_fetch_timer",
            delay_ms=250,
            timeout_callback=self._flush_deferred_fetch_result,
            resource_name="gmail_deferred_fetch_timer",
        )

    def _flush_deferred_fetch_result(self) -> None:
        if self._cancelled:
            self._deferred_fetch_result = None
            self._deferred_fetch_error = None
            return
        if self._parent_transition_running():
            self._schedule_deferred_fetch_flush()
            return
        if self._deferred_fetch_error is not None:
            error_msg, generation = self._deferred_fetch_error
            self._deferred_fetch_error = None
            self._on_fetch_error(error_msg, generation, defer_for_transition=False)
            return
        if self._deferred_fetch_result is not None:
            emails, unread_count, generation = self._deferred_fetch_result
            self._deferred_fetch_result = None
            self._on_emails_fetched(emails, unread_count, generation, defer_for_transition=False)

    def _on_emails_fetched(
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        with widget_timer_sample(self, "gmail.fetch.apply"):
            self._on_emails_fetched_impl(
                emails,
                unread_count,
                generation,
                defer_for_transition=defer_for_transition,
            )

    def _on_emails_fetched_impl(
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        if self._cancelled:
            return
        if (
            generation is not None
            and generation
            < max(
                self._last_applied_runtime_revision,
                self._last_received_runtime_revision,
            )
        ):
            return
        self._set_refreshing(False)
        if defer_for_transition and self._defer_fetch_result_if_transition(emails, unread_count, generation):
            return
        display_emails = list(emails)
        if (
            self._has_displayed_valid_data
            and self._last_error is None
            and display_emails == self._emails
            and unread_count == self._unread_count
        ):
            if generation is not None:
                self._last_applied_runtime_revision = max(
                    self._last_applied_runtime_revision, generation
                )
            logger.debug("[GMAIL] Gmail projection unchanged; skipping repaint")
            return
        if not display_emails and preserve_visible_fallback(
            self,
            content_attr="_emails",
            logger=logger,
            log_message="[GMAIL] Empty fetch result received; keeping cached/displayed content visible",
        ):
            if generation is not None:
                self._last_applied_runtime_revision = max(
                    self._last_applied_runtime_revision, generation
                )
            return
        self._emails = display_emails
        self._last_error = None
        self._rebuild_display_rows()
        if unread_count != self._unread_count:
            self._unread_count = unread_count
            self.unread_count_changed.emit(unread_count)
        if generation is not None:
            self._last_applied_runtime_revision = max(
                self._last_applied_runtime_revision, generation
            )
        visible_count = len(self._display_rows)
        if display_emails:
            self._has_displayed_valid_data = True
            self._update_card_height_from_content(visible_count)
            self._invalidate_content_cache_and_update(prepare_now=True)
            if not self.isVisible():
                self._request_fade_in()
        else:
            self._update_card_height_from_content(1)
            self._invalidate_content_cache_and_update(prepare_now=True)
            if not self.isVisible():
                self._request_fade_in()

    def _rebuild_display_rows(self) -> None:
        """Rebuild _display_rows from _emails, applying thread grouping if enabled."""
        emails = self._emails[: self._configured_capacity]
        if self._group_threads and emails:
            self._display_rows = group_emails(emails)[: self._configured_capacity]
        else:
            self._display_rows = [DisplayRow(email=e) for e in emails]
        self._effective_visible_capacity = max(1, len(self._display_rows) or self._configured_capacity)

    def _on_fetch_error(
        self,
        error_msg: str,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        with widget_timer_sample(self, "gmail.fetch.error_apply"):
            self._on_fetch_error_impl(
                error_msg,
                generation,
                defer_for_transition=defer_for_transition,
            )

    def _on_fetch_error_impl(
        self,
        error_msg: str,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        if self._cancelled:
            return
        if (
            generation is not None
            and generation
            < max(
                self._last_applied_runtime_revision,
                self._last_received_runtime_revision,
            )
        ):
            return
        self._set_refreshing(False)
        if defer_for_transition and self._defer_fetch_error_if_transition(error_msg, generation):
            return
        if error_msg.lower() != "auth" and preserve_visible_fallback(
            self,
            content_attr="_emails",
            logger=logger,
            log_message=f"[GMAIL] Fetch failed but keeping cached/displayed content visible: {error_msg}",
        ):
            if generation is not None:
                self._last_applied_runtime_revision = max(
                    self._last_applied_runtime_revision, generation
                )
            return
        self._last_error = error_msg
        if generation is not None:
            self._last_applied_runtime_revision = max(
                self._last_applied_runtime_revision, generation
            )
        logger.warning("[GMAIL] Displaying error state: %s", error_msg)
        self._update_card_height_from_content(1)
        self._invalidate_content_cache_and_update(prepare_now=True)

    # ------------------------------------------------------------------
    # Card Height
    # ------------------------------------------------------------------

    def _update_card_height_from_content(
        self, visible_rows: Optional[int] = None
    ) -> None:
        if self._last_error:
            self._update_card_height_for_error_state()
            return
        rows = max(1, int(visible_rows)) if visible_rows is not None else 0
        if rows <= 0:
            rows = len(self._display_rows) or self._configured_capacity or 1
        rows = max(1, min(rows, max(1, self._configured_capacity)))
        base_font_pt = max(8, int(self._font_size))
        layout_scale = max(0.5, min(2.0, float(base_font_pt) / 13.0))
        header_font_pt = int(self._header_font_pt or base_font_pt)
        header_font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        header_layout = self._calculate_header_layout(
            header_font,
            self._header_text(),
            self._brand_pixmap,
        )
        header_height = int(header_layout["height"]) + self._content_padding_top + 8
        row_font = QFont(self._font_family, base_font_pt, QFont.Weight.Normal)
        row_metrics = QFontMetrics(row_font)
        line_height = row_metrics.height() + max(2, int(round(6 * layout_scale)))
        card_padding = 22
        try:
            margins = self.contentsMargins()
            margin_top = margins.top()
            margin_bottom = margins.bottom()
        except Exception:
            margin_top = 0
            margin_bottom = 0
        content_height = (
            header_height
            + (rows * line_height)
            + (max(0, rows - 1) * self._row_vertical_spacing)
            + card_padding
        )
        target = content_height + margin_top + margin_bottom + 4
        try:
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)
        except Exception:
            pass
        try:
            self._apply_runtime_content_height_in_custom_layout(target)
        except Exception:
            pass

    def _update_card_height_for_error_state(self) -> None:
        base_font_pt = max(8, int(self._font_size))
        header_font_pt = int(self._header_font_pt or base_font_pt)
        header_font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        header_layout = self._calculate_header_layout(
            header_font,
            self._header_text(),
            self._brand_pixmap,
        )
        header_bottom = int(header_layout["bottom"]) + 8
        error_font = QFont(self._font_family, base_font_pt, QFont.Weight.Normal)
        error_metrics = QFontMetrics(error_font)
        available_width = max(200, self._width - 40)
        error_rect = error_metrics.boundingRect(
            QRect(0, 0, available_width, 200),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            "Gmail unavailable. Tap to retry.",
        )
        error_height = max(error_metrics.height() * 2, error_rect.height())
        card_padding = 26
        try:
            margins = self.contentsMargins()
            margin_top = margins.top()
            margin_bottom = margins.bottom()
        except Exception:
            margin_top = 0
            margin_bottom = 0
        target = header_bottom + error_height + card_padding + margin_top + margin_bottom + 8
        try:
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)
        except Exception:
            pass
        try:
            self._apply_runtime_content_height_in_custom_layout(target)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fade In
    # ------------------------------------------------------------------

    def _request_fade_in(self) -> None:
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                def starter():
                    self.show()
                    self.raise_()
                    ShadowFadeProfile.start_fade_in(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                parent.request_overlay_fade_sync("gmail", starter)
            else:
                self.show()
                self.raise_()
        except Exception:
            self.show()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        with widget_paint_sample(self, "gmail.paint"):
            super().paintEvent(event)
            self._paint_cached_content()

    def _paint_cached_content(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        try:
            prepared_pixmap = self._prepared_content_pixmap_for_paint()
            if prepared_pixmap is not None:
                painter.drawPixmap(0, 0, prepared_pixmap)
            if self._show_refresh_spiral:
                self._paint_refresh_button(painter)
            else:
                self._refresh_hit_rect = None
        finally:
            painter.end()

    def _prepared_content_pixmap_for_paint(self) -> Optional[QPixmap]:
        """Return only a cache whose pixels and hit geometry match live state."""

        pixmap = self._cached_content_pixmap
        if self._cache_invalidated or pixmap is None or pixmap.isNull():
            return None
        if self._cached_content_identity != self._current_content_cache_identity():
            return None
        return pixmap

    def _current_content_cache_identity(
        self,
        size: Optional[QSize] = None,
        dpr: Optional[float] = None,
    ) -> Tuple[int, int, float, int]:
        current_size = size or self.size()
        if dpr is None:
            try:
                dpr = float(self.devicePixelRatioF())
            except Exception:
                dpr = 1.0
        return (
            int(current_size.width()),
            int(current_size.height()),
            float(dpr),
            int(self._cache_revision),
        )

    def _prepare_static_content_cache(self) -> bool:
        """Build stable Gmail content on the GUI thread before paint delivery."""

        try:
            if QThread.currentThread() != self.thread():
                logger.error("[GMAIL] Refusing static content-cache preparation off GUI thread")
                return False
        except RuntimeError:
            return False

        size = self.size()
        if size.width() <= 0 or size.height() <= 0:
            self._cached_content_pixmap = None
            self._cached_content_identity = None
            self._cache_invalidated = True
            return False

        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        identity = self._current_content_cache_identity(size, dpr)
        if (
            not self._cache_invalidated
            and self._cached_content_identity == identity
            and self._cached_content_pixmap is not None
            and not self._cached_content_pixmap.isNull()
        ):
            return False

        with widget_timer_sample(self, "gmail.cache.regen"):
            pixmap = QPixmap(max(1, int(size.width() * dpr)), max(1, int(size.height() * dpr)))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            try:
                self._paint_stable_content(painter)
            finally:
                painter.end()
            self._cached_content_pixmap = pixmap
            self._cached_content_identity = identity
            self._cache_invalidated = False
        return True

    def _schedule_content_cache_prepare(self) -> None:
        if self._cache_prepare_scheduled:
            return
        self._cache_prepare_scheduled = True
        ThreadManager.single_shot(0, self._flush_content_cache_prepare)

    def _flush_content_cache_prepare(self) -> None:
        self._cache_prepare_scheduled = False
        if self._cancelled or not Shiboken.isValid(self):
            return
        if self._prepare_static_content_cache():
            self.update()

    def _paint_stable_content(self, painter: QPainter) -> None:
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        self._paint_header(painter)
        if self._last_error:
            self._paint_error_state(painter)
        elif not self._emails:
            self._paint_empty_state(painter)
        else:
            self._paint_emails(painter)

    def _invalidate_content_cache(self, *, schedule_prepare: bool = True) -> None:
        self._cache_revision += 1
        self._cache_invalidated = True
        self._header_hit_rect = None
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        if schedule_prepare:
            self._schedule_content_cache_prepare()

    def _invalidate_content_cache_and_update(self, *, prepare_now: bool = False) -> None:
        self._invalidate_content_cache(schedule_prepare=not prepare_now)
        if prepare_now:
            self._prepare_static_content_cache()
        self.update()

    def _clear_content_cache(self) -> None:
        self._cached_content_pixmap = None
        self._cached_content_identity = None
        self._cache_revision += 1
        self._cache_invalidated = True
        self._header_hit_rect = None
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._invalidate_content_cache()

    def event(self, event) -> bool:  # type: ignore[override]
        if event.type() in (
            QEvent.Type.DevicePixelRatioChange,
            QEvent.Type.ScreenChangeInternal,
        ) and hasattr(self, "_cache_revision"):
            self._invalidate_content_cache()
        return super().event(event)

    def _paint_header(self, painter: QPainter) -> None:
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        painter.setFont(font)
        header_text = self._header_text()
        pixmap = self._brand_pixmap
        if self._desaturate_when_no_unread and self._unread_count == 0:
            desat = self._ensure_desaturated_brand()
            if desat is not None:
                pixmap = desat
        layout = self._calculate_header_layout(font, header_text, pixmap)
        self._paint_header_frame(painter, layout["frame_rect"])
        if pixmap is not None:
            painter.drawPixmap(layout["logo_rect"], pixmap)
        painter.setPen(self._text_color)
        draw_text_with_shadow(
            painter,
            layout["text_x"],
            layout["text_baseline_y"],
            header_text,
            font_size=header_font_pt,
            enabled=text_shadows_enabled(self._shadow_config),
        )
        self._header_hit_rect = QRect(layout["frame_rect"])

    def _paint_refresh_button(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        size = 22
        right = self.width() - margins.right() - self._content_padding_right
        top = margins.top() + self._content_padding_top
        rect = QRect(max(0, right - size), top, size, size)
        self._refresh_hit_rect = rect

        painter.save()
        try:
            color = QColor(170, 170, 170, 190)
            if self._refreshing:
                color = QColor(210, 210, 210, 230)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            center = rect.center()
            max_radius = max(4.0, (min(rect.width(), rect.height()) / 2.0) - 3.0)
            path = QPainterPath()
            steps = 44
            for index in range(steps):
                progress = index / float(steps - 1)
                radius = 1.1 + progress * (max_radius - 1.1)
                angle = math.radians(self._refresh_spin_angle + 30 + progress * 620)
                x = center.x() + math.cos(angle) * radius
                y = center.y() + math.sin(angle) * radius
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        finally:
            painter.restore()

    def _header_text(self) -> str:
        if self._show_unread_count_in_header and self._unread_count > 0:
            return f"Gmail ( {self._unread_count} )"
        return "Gmail"

    def _calculate_header_layout(
        self,
        font: QFont,
        header_text: str,
        pixmap: Optional[QPixmap],
    ) -> Dict[str, Any]:
        margins = self.contentsMargins()
        left = margins.left() + self._content_padding_left
        top = margins.top() + self._content_padding_top
        fm = QFontMetrics(font)
        logo_width = pixmap.width() if pixmap is not None else max(1, int(self._header_logo_size))
        logo_height = pixmap.height() if pixmap is not None else max(1, int(self._header_logo_size))
        text_width = fm.horizontalAdvance(header_text)
        text_height = fm.height()
        content_width = logo_width + self._header_logo_gap + text_width
        content_height = max(logo_height, text_height)
        frame_width = content_width + (self._header_frame_pad_x * 2)
        frame_height = content_height + (self._header_frame_pad_y * 2)
        max_width = max(1, self.width() - left - margins.right() - self._content_padding_right)
        frame_width = max(1, min(frame_width, max_width))
        frame_rect = QRect(left, top, frame_width, frame_height)
        center_y = frame_rect.top() + self._header_frame_pad_y + (content_height / 2)
        logo_x = frame_rect.left() + self._header_frame_pad_x
        content_y_offset = int(self._header_content_y_offset)
        logo_y = int(center_y - (logo_height / 2)) + int(self._header_logo_y_offset) + content_y_offset
        text_x = logo_x + logo_width + self._header_logo_gap
        text_baseline_y = int(center_y - (text_height / 2) + fm.ascent()) + content_y_offset + 1
        return {
            "frame_rect": frame_rect,
            "logo_rect": QRect(logo_x, logo_y, logo_width, logo_height),
            "text_x": text_x,
            "text_baseline_y": text_baseline_y,
            "height": frame_height,
            "bottom": frame_rect.bottom(),
        }

    def _paint_header_frame(self, painter: QPainter, frame_rect: QRect) -> None:
        if not self._show_header_border:
            return
        if self._bg_border_width <= 0 or self._bg_border_color.alpha() <= 0:
            return
        if frame_rect.width() <= 0 or frame_rect.height() <= 0:
            return
        radius = min(self._bg_corner_radius + 1, min(frame_rect.width(), frame_rect.height()) / 2)
        border_width = max(2, max(1, self._bg_border_width) - 3)
        draw_rounded_rect_border(
            painter,
            frame_rect,
            radius,
            self._bg_border_color,
            border_width,
        )

    def _header_bottom_y(self) -> int:
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        pixmap = self._brand_pixmap
        layout = self._calculate_header_layout(font, self._header_text(), pixmap)
        return int(layout["bottom"]) + 8

    def _paint_empty_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left() + self._content_padding_left,
            self._header_bottom_y() + 8,
            -(margins.right() + self._content_padding_right),
            -max(12, margins.bottom()),
        )
        msg = "No unread emails"
        painter.setFont(QFont(self._font_family, max(8, int(self._font_size)), QFont.Weight.Normal))
        painter.setPen(self._text_color.darker(120))
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
            msg,
        )

    def _paint_error_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left() + self._content_padding_left,
            self._header_bottom_y() + 8,
            -(margins.right() + self._content_padding_right),
            -max(12, margins.bottom()),
        )
        is_auth = self._last_error and "auth" in self._last_error.lower()
        msg = (
            "Gmail not connected. Tap to authenticate."
            if is_auth
            else "Gmail unavailable. Tap to retry."
        )
        painter.setFont(QFont(self._font_family, max(8, int(self._font_size)), QFont.Weight.Normal))
        painter.setPen(self._text_color.darker(120))
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
            msg,
        )

    def _compute_email_layout_metrics(self, visible_rows: List[DisplayRow]) -> Dict[str, Any]:
        margins = self.contentsMargins()
        left = margins.left() + self._content_padding_left
        base_font_pt = max(8, int(self._font_size))
        layout_scale = max(0.5, min(2.0, float(base_font_pt) / 13.0))
        available_width = max(
            1,
            self.width() - left - margins.right() - self._content_padding_right,
        )
        content_bottom = self.height() - max(12, margins.bottom())
        action_width = max(18, int(round(24 * layout_scale))) if self._show_three_dot_menu else 0
        env_slot_width = (
            self._envelope_pixmap.width() + max(3, int(round(6 * layout_scale)))
            if self._show_envelope_icon and self._envelope_pixmap is not None
            else 0
        )
        time_slot_width = 0
        if self._show_timestamp:
            time_font = QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal)
            time_fm = QFontMetrics(time_font)
            time_slot_width = max(
                (
                    time_fm.horizontalAdvance(self._format_email_date(row.email.date))
                    + max(4, int(round(8 * layout_scale)))
                    for row in visible_rows
                ),
                default=0,
            )
        row_outer_gap = max(10, int(round(18 * layout_scale)))
        sender_text_gap = max(6, int(round(12 * layout_scale)))
        text_area_width = max(1, available_width - env_slot_width - time_slot_width - action_width - row_outer_gap)
        sender_slot_width = 0
        subject_slot_width = 0
        sender_subject_gap = 0
        if self._show_sender and self._show_subject:
            sender_subject_gap = min(sender_text_gap, max(0, text_area_width - 2))
        split_budget = max(0, text_area_width - sender_subject_gap)
        if self._show_sender and self._show_subject:
            if split_budget >= 2:
                sender_slot_width = max(
                    1,
                    min(
                        split_budget - 1,
                        int(round(split_budget * self._sender_subject_ratio / 100.0)),
                    ),
                )
                subject_slot_width = split_budget - sender_slot_width
            elif split_budget == 1:
                sender_slot_width = int(self._sender_subject_ratio >= 50)
                subject_slot_width = 1 - sender_slot_width
        elif self._show_sender:
            sender_slot_width = text_area_width
        elif self._show_subject:
            subject_slot_width = text_area_width
        return {
            "left": left,
            "base_font_pt": base_font_pt,
            "layout_scale": layout_scale,
            "available_width": available_width,
            "content_bottom": content_bottom,
            "action_width": action_width,
            "env_slot_width": env_slot_width,
            "time_slot_width": time_slot_width,
            "row_outer_gap": row_outer_gap,
            "sender_text_gap": sender_text_gap,
            "text_area_width": text_area_width,
            "sender_slot_width": sender_slot_width,
            "subject_slot_width": subject_slot_width,
            "sender_subject_gap": sender_subject_gap,
        }

    def _compute_email_row_budget(self, row: DisplayRow, layout_metrics: Dict[str, Any]) -> Dict[str, int]:
        sender_width = 0
        if self._show_sender:
            sender_width = int(layout_metrics["sender_slot_width"]) + int(
                layout_metrics["sender_subject_gap"]
            )
        subject_max_width = int(layout_metrics["subject_slot_width"])
        return {
            "sender_width": sender_width,
            "subject_max_width": subject_max_width,
        }

    def _paint_emails(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        layout_metrics = self._compute_email_layout_metrics(
            self._display_rows[: self._configured_capacity]
        )
        left = int(layout_metrics["left"])
        base_font_pt = int(layout_metrics["base_font_pt"])
        layout_scale = float(layout_metrics["layout_scale"])
        row_y = self._header_bottom_y()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        available_width = int(layout_metrics["available_width"])
        content_bottom = int(layout_metrics["content_bottom"])
        visible_rows = self._display_rows[: self._configured_capacity]
        action_width = int(layout_metrics["action_width"])
        env_slot_width = int(layout_metrics["env_slot_width"])
        time_slot_width = int(layout_metrics["time_slot_width"])
        sender_slot_width = int(layout_metrics["sender_slot_width"])
        prev_unread = None
        painter.save()
        painter.setClipRect(QRect(left, row_y, max(1, available_width), max(0, content_bottom - row_y)))
        for i, row in enumerate(visible_rows):
            email = row.email
            row_budget = self._compute_email_row_budget(row, layout_metrics)
            subject_font = QFont(self._font_family, base_font_pt, QFont.Weight(600) if email.is_unread else QFont.Weight(400))
            subject_fm = QFontMetrics(subject_font)
            line_height = subject_fm.height() + max(2, int(round(6 * layout_scale)))
            if row_y + line_height > content_bottom:
                break
            if prev_unread is not None and prev_unread != email.is_unread and self._show_separators:
                sep_y = row_y - 1
                if sep_y > content_bottom:
                    break
                painter.setPen(QPen(self._boundary_separator_color, self._boundary_separator_thickness))
                painter.drawLine(left, sep_y, left + available_width, sep_y)
                row_y += 2
            subject_weight = QFont.Weight(600) if email.is_unread else QFont.Weight(400)
            sender_weight = QFont.Weight(680) if email.is_unread else QFont.Weight(550)
            time_width = time_slot_width
            time_text = ""
            if self._show_timestamp:
                time_font = QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal)
                painter.setFont(time_font)
                time_text = self._format_email_date(email.date)
            env_x = left
            env_width = env_slot_width
            if self._show_envelope_icon and self._envelope_pixmap is not None:
                env_pm = self._envelope_for_email(email)
                if env_pm is not None:
                    line_centre = row_y + (line_height * 0.5)
                    icon_half = float(env_pm.height()) / 2.0
                    env_y = int(line_centre - icon_half)
                    env_y = max(row_y, min(env_y, row_y + line_height - env_pm.height()))
                    painter.drawPixmap(env_x, env_y, env_pm)
            sender_width = 0
            if self._show_sender:
                sender_font = QFont(self._font_family, base_font_pt, sender_weight)
                painter.setFont(sender_font)
                sender_fm = QFontMetrics(sender_font)
                sender_text = self._build_sender_display_text(row)
                sender_text = sender_fm.elidedText(
                    sender_text, Qt.TextElideMode.ElideRight, sender_slot_width
                )
                sender_width = int(row_budget["sender_width"])
            subject_font = QFont(self._font_family, base_font_pt, subject_weight)
            painter.setFont(subject_font)
            subject_fm = QFontMetrics(subject_font)
            subject_text = self._build_subject_display_text(row)
            subject_max_width = int(row_budget["subject_max_width"])
            subject_text = subject_fm.elidedText(
                subject_text, Qt.TextElideMode.ElideRight, subject_max_width
            )
            text_y = row_y + subject_fm.ascent() + max(1, int(round(2 * layout_scale)))
            if self._show_timestamp:
                painter.setFont(QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal))
                painter.setPen(QColor(180, 180, 180, 200))
                time_x = env_x + env_width
                draw_text_with_shadow(
                    painter,
                    time_x,
                    text_y - 2,
                    time_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
            if self._show_sender:
                painter.setFont(QFont(self._font_family, base_font_pt, sender_weight))
                painter.setPen(
                    QColor(200, 200, 200, 255)
                    if email.is_unread
                    else QColor(180, 180, 180, 220)
                )
                sender_x = env_x + env_width + time_width
                draw_text_with_shadow(
                    painter,
                    sender_x,
                    text_y,
                    sender_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
            if self._show_subject:
                painter.setFont(subject_font)
                painter.setPen(
                    QColor(255, 255, 255, 255)
                    if email.is_unread
                    else QColor(220, 220, 220, 230)
                )
                subject_x = env_x + env_width + time_width + sender_width
                draw_text_with_shadow(
                    painter,
                    subject_x,
                    text_y,
                    subject_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
            if self._show_separators and i < len(visible_rows) - 1:
                sep_y = row_y + line_height
                if sep_y <= content_bottom:
                    painter.setPen(QPen(self._separator_color, self._separator_thickness))
                    painter.drawLine(left, sep_y, left + available_width, sep_y)
            row_rect = QRect(left, row_y, available_width, line_height)
            self._row_hit_rects.append((row_rect, email.id, email.subject))
            if self._show_three_dot_menu:
                action_x = self.width() - margins.right() - self._content_padding_right - action_width
                action_rect = QRect(action_x, row_y, action_width, line_height)
                self._action_hit_rects.append((action_rect, email.id))
                painter.setPen(QColor(150, 150, 150, 180))
                dot_x = action_x + action_rect.width() // 2
                dot_y = row_y + line_height // 2 - 6
                for j in range(3):
                    painter.drawEllipse(QPoint(dot_x, dot_y + j * 6), 2, 2)
            prev_unread = email.is_unread
            row_y += line_height + self._row_vertical_spacing
        painter.restore()

    @staticmethod
    def _group_count_suffix(row: DisplayRow) -> str:
        return f" ({row.count})" if row.count > 1 else ""

    def _build_sender_display_text(self, row: DisplayRow) -> str:
        sender_text = clean_sender_name(
            row.email.sender,
            enabled=self._clean_sender_names,
            max_words=self._max_sender_words,
        )
        return f"{sender_text}{self._group_count_suffix(row)}"

    def _build_subject_display_text(self, row: DisplayRow) -> str:
        subject_text = row.email.subject
        if self._auto_title_case:
            subject_text = smart_title_case_subject(subject_text)
        return shorten_subject(
            subject_text,
            max_words=self._max_subject_words,
            max_chars=0,
        )

    # ------------------------------------------------------------------
    # Click Handling
    # ------------------------------------------------------------------

    def _is_interactive_point(self, local_pos: QPoint) -> bool:
        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
            return True
        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            return True
        if self.is_action_menu_point(local_pos):
            return True
        if any(rect.contains(local_pos) for rect, _message_id, _subject in self._row_hit_rects):
            return True
        return False

    def is_action_menu_point(self, local_pos: QPoint) -> bool:
        return any(rect.contains(local_pos) for rect, _message_id in self._action_hit_rects)

    def is_action_menu_visible(self) -> bool:
        menu = self._active_action_menu
        return bool(menu is not None and menu.isVisible())

    def handle_click(self, local_pos: QPoint) -> bool:
        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
            self._trigger_manual_refresh()
            return True

        if self._last_error:
            is_auth = "auth" in self._last_error.lower()
            if is_auth:
                self._trigger_auth_flow()
            else:
                self._trigger_manual_refresh()
            return True

        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            open_url(gmail_inbox_url(self._account_slot))
            return True

        for rect, message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                self._show_action_menu(message_id, local_pos)
                return True

        for rect, message_id, _subject in self._row_hit_rects:
            if rect.contains(local_pos):
                email = next((e for e in self._emails if e.id == message_id), None)
                if email is not None and email.open_url:
                    open_url(email.open_url)
                else:
                    service = self._runtime_service
                    if service is None or not service.open_message_in_browser(message_id):
                        open_url(gmail_inbox_url(self._account_slot))
                return True

        return False

    def handle_double_click(self, local_pos: QPoint) -> bool:
        if not self._enabled:
            return False
        if self._is_interactive_point(local_pos):
            return False
        started = self._trigger_manual_refresh()
        if started:
            logger.debug("[GMAIL] Blank-space double-click triggered email refresh")
        return bool(started)

    def resolve_click_target(self, local_pos: QPoint) -> Optional[str]:
        """Return a Gmail URL for central MC/SCR click routing, without opening it."""
        if self._last_error:
            return None

        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
            return None

        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            return gmail_inbox_url(self._account_slot)

        for rect, _message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                return None

        for rect, message_id, _subject in self._row_hit_rects:
            if not rect.contains(local_pos):
                continue
            email = next((e for e in self._emails if e.id == message_id), None)
            if email is not None and email.open_url:
                return email.open_url
            return gmail_inbox_url(self._account_slot)

        return None

    def _trigger_auth_flow(self) -> None:
        logger.info("[GMAIL] Requesting authentication")
        service = self._runtime_service
        if service is None or not service.start_auth_flow():
            logger.error("[GMAIL] Auth flow was not admitted by the Gmail runtime")

    def _trigger_manual_refresh(self) -> bool:
        if not self._enabled:
            return False
        service = self._runtime_service
        if service is None:
            return False
        if service.is_refresh_in_progress():
            logger.debug("[GMAIL] Manual refresh ignored; fetch already in progress")
            return True
        if self._defer_refresh_if_transition():
            return True
        return bool(service.refresh())

    def _show_action_menu(self, message_id: str, local_pos: QPoint) -> None:
        if self._active_action_menu is not None:
            try:
                self._active_action_menu.close()
            except Exception:
                pass
            self._active_action_menu = None

        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        menu.setStyleSheet(
            "QMenu { background-color: rgba(43,43,43,255); border: 2px solid rgba(154,154,154,200); border-radius: 6px; padding: 4px 2px; }"
            "QMenu::item { background-color: transparent; color: #ffffff; padding: 6px 20px 6px 12px; margin: 1px 3px; border-radius: 3px; font-size: 12px; }"
            "QMenu::item:selected { background-color: rgba(62,62,62,220); }"
        )
        email = next((e for e in self._emails if e.id == message_id), None)
        if not email:
            return

        action_message_id = self._action_message_id(email)

        if email.is_unread:
            action_read = menu.addAction("Mark as Read")
            action_read.setIcon(self._action_icon("read"))
            action_read.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action("mark_read", mid)
            )
        else:
            action_unread = menu.addAction("Mark as Unread")
            action_unread.setIcon(self._action_icon("unread"))
            action_unread.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action("mark_unread", mid)
            )

        if self._should_show_archive_action(email):
            action_archive = menu.addAction("Archive")
            action_archive.setIcon(self._action_icon("archive"))
            action_archive.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action("archive", mid)
            )

        action_spam = menu.addAction("Mark as Spam")
        action_spam.setIcon(self._action_icon("spam"))
        action_spam.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action("spam", mid)
        )

        action_trash = menu.addAction("Delete")
        action_trash.setIcon(self._action_icon("trash"))
        action_trash.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action("trash", mid)
        )

        global_pos = self.mapToGlobal(local_pos)
        self._active_action_menu = menu
        menu.aboutToHide.connect(lambda: setattr(self, "_active_action_menu", None))
        menu.popup(global_pos)

    @staticmethod
    def _action_message_id(email: EmailMetadata) -> str:
        if email.provider in {"gmail", "imap"} and email.imap_uid:
            return email.imap_uid
        return email.id

    def _should_show_archive_action(self, email: EmailMetadata) -> bool:
        """Hide Archive for IMAP; keep the action code for future OAuth/diagnostic work."""
        service = self._runtime_service
        if service is not None and service.is_imap_backend():
            return False
        return email.provider != "imap"

    def _dispatch_action(self, action: str, message_id: str) -> bool:
        """Send one semantic action to the neutral serialized action owner."""

        service = self._runtime_service
        return bool(
            service is not None and service.dispatch_action(action, message_id)
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def apply_settings(self, settings: Any) -> None:
        if isinstance(settings, dict):
            self._apply_settings_dict(settings)
            return
        self.set_gmail_position(getattr(settings, "position", self._gmail_position.value))
        self.set_width(self._settings_width_value(settings))
        self.set_show_header_border(getattr(settings, "show_header_border", self._show_header_border))
        self.set_header_logo_px_adjust(getattr(settings, "header_logo_px_adjust", self._header_logo_px_adjust))
        self.set_account_slot(getattr(settings, "account_slot", self._account_slot))
        self.set_limit(getattr(settings, "limit", self._configured_capacity))
        self.set_refresh_interval(getattr(settings, "refresh_minutes", 5))
        self.set_group_threads(getattr(settings, "group_threads", self._group_threads))
        self.set_show_sender(getattr(settings, "show_sender", self._show_sender))
        self.set_show_subject(getattr(settings, "show_subject", self._show_subject))
        self.set_show_envelope_icon(getattr(settings, "show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(getattr(settings, "show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_refresh_spiral(getattr(settings, "show_refresh_spiral", self._show_refresh_spiral))
        self.set_show_timestamp(getattr(settings, "show_timestamp", self._show_timestamp))
        self.set_date_display_mode(getattr(settings, "date_display_mode", self._date_display_mode))
        self.set_show_separators(getattr(settings, "show_separators", self._show_separators))
        self.set_separator_color(getattr(settings, "separator_color", self._separator_color))
        self.set_separator_thickness(getattr(settings, "separator_thickness", self._separator_thickness))
        self.set_boundary_separator_color(getattr(settings, "boundary_separator_color", self._boundary_separator_color))
        self.set_boundary_separator_thickness(getattr(settings, "boundary_separator_thickness", self._boundary_separator_thickness))
        self.set_auto_title_case(getattr(settings, "auto_title_case", self._auto_title_case))
        self.set_clean_sender_names(getattr(settings, "clean_sender_names", self._clean_sender_names))
        self.set_max_sender_words(getattr(settings, "max_sender_words", self._max_sender_words))
        if hasattr(settings, "sender_subject_ratio"):
            self.set_sender_subject_ratio(getattr(settings, "sender_subject_ratio"))
        elif hasattr(settings, "sender_column_width"):
            self.set_sender_column_width(getattr(settings, "sender_column_width"))
        self.set_max_subject_words(getattr(settings, "max_subject_words", self._max_subject_words))
        self.set_show_unread_count_in_header(getattr(settings, "show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(getattr(settings, "desaturate_when_no_unread", self._desaturate_when_no_unread))
        self.set_play_sound_on_new_mail(getattr(settings, "play_sound_on_new_mail", self._play_sound_on_new_mail))
        self.set_sound_file_path(getattr(settings, "sound_file_path", self._sound_file_path))
        self.set_sound_volume_percent(getattr(settings, "sound_volume_percent", self._sound_volume_percent))

    def _apply_settings_dict(self, d: Dict[str, Any]) -> None:
        if any(str(key).startswith("gmail.") for key in d):
            d = {
                str(key).split(".", 1)[1] if str(key).startswith("gmail.") else str(key): value
                for key, value in d.items()
            }
        self.set_gmail_position(d.get("position", self._gmail_position.value))
        self.set_width(d.get("width", d.get("min_width", d.get("max_width", self._width))))
        self.set_show_header_border(d.get("show_header_border", self._show_header_border))
        self.set_header_logo_px_adjust(d.get("header_logo_px_adjust", self._header_logo_px_adjust))
        self.set_account_slot(d.get("account_slot", self._account_slot))
        self.set_limit(d.get("limit", self._configured_capacity))
        self.set_refresh_interval(d.get("refresh_minutes", 5))
        self.set_group_threads(d.get("group_threads", self._group_threads))
        self.set_show_sender(d.get("show_sender", self._show_sender))
        self.set_show_subject(d.get("show_subject", self._show_subject))
        self.set_show_envelope_icon(d.get("show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(d.get("show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_refresh_spiral(d.get("show_refresh_spiral", self._show_refresh_spiral))
        self.set_show_timestamp(d.get("show_timestamp", self._show_timestamp))
        self.set_date_display_mode(d.get("date_display_mode", self._date_display_mode))
        self.set_show_separators(d.get("show_separators", self._show_separators))
        self.set_separator_color(d.get("separator_color", self._separator_color))
        self.set_separator_thickness(d.get("separator_thickness", self._separator_thickness))
        self.set_boundary_separator_color(d.get("boundary_separator_color", self._boundary_separator_color))
        self.set_boundary_separator_thickness(d.get("boundary_separator_thickness", self._boundary_separator_thickness))
        self.set_auto_title_case(d.get("auto_title_case", self._auto_title_case))
        self.set_clean_sender_names(d.get("clean_sender_names", self._clean_sender_names))
        self.set_max_sender_words(d.get("max_sender_words", self._max_sender_words))
        if "sender_subject_ratio" in d:
            self.set_sender_subject_ratio(d["sender_subject_ratio"])
        elif "sender_column_width" in d:
            self.set_sender_column_width(d["sender_column_width"])
        self.set_max_subject_words(d.get("max_subject_words", self._max_subject_words))
        self.set_show_unread_count_in_header(d.get("show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(d.get("desaturate_when_no_unread", self._desaturate_when_no_unread))
        self.set_play_sound_on_new_mail(d.get("play_sound_on_new_mail", self._play_sound_on_new_mail))
        self.set_sound_file_path(d.get("sound_file_path", self._sound_file_path))
        self.set_sound_volume_percent(d.get("sound_volume_percent", self._sound_volume_percent))

    def set_gmail_position(self, position: Any) -> None:
        if isinstance(position, GmailPosition):
            gmail_position = position
        else:
            gmail_position = GmailPosition.from_string(str(position))
        self._gmail_position = gmail_position
        self.set_position(OverlayPosition.from_string(gmail_position.value))

    def _settings_width_value(self, settings: Any) -> Any:
        if hasattr(settings, "width"):
            return getattr(settings, "width")
        if hasattr(settings, "min_width"):
            return getattr(settings, "min_width")
        if hasattr(settings, "max_width"):
            return getattr(settings, "max_width")
        return self._width

    def set_width(self, width: Any) -> None:
        try:
            next_width = int(width)
        except (TypeError, ValueError):
            next_width = 600
        if self._width == max(200, min(1200, next_width)):
            return
        self._width = next_width
        self._apply_width()
        self._invalidate_content_cache_and_update()

    def set_min_width(self, width: int) -> None:
        self.set_width(width)

    def set_max_width(self, width: int) -> None:
        self.set_width(width)

    def _set_attr_and_update(self, attr: str, value: Any) -> bool:
        if getattr(self, attr) == value:
            return False
        setattr(self, attr, value)
        self._invalidate_content_cache_and_update()
        return True

    def set_font_family(self, family: str) -> None:
        next_family = family or self.DEFAULT_FONT_FAMILY
        if self._font_family == next_family:
            return
        self._invalidate_content_cache()
        super().set_font_family(next_family)
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self.update()

    def set_text_color(self, color: QColor) -> None:
        if not isinstance(color, QColor) or self._text_color == color:
            return
        self._invalidate_content_cache()
        super().set_text_color(color)
        self.update()

    def set_show_background(self, show: bool) -> None:
        super().set_show_background(show)

    def set_background_color(self, color: QColor) -> None:
        super().set_background_color(color)

    def set_background_opacity(self, opacity: float) -> None:
        super().set_background_opacity(opacity)

    def set_background_border(self, width: int, color: QColor) -> None:
        next_width = max(0, int(width))
        next_color = color if isinstance(color, QColor) else self._bg_border_color
        if int(self._bg_border_width) == next_width and self._bg_border_color == next_color:
            return
        self._invalidate_content_cache()
        super().set_background_border(width, color)
        self.update()

    def set_background_corner_radius(self, radius: int) -> None:
        if int(self._bg_corner_radius) == max(0, int(radius)):
            return
        self._invalidate_content_cache()
        super().set_background_corner_radius(radius)
        self.update()

    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        self._invalidate_content_cache()
        super().set_shadow_config(config)

    def on_fade_complete(self) -> None:
        super().on_fade_complete()

    def set_content_padding(self, left: int, right: int, top: int) -> None:
        if (
            self._content_padding_left == 0
            and self._content_padding_right == 0
            and self._content_padding_top == 0
        ):
            return
        self._content_padding_left = 0
        self._content_padding_right = 0
        self._content_padding_top = 0
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self._invalidate_content_cache_and_update()
        self._update_position()

    def set_show_header_border(self, show: bool) -> None:
        show = bool(show)
        if self._show_header_border == show:
            return
        self._show_header_border = show
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self._invalidate_content_cache_and_update()

    def set_font_size(self, size: int) -> None:
        next_size = max(8, int(size))
        if self._font_size == next_size:
            return
        self._invalidate_content_cache()
        super().set_font_size(size)
        self._sync_header_metrics()
        self._load_brand_pixmap()
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self.update()

    def set_header_logo_px_adjust(self, value: Any) -> None:
        try:
            adjust = int(value)
        except (TypeError, ValueError):
            adjust = 0
        adjust = max(-12, min(24, adjust))
        if self._header_logo_px_adjust == adjust:
            return
        self._header_logo_px_adjust = adjust
        self._sync_header_metrics()
        self._load_brand_pixmap()
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self._invalidate_content_cache_and_update()

    def set_account_slot(self, slot: Any) -> None:
        text = str(slot or "0").strip()
        next_slot = text if text.isdigit() else "0"
        if self._account_slot == next_slot:
            return
        self._account_slot = next_slot

    @property
    def configured_capacity(self) -> int:
        return int(self._configured_capacity)

    @property
    def effective_visible_capacity(self) -> int:
        return int(self._effective_visible_capacity)

    def set_limit(self, limit: int) -> None:
        next_limit = clamp_list_capacity(limit, default=self._configured_capacity)
        if self._configured_capacity == next_limit:
            return
        self._configured_capacity = next_limit
        self._rebuild_display_rows()
        self._update_card_height_from_content(len(self._display_rows) or self._configured_capacity)
        self._invalidate_content_cache_and_update()

    def set_refresh_interval(self, minutes: int) -> None:
        try:
            normalized_minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            normalized_minutes = 5
        next_interval = timedelta(minutes=normalized_minutes)
        if self._refresh_interval == next_interval:
            return
        self._refresh_interval = next_interval
        self._sync_runtime_config()

    def set_group_threads(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._group_threads == enabled:
            return
        self._group_threads = enabled
        self._rebuild_display_rows()
        self._update_card_height_from_content(len(self._display_rows) or 1)
        self._invalidate_content_cache_and_update()

    def set_show_sender(self, show: bool) -> None:
        self._set_attr_and_update("_show_sender", bool(show))

    def set_show_subject(self, show: bool) -> None:
        self._set_attr_and_update("_show_subject", bool(show))

    def set_show_envelope_icon(self, show: bool) -> None:
        self._set_attr_and_update("_show_envelope_icon", bool(show))

    def set_show_three_dot_menu(self, show: bool) -> None:
        self._set_attr_and_update("_show_three_dot_menu", bool(show))

    def set_show_refresh_spiral(self, show: bool) -> None:
        show = bool(show)
        if self._show_refresh_spiral == show:
            return
        self._show_refresh_spiral = show
        self._update_refresh_button_region()

    def set_show_timestamp(self, show: bool) -> None:
        self._set_attr_and_update("_show_timestamp", bool(show))

    def set_date_display_mode(self, mode: Any) -> None:
        normalized = str(mode or "relative").strip().lower()
        if normalized not in {"relative", "numeric", "words"}:
            normalized = "relative"
        self._set_attr_and_update("_date_display_mode", normalized)

    def _format_email_date(self, dt: datetime) -> str:
        return format_email_date(dt, self._date_display_mode)

    def set_show_separators(self, show: bool) -> None:
        self._set_attr_and_update("_show_separators", bool(show))

    def set_separator_color(self, color: Any) -> None:
        next_color = self._separator_color
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            next_color = QColor(*color)
        elif isinstance(color, QColor):
            next_color = color
        self._set_attr_and_update("_separator_color", next_color)

    def set_separator_thickness(self, thickness: int) -> None:
        self._set_attr_and_update("_separator_thickness", max(1, min(4, thickness)))

    def set_boundary_separator_color(self, color: Any) -> None:
        next_color = self._boundary_separator_color
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            next_color = QColor(*color)
        elif isinstance(color, QColor):
            next_color = color
        self._set_attr_and_update("_boundary_separator_color", next_color)

    def set_boundary_separator_thickness(self, thickness: int) -> None:
        self._set_attr_and_update("_boundary_separator_thickness", max(1, min(6, thickness)))

    def set_auto_title_case(self, enable: bool) -> None:
        self._set_attr_and_update("_auto_title_case", bool(enable))

    def set_clean_sender_names(self, enable: bool) -> None:
        self._set_attr_and_update("_clean_sender_names", bool(enable))

    def set_max_sender_words(self, value: Any) -> None:
        self._set_attr_and_update("_max_sender_words", self._coerce_non_negative_int(value, 3))

    def set_sender_subject_ratio(self, value: Any) -> None:
        try:
            next_ratio = max(10, min(80, int(value)))
        except (TypeError, ValueError):
            next_ratio = 35
        self._set_attr_and_update("_sender_subject_ratio", next_ratio)

    def set_sender_column_width(self, value: Any) -> None:
        """Migrate a legacy fixed sender width into the bounded ratio contract."""

        try:
            legacy_width = max(1, int(value))
        except (TypeError, ValueError):
            legacy_width = 180
        estimated_text_budget = max(80, int(self._width) - 80)
        self.set_sender_subject_ratio(round(legacy_width * 100.0 / estimated_text_budget))

    def set_max_subject_words(self, value: Any) -> None:
        self._set_attr_and_update("_max_subject_words", self._coerce_non_negative_int(value, 4))

    @staticmethod
    def _coerce_non_negative_int(value: Any, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def set_show_unread_count_in_header(self, show: bool) -> None:
        self._set_attr_and_update("_show_unread_count_in_header", bool(show))

    def set_desaturate_when_no_unread(self, desaturate: bool) -> None:
        self._set_attr_and_update("_desaturate_when_no_unread", bool(desaturate))

    # ------------------------------------------------------------------
    # Notification sound
    # ------------------------------------------------------------------

    def set_play_sound_on_new_mail(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._play_sound_on_new_mail == value:
            return
        self._play_sound_on_new_mail = value
        self._sync_runtime_config()

    def set_sound_file_path(self, path: str) -> None:
        path = str(path or "")
        if path == self._sound_file_path:
            return
        self._sound_file_path = path
        self._sync_runtime_config()

    def set_sound_volume_percent(self, percent: int) -> None:
        try:
            value = max(0, min(100, int(percent)))
        except (TypeError, ValueError):
            value = 50
        if value == self._sound_volume_percent:
            return
        self._sound_volume_percent = value
        self._sync_runtime_config()
