"""Production Steam Abandonment Issues overlay."""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.steam.abandonment_issues import AbandonmentSelection
from widgets.steam_abandonment_components import (
    ABANDONMENT_ACCENT_RGBA,
    ABANDONMENT_ARTWORK_SIZE_DEFAULT,
    ABANDONMENT_FIELD_DEFAULTS,
    AbandonmentCardLayout,
    abandonment_authored_size,
    abandonment_field_slot_count,
    layout_abandonment_card,
    normalize_abandonment_artwork_shape,
    normalize_abandonment_artwork_size,
    render_abandonment_card,
)
from widgets.steam_card_widget import SteamCardDefinition, SteamCardWidget
from widgets.steam_card_models import SteamCardViewModel


logger = get_logger(__name__)


class AbandonmentIssuesWidget(SteamCardWidget):
    """Cache-first archival rediscovery card with cache-backed rotation."""

    def __init__(
        self,
        parent=None,
        *,
        definition: SteamCardDefinition,
        position,
        initial_view_model: SteamCardViewModel,
        selection: AbandonmentSelection = AbandonmentSelection(),
        field_visibility: Mapping[str, bool] | None = None,
        show_artwork: bool = True,
        artwork_shape: str = "portrait",
        artwork_size: int = ABANDONMENT_ARTWORK_SIZE_DEFAULT,
        accent_color: QColor | None = None,
        guilt_desaturater: bool = False,
        guilt_desaturation_strength: int = 55,
        refresh_minutes: int = 10,
        show_connection_info_icon: bool = True,
        show_rediscovery_message: bool = True,
        build_default_runtime: bool = True,
    ) -> None:
        self._runtime_service: Optional[Any] = None
        self._owns_runtime_service = False
        self._abandonment_selection = selection
        self._abandonment_field_visibility = dict(field_visibility or {})
        self._abandonment_field_slots = abandonment_field_slot_count(
            self._abandonment_field_visibility
        )
        self._abandonment_show_artwork = bool(show_artwork)
        self._abandonment_artwork_shape = normalize_abandonment_artwork_shape(
            artwork_shape
        )
        self._abandonment_artwork_size = normalize_abandonment_artwork_size(artwork_size)
        self._abandonment_accent_color = QColor(
            accent_color or QColor(*ABANDONMENT_ACCENT_RGBA)
        )
        self._abandonment_guilt_desaturater = bool(guilt_desaturater)
        self._abandonment_guilt_desaturation_strength = max(
            0,
            min(100, int(guilt_desaturation_strength)),
        )
        self._abandonment_show_connection_info_icon = bool(show_connection_info_icon)
        self._abandonment_show_rediscovery_message = bool(show_rediscovery_message)
        self._abandonment_artwork = QImage()
        self._abandonment_artwork_identity = ""
        self._abandonment_scaled_artwork_cache = QImage()
        self._abandonment_scaled_artwork_cache_key: tuple[
            int, int, int, float, str
        ] | None = None
        self._pending_abandonment_manual_refresh = False
        self._pending_abandonment_rotation = False
        self._deferred_abandonment_presentation = None
        super().__init__(
            parent=parent,
            definition=definition,
            position=position,
            initial_view_model=initial_view_model,
            achievement_show_artwork=False,
            refresh_minutes=refresh_minutes,
        )
        if build_default_runtime:
            from widgets.steam_abandonment_runtime import AbandonmentRuntimeService

            self.set_runtime_service(
                AbandonmentRuntimeService(
                    runtime_generation=getattr(self, "_runtime_generation", None)
                ),
                owns_service=True,
            )

    def _authored_content_size(self):
        return abandonment_authored_size(
            show_artwork=self._abandonment_show_artwork,
            artwork_shape=self._abandonment_artwork_shape,
            artwork_size=self._abandonment_artwork_size,
            field_count=self._abandonment_field_slots,
        )

    def _calculate_content_size(self) -> QSize:
        authored = self._authored_content_size()
        return QSize(
            max(int(math.ceil(authored.width())), self.minimumWidth()),
            max(int(math.ceil(authored.height())), self.minimumHeight()),
        )

    def last_layout(self) -> AbandonmentCardLayout | None:
        return self._last_layout

    # ------------------------------------------------------------------
    # Runtime/model owner bridge
    # ------------------------------------------------------------------
    def _build_runtime_config(self):
        from widgets.steam_abandonment_runtime import AbandonmentRuntimeConfig

        return AbandonmentRuntimeConfig(
            selection=self._abandonment_selection,
            field_visibility=dict(self._abandonment_field_visibility),
            show_artwork=self._abandonment_show_artwork,
            artwork_shape=self._abandonment_artwork_shape,
            guilt_desaturater=self._abandonment_guilt_desaturater,
            guilt_desaturation_strength=self._abandonment_guilt_desaturation_strength,
            refresh_minutes=self._refresh_minutes,
            show_connection_info_icon=self._abandonment_show_connection_info_icon,
            show_rediscovery_message=self._abandonment_show_rediscovery_message,
        )

    def set_runtime_service(self, service: Optional[Any], *, owns_service: bool = False) -> None:
        """Attach the presentation-neutral Abandonment runtime/model owner."""

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
            service.configure(self._build_runtime_config())
            thread_manager = getattr(self, "_thread_manager", None)
            if thread_manager is not None:
                service.set_thread_manager(thread_manager)
            service.attach_consumer(self)
        except Exception:
            self._runtime_service = None
            self._owns_runtime_service = False
            try:
                service.detach_consumer(self)
            except Exception:
                pass
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

    def set_thread_manager(self, manager) -> None:
        super().set_thread_manager(manager)
        service = self._runtime_service
        if service is not None:
            service.set_thread_manager(manager)

    def is_abandonment_consumer_alive(self) -> bool:
        return bool(Shiboken.isValid(self))

    def on_abandonment_presentation(self, presentation: Any, *, animate: bool) -> None:
        self._apply_prepared_presentation(presentation, animate=animate)

    def request_abandonment_fade(self) -> None:
        self._request_coordinated_fade()

    def on_abandonment_rotation_due(self) -> bool:
        return self._request_cache_only_rotation()

    # ------------------------------------------------------------------
    # Presentation lifecycle / transition gates
    # ------------------------------------------------------------------
    def handle_double_click(self, _local_pos) -> bool:
        return self.request_manual_refresh()

    def _activate_impl(self) -> None:
        service = self._runtime_service
        if service is None:
            raise RuntimeError("Abandonment runtime service is not attached")
        if not self._ensure_thread_manager("Abandonment Issues activation"):
            raise RuntimeError("ThreadManager is not configured")
        if not service.start(start_fade_after_load=True):
            raise RuntimeError("Abandonment runtime service failed to start")

    def on_fade_complete(self) -> None:
        super().on_fade_complete()
        service = self._runtime_service
        if service is not None:
            service.on_presentation_fade_complete()

    def _reset_deferred_runtime_state(self) -> None:
        self._pending_abandonment_manual_refresh = False
        self._pending_abandonment_rotation = False
        self._deferred_abandonment_presentation = None

    def _deactivate_impl(self) -> None:
        self._reset_deferred_runtime_state()
        service = self._runtime_service
        if service is not None and service.is_running():
            service.stop()
        super()._deactivate_impl()

    def _cleanup_impl(self) -> None:
        self._reset_deferred_runtime_state()
        service = self._runtime_service
        if service is not None and service.is_running():
            service.stop()
        self._release_runtime_service()
        super()._cleanup_impl()

    def request_manual_refresh(self) -> bool:
        from widgets.service_widget_runtime import defer_refresh_if_transition

        if defer_refresh_if_transition(
            self,
            pending_attr="_pending_abandonment_manual_refresh",
            schedule_callback=self._schedule_deferred_manual_refresh,
            logger=logger,
            log_message="[STEAM] Deferred manual Abandonment Issues refresh during parent transition",
        ):
            return True
        service = self._runtime_service
        return bool(service is not None and service.request_manual_refresh())

    def _schedule_deferred_manual_refresh(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._run_deferred_manual_refresh)

    def _run_deferred_manual_refresh(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        if not self._pending_abandonment_manual_refresh:
            return
        if parent_transition_running(self):
            self._schedule_deferred_manual_refresh()
            return
        self._pending_abandonment_manual_refresh = False
        service = self._runtime_service
        if service is not None:
            service.request_manual_refresh()

    def _request_cache_only_rotation(self) -> bool:
        from widgets.service_widget_runtime import defer_refresh_if_transition

        if defer_refresh_if_transition(
            self,
            pending_attr="_pending_abandonment_rotation",
            schedule_callback=self._schedule_deferred_cache_rotation,
            logger=logger,
            log_message="[STEAM] Deferred Abandonment Issues rotation during parent transition",
        ):
            return True
        self._pending_abandonment_rotation = False
        service = self._runtime_service
        return bool(service is not None and service.request_cache_rotation())

    def _schedule_deferred_cache_rotation(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(1_000, self._run_deferred_cache_rotation)

    def _run_deferred_cache_rotation(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        if not self._pending_abandonment_rotation:
            return
        if parent_transition_running(self):
            self._schedule_deferred_cache_rotation()
            return
        self._pending_abandonment_rotation = False
        service = self._runtime_service
        if service is not None:
            service.request_cache_rotation()

    def _apply_prepared_presentation(
        self,
        presentation: Any,
        *,
        animate: bool,
    ) -> None:
        from widgets.service_widget_runtime import defer_value_if_transition

        if defer_value_if_transition(
            self,
            attr_name="_deferred_abandonment_presentation",
            value=(presentation, animate),
            clear_attrs=(),
            schedule_callback=self._schedule_deferred_presentation,
            logger=logger,
            log_message="[STEAM] Deferred Abandonment Issues presentation during parent transition",
        ):
            return
        self._commit_prepared_presentation(presentation, animate=animate)

    def _schedule_deferred_presentation(self) -> None:
        from core.threading.manager import ThreadManager

        ThreadManager.single_shot(250, self._apply_deferred_presentation)

    def _apply_deferred_presentation(self) -> None:
        from widgets.service_widget_runtime import parent_transition_running

        deferred = getattr(self, "_deferred_abandonment_presentation", None)
        if deferred is None:
            return
        if parent_transition_running(self):
            self._schedule_deferred_presentation()
            return
        self._deferred_abandonment_presentation = None
        presentation, animate = deferred
        self._commit_prepared_presentation(presentation, animate=bool(animate))

    def _commit_prepared_presentation(
        self,
        presentation: Any,
        *,
        animate: bool,
    ) -> None:
        model = presentation.model
        transition_key = (
            model.state,
            model.appid,
            presentation.artwork_identity,
            presentation.desaturation_bucket,
        )

        def _commit() -> None:
            self._view_model = model
            next_identity = str(presentation.artwork_identity or "")
            next_artwork_key = int(presentation.artwork.cacheKey())
            if (
                next_identity != self._abandonment_artwork_identity
                or next_artwork_key != int(self._abandonment_artwork.cacheKey())
            ):
                self._abandonment_artwork_identity = next_identity
                self._abandonment_artwork = QImage(presentation.artwork)
                self._abandonment_scaled_artwork_cache = QImage()
                self._abandonment_scaled_artwork_cache_key = None
            self._has_displayed_valid_data = True

        self.apply_content_transition(transition_key, _commit, animate=animate)

    def _scaled_abandonment_artwork(self, art_rect: QRectF, dpr: float) -> QImage:
        """Return the presenter's cached DPR-aware smooth cover crop."""

        if self._abandonment_artwork.isNull() or art_rect.isNull():
            return QImage()
        scale_dpr = max(1.0, float(dpr))
        target_width = max(1, int(round(art_rect.width() * scale_dpr)))
        target_height = max(1, int(round(art_rect.height() * scale_dpr)))
        cache_key = (
            int(self._abandonment_artwork.cacheKey()),
            target_width,
            target_height,
            scale_dpr,
            self._abandonment_artwork_shape,
        )
        if (
            self._abandonment_scaled_artwork_cache_key == cache_key
            and not self._abandonment_scaled_artwork_cache.isNull()
        ):
            return self._abandonment_scaled_artwork_cache

        scaled = self._abandonment_artwork.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - target_width) // 2)
        crop_y = max(0, (scaled.height() - target_height) // 2)
        prepared = scaled.copy(crop_x, crop_y, target_width, target_height)
        prepared.setDevicePixelRatio(scale_dpr)
        self._abandonment_scaled_artwork_cache = prepared
        self._abandonment_scaled_artwork_cache_key = cache_key
        return prepared

    def _paint_before_native_text(self) -> None:
        painter = None
        try:
            painter = QPainter(self)
            target = QRectF(
                0.0,
                0.0,
                max(1.0, float(self.width())),
                max(1.0, float(self.height())),
            )
            preview_layout = layout_abandonment_card(
                self._view_model,
                target,
                show_artwork=self._abandonment_show_artwork,
                artwork_shape=self._abandonment_artwork_shape,
                artwork_size=self._abandonment_artwork_size,
                field_slot_count=self._abandonment_field_slots,
            )
            dpr = max(1.0, float(self.devicePixelRatioF()))
            artwork = (
                self._scaled_abandonment_artwork(preview_layout.art_rect, dpr)
                if self._abandonment_show_artwork
                else QImage()
            )
            self._last_layout = render_abandonment_card(
                painter,
                self._view_model,
                target,
                font_family=self.get_font_family(),
                font_size=self.get_font_size(),
                text_color=self.get_text_color(),
                logo_pixmap=self._steam_logo,
                artwork_image=artwork,
                show_artwork=self._abandonment_show_artwork,
                artwork_shape=self._abandonment_artwork_shape,
                artwork_size=self._abandonment_artwork_size,
                accent_color=self._abandonment_accent_color,
                content_opacity=self.content_opacity(),
                field_slot_count=self._abandonment_field_slots,
            )
        finally:
            if painter is not None:
                painter.end()
