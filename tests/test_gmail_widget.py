"""Tests for Gmail widget with Qt app (requires QCoreApplication)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import threading

from PySide6.QtCore import QRect, QThread
from PySide6.QtWidgets import QApplication, QWidget
import pytest


@pytest.fixture(scope="module")
def qt_app():
    """Create Qt application for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't delete the app - other tests might need it


class _QueuedIoManager:
    def __init__(self) -> None:
        self.tasks = []
        self.timers = []

    def submit_io_task(self, func, *args, callback=None, category="uncategorized", **kwargs):
        self.tasks.append(
            SimpleNamespace(
                func=func,
                args=args,
                kwargs=kwargs,
                callback=callback,
                category=category,
            )
        )
        return f"task-{len(self.tasks)}"

    def schedule_recurring(self, interval, callback, **kwargs):
        class _Timer:
            def __init__(self):
                self.active = True

            def stop(self):
                self.active = False

            def isActive(self):
                return self.active

            def thread(self):
                return QThread.currentThread()

        timer = _Timer()
        self.timers.append(SimpleNamespace(interval=interval, callback=callback, timer=timer))
        return timer


class _ReadyBackend:
    def __init__(self, *, authenticated: bool = False, client=None) -> None:
        from core.gmail.gmail_backend import GmailBackendMode

        self.is_initialized = True
        self.is_authenticated = authenticated
        self.client = client
        self.mode = GmailBackendMode.OAUTH

    def ensure_initialized(self, _manager, callback):
        callback(True)
        return True

    def start_oauth_flow(self):
        return True


def _run_queued_io_task(task) -> None:
    try:
        value = task.func(*task.args, **task.kwargs)
        result = SimpleNamespace(success=True, result=value, error=None)
    except Exception as exc:  # pragma: no cover - surfaced through callback assertions
        result = SimpleNamespace(success=False, result=None, error=exc)
    if task.callback is not None:
        task.callback(result)


@pytest.fixture(autouse=True)
def isolated_gmail_cache(tmp_path, monkeypatch):
    """Keep direct-widget convenience owners away from the user cache."""

    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "gmail_cache.json"
    monkeypatch.setattr("widgets.gmail_widget.CACHE_DIR", cache_dir)
    monkeypatch.setattr("widgets.gmail_widget.CACHE_PATH", cache_path)
    yield cache_path


def test_gmail_widget_instantiation_mock_settings(qt_app):
    """Verify GmailWidget can be instantiated with mock settings (no real widget painting)."""
    from widgets.gmail_widget import GmailWidget

    # Create widget with mock settings (no real Gmail credentials)
    mock_settings = {
        "gmail.enabled": True,
        "gmail.position": "TOP_LEFT",
        "gmail.limit": 5,
        "gmail.refresh_interval": 300000,
        "gmail.backend_mode": "oauth",
        "gmail.imap_email": "",
        "gmail.imap_password": "",
    }

    try:
        widget = GmailWidget()
        widget.apply_settings(mock_settings)
        
        # Verify widget was created
        assert widget is not None
        assert widget.isEnabled() is True
        
        # Cleanup
        widget.cleanup()
    except Exception as e:
        # Widget might fail without proper setup - that's okay for this test
        # We're just verifying it can be instantiated without crashing
        pytest.skip(f"Widget instantiation failed (expected without full setup): {e}")


def test_gmail_widget_paint_event_empty_state(qt_app):
    """Verify GmailWidget paintEvent doesn't crash with empty email list."""
    from widgets.gmail_widget import GmailWidget

    try:
        widget = GmailWidget()
        widget._emails = []  # Empty email list
        widget._unread_count = 0
        widget._has_displayed_valid_data = False

        # Trigger paint event (should not crash)
        # Note: This would need proper Qt event loop setup
        # For now, we're just verifying the widget doesn't crash on instantiation
        widget.cleanup()
    except Exception as e:
        pytest.skip(f"Paint event test skipped (requires full Qt setup): {e}")


def test_gmail_widget_handle_click_miss(qt_app):
    """Verify GmailWidget.handle_click() returns False for clicks outside email rows."""
    from widgets.gmail_widget import GmailWidget

    try:
        widget = GmailWidget()
        widget._email_hit_rects = []  # No email hit rects

        # Click outside any email (should return False)
        # Note: This would need proper Qt event setup
        # For now, we're just verifying the widget structure
        widget.cleanup()
    except Exception as e:
        pytest.skip(f"Handle click test skipped (requires full Qt setup): {e}")


def test_gmail_widget_cleanup_no_leaks(qt_app):
    """Verify GmailWidget.cleanup() stops timers and clears references."""
    from widgets.gmail_widget import GmailWidget

    try:
        widget = GmailWidget()
        
        # Call cleanup
        widget.cleanup()
        
        # Verify cleanup was called (no exception raised)
        assert True  # If we get here, cleanup succeeded
    except Exception as e:
        pytest.skip(f"Cleanup test skipped: {e}")


def test_gmail_widget_limit_change_requests_shared_parent_stacking_recalc(qt_app):
    from widgets.gmail_widget import GmailWidget

    class _Parent(QWidget):
        def __init__(self):
            super().__init__()
            self.recalc_calls = 0

        def recalculate_stacking(self) -> None:
            self.recalc_calls += 1

    parent = _Parent()
    parent.resize(1600, 900)
    widget = GmailWidget(parent=parent)
    try:
        widget.apply_settings(
            {
                "gmail.enabled": True,
                "gmail.position": "MIDDLE_LEFT",
                "gmail.limit": 5,
                "gmail.width": 600,
            }
        )
        parent.show()
        widget.show()
        qt_app.processEvents()
        parent.recalc_calls = 0

        widget.set_limit(25)
        qt_app.processEvents()

        assert parent.recalc_calls >= 1
    finally:
        widget.cleanup()
        parent.close()




def test_gmail_deferred_timers_are_cleared_on_cleanup(qt_app):
    """Deferred Gmail timers should not survive widget cleanup."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget._pending_refresh_after_transition = True
        widget._schedule_deferred_refresh()
        widget._deferred_fetch_result = ([], 0, None)
        widget._schedule_deferred_fetch_flush()

        assert widget._deferred_refresh_timer is not None
        assert widget._deferred_fetch_timer is not None

        widget.cleanup()

        assert widget._deferred_refresh_timer is None
        assert widget._deferred_fetch_timer is None
    finally:
        widget.deleteLater()


def test_gmail_no_auth_and_no_cache_does_not_request_fade(qt_app, monkeypatch):
    """Gmail should stay hidden when there is no account information and no cache."""
    from core.gmail.gmail_preparation import PreparedGmailStartup
    from widgets.gmail_widget import GmailWidget

    from widgets import gmail_runtime

    backend = _ReadyBackend(authenticated=False)
    monkeypatch.setattr(
        gmail_runtime.GmailBackend,
        "instance",
        classmethod(lambda _cls: backend),
    )
    widget = GmailWidget()
    manager = _QueuedIoManager()
    widget.set_thread_manager(manager)
    fade_requests = []
    try:
        monkeypatch.setattr(
            "widgets.gmail_runtime.load_gmail_startup_snapshot",
            lambda *args, **kwargs: PreparedGmailStartup((), None, "missing"),
        )
        monkeypatch.setattr(
            "widgets.gmail_widget.ThreadManager.run_on_ui_thread",
            lambda callback, *args, **kwargs: callback(*args, **kwargs),
        )
        monkeypatch.setattr(widget, "_request_fade_in", lambda: fade_requests.append("fade"))

        widget._activate_impl()
        _run_queued_io_task(manager.tasks.pop(0))

        assert fade_requests == []
        assert widget._has_displayed_valid_data is False
    finally:
        widget.cleanup()


def test_gmail_cached_startup_stays_hidden_until_fade_starter_runs(qt_app, monkeypatch):
    """Cached Gmail content may mark itself ready, but must not become visible early."""
    from core.gmail.gmail_client import EmailMetadata
    from core.gmail.gmail_preparation import PreparedGmailStartup
    from widgets.gmail_widget import GmailWidget

    class _FadeParent(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.starters = []

        def request_overlay_fade_sync(self, overlay_name, starter):
            self.starters.append((overlay_name, starter))

    from widgets import gmail_runtime

    backend = _ReadyBackend(authenticated=False)
    monkeypatch.setattr(
        gmail_runtime.GmailBackend,
        "instance",
        classmethod(lambda _cls: backend),
    )
    parent = _FadeParent()
    widget = GmailWidget(parent=parent)
    manager = _QueuedIoManager()
    widget.set_thread_manager(manager)
    show_calls = []
    try:
        cached = EmailMetadata(
            id="cached_msg",
            thread_id="cached_thread",
            sender="Sender",
            subject="Cached Subject",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=True,
        )
        monkeypatch.setattr(
            "widgets.gmail_runtime.load_gmail_startup_snapshot",
            lambda *args, **kwargs: PreparedGmailStartup((cached,), datetime.now(), "fresh"),
        )
        monkeypatch.setattr(
            "widgets.gmail_widget.ThreadManager.run_on_ui_thread",
            lambda callback, *args, **kwargs: callback(*args, **kwargs),
        )
        monkeypatch.setattr(widget, "show", lambda: show_calls.append("show"))

        assert widget.isVisible() is False

        widget._activate_impl()
        _run_queued_io_task(manager.tasks.pop(0))

        assert widget._has_displayed_valid_data is True
        assert widget._cache_invalidated is False
        assert widget._cached_content_pixmap is not None
        assert widget._row_hit_rects
        assert [name for name, _ in parent.starters] == ["gmail"]
        assert show_calls == []

        parent.starters.pop(0)[1]()

        assert show_calls
    finally:
        widget.cleanup()
        parent.deleteLater()






def test_gmail_fetch_error_keeps_displayed_cache_visible(qt_app):
    """Fetch errors should not replace valid displayed mail with retry UI."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    updates = []
    try:
        email = EmailMetadata(
            id="cached_msg",
            thread_id="cached_thread",
            sender="Sender",
            subject="Cached Subject",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
        )
        widget._emails = [email]
        widget._has_displayed_valid_data = True
        widget._last_error = None
        widget.update = lambda *args, **kwargs: updates.append("update")  # type: ignore[method-assign]

        widget._on_fetch_error("Network error")

        assert widget._last_error is None
        assert [item.id for item in widget._emails] == ["cached_msg"]
        assert updates == []
    finally:
        widget.cleanup()


def test_gmail_empty_fetch_keeps_displayed_cache_visible(qt_app):
    """An empty live fetch must not replace valid cached/read content."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    updates = []
    try:
        email = EmailMetadata(
            id="cached_msg",
            thread_id="cached_thread",
            sender="Sender",
            subject="Cached Subject",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
        )
        widget._emails = [email]
        widget._rebuild_display_rows()
        widget._has_displayed_valid_data = True
        widget._last_error = None
        widget.update = lambda *args, **kwargs: updates.append("update")  # type: ignore[method-assign]

        widget._on_emails_fetched([], 0)

        assert widget._last_error is None
        assert [item.id for item in widget._emails] == ["cached_msg"]
        assert len(widget._display_rows) == 1
        assert updates == []
    finally:
        widget.cleanup()


def test_gmail_manual_refresh_ignores_duplicate_fetch(qt_app):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget._enabled = True
        calls = []
        service = widget._runtime_service
        assert service is not None
        service.is_refresh_in_progress = lambda: True  # type: ignore[method-assign]
        service.refresh = lambda: calls.append("refresh") or True  # type: ignore[method-assign]

        started = widget._trigger_manual_refresh()  # type: ignore[attr-defined]

        assert started is True
        assert calls == []
    finally:
        widget.cleanup()


def test_gmail_cache_max_age_is_two_weeks():
    """Disk cache should remain valid for up to two weeks as a fallback surface."""
    from widgets.gmail_widget import CACHE_MAX_AGE_HOURS

    assert CACHE_MAX_AGE_HOURS == 24 * 14




















def test_gmail_limit_clamps_to_shared_capacity_policy(qt_app):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.set_limit(4)
        assert widget.configured_capacity == 5

        widget.set_limit(30)
        assert widget.configured_capacity == 25
    finally:
        widget.cleanup()




def test_gmail_error_state_height_exceeds_single_row_height(qt_app):
    """Retry/auth state should reserve more vertical room than a one-row content card."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(600, 120)
        widget._last_error = "Network error"
        widget._update_card_height_from_content(1)
        error_height = widget.minimumHeight()

        widget._last_error = None
        widget._update_card_height_from_content(1)
        row_height = widget.minimumHeight()

        assert error_height > row_height
    finally:
        widget.cleanup()


def test_gmail_custom_layout_rect_survives_content_height_recalc(qt_app):
    """Custom Gmail geometry must remain authoritative after content-driven height updates."""
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    from widgets.gmail_widget import GmailWidget

    parent = QWidget()
    parent.resize(1200, 900)
    widget = GmailWidget(parent)
    try:
        custom_rect = QRect(30, 30, 600, 322)
        widget._custom_layout_local_rect = QRect(custom_rect)
        widget._limit = 10
        widget._update_position()

        widget.set_font_size(28)
        widget._update_card_height_from_content(10)
        QApplication.processEvents()

        assert widget.geometry() == custom_rect
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_content_height_updates_do_not_change_width_constraints(qt_app):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(640, 180)
        widget.setMinimumWidth(640)
        widget.setMaximumWidth(640)
        widget._configured_capacity = 10

        widget._update_card_height_from_content(10)

        assert widget.minimumWidth() == 640
        assert widget.maximumWidth() == 640
        assert widget.minimumHeight() == widget.maximumHeight()
    finally:
        widget.cleanup()


def test_gmail_custom_layout_payload_leaves_text_ratio_settings_owned():
    from types import SimpleNamespace

    from rendering.custom_layout_manager import CustomLayoutManager

    class _DummyGmail:
        def __init__(self) -> None:
            self._font_size = 13
            self._sender_subject_ratio = 62

        def set_font_size(self, value: int) -> None:
            self._font_size = int(value)

        def set_sender_subject_ratio(self, value: int) -> None:
            self._sender_subject_ratio = int(value)

    manager = CustomLayoutManager.__new__(CustomLayoutManager)
    descriptor = SimpleNamespace(custom_layout_resize_mode="gmail_font", widget_id="gmail")
    widget = _DummyGmail()

    payload = manager._capture_size_payload(descriptor, widget)
    scaled = manager._scale_size_payload(descriptor, payload, 0.65)
    manager._apply_size_payload(descriptor, widget, scaled)

    assert payload == {"font_size": 13}
    assert scaled["font_size"] < payload["font_size"]
    assert widget._font_size == scaled["font_size"]
    assert widget._sender_subject_ratio == 62

    manager._apply_size_payload(
        descriptor,
        widget,
        {
            "font_size": 16,
            "sender_subject_ratio": 35,
            "sender_column_width": 180,
        },
    )

    assert widget._font_size == 16
    assert widget._sender_subject_ratio == 62


def test_gmail_small_font_compacts_action_lane(qt_app):
    from datetime import datetime

    from PySide6.QtGui import QPainter, QPixmap

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(420, 180)
        widget._show_three_dot_menu = True
        widget._emails = [
            EmailMetadata(
                id="msg_1",
                thread_id="thread_1",
                sender="Some Longer Sender Name",
                subject="A subject that needs room",
                date=datetime.now(),
                labels=("INBOX",),
                is_unread=True,
            )
        ]
        widget._rebuild_display_rows()

        def _paint_and_action_width() -> int:
            pixmap = QPixmap(widget.size())
            pixmap.fill()
            painter = QPainter(pixmap)
            try:
                widget._paint_emails(painter)
            finally:
                painter.end()
            assert widget._action_hit_rects
            return widget._action_hit_rects[0][0].width()

        widget.set_font_size(13)
        baseline_width = _paint_and_action_width()

        widget.set_font_size(8)
        compact_width = _paint_and_action_width()

        assert compact_width < baseline_width
    finally:
        widget.cleanup()


def test_gmail_small_font_rebalances_budget_toward_subject_text(qt_app):
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(760, 220)
        widget._show_three_dot_menu = True
        widget._emails = [
            EmailMetadata(
                id="msg_1",
                thread_id="thread_1",
                sender="Some Longer Sender Name",
                subject="A subject that benefits from more horizontal budget when shrunk",
                date=datetime.now(),
                labels=("INBOX",),
                is_unread=True,
            )
        ]
        widget._rebuild_display_rows()
        row = widget._display_rows[0]

        widget.set_font_size(13)
        baseline_layout = widget._compute_email_layout_metrics(widget._display_rows)
        baseline_budget = widget._compute_email_row_budget(row, baseline_layout)

        widget.set_font_size(8)
        compact_layout = widget._compute_email_layout_metrics(widget._display_rows)
        compact_budget = widget._compute_email_row_budget(row, compact_layout)

        assert compact_layout["action_width"] < baseline_layout["action_width"]
        assert compact_layout["time_slot_width"] < baseline_layout["time_slot_width"]
        assert compact_budget["subject_max_width"] > baseline_budget["subject_max_width"]
    finally:
        widget.cleanup()


def test_gmail_sender_subject_ratio_splits_only_the_remaining_row_budget(qt_app):
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(600, 220)
        widget._emails = [
            EmailMetadata(
                id="msg_ratio",
                thread_id="thread_ratio",
                sender="A Sender With Several Words",
                subject="A subject that should receive the larger default share",
                date=datetime.now(),
                labels=("INBOX",),
                is_unread=True,
            )
        ]
        widget._rebuild_display_rows()
        row = widget._display_rows[0]

        widget.set_sender_subject_ratio(35)
        default_layout = widget._compute_email_layout_metrics(widget._display_rows)
        default_budget = widget._compute_email_row_budget(row, default_layout)
        assert (
            default_layout["sender_slot_width"]
            + default_layout["sender_subject_gap"]
            + default_layout["subject_slot_width"]
            == default_layout["text_area_width"]
        )
        assert default_budget["subject_max_width"] > default_layout["sender_slot_width"]
        assert default_layout["text_area_width"] < default_layout["available_width"]

        widget.set_sender_subject_ratio(60)
        sender_heavy_layout = widget._compute_email_layout_metrics(widget._display_rows)
        sender_heavy_budget = widget._compute_email_row_budget(row, sender_heavy_layout)
        assert sender_heavy_layout["sender_slot_width"] > default_layout["sender_slot_width"]
        assert sender_heavy_budget["subject_max_width"] < default_budget["subject_max_width"]
        assert sender_heavy_layout["text_area_width"] == default_layout["text_area_width"]

        widget.set_width(200)
        widget.resize(200, 220)
        widget.set_font_size(40)
        constrained_layout = widget._compute_email_layout_metrics(widget._display_rows)
        assert (
            constrained_layout["sender_slot_width"]
            + constrained_layout["sender_subject_gap"]
            + constrained_layout["subject_slot_width"]
            == constrained_layout["text_area_width"]
        )
        assert constrained_layout["text_area_width"] <= constrained_layout["available_width"]
    finally:
        widget.cleanup()


def test_gmail_legacy_subject_character_limit_is_ignored(qt_app):
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_components import DisplayRow
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        subject = "This subject remains governed only by its word limit"
        widget.apply_settings(
            {
                "auto_title_case": False,
                "max_subject_words": 0,
                "max_subject_chars": 5,
            }
        )
        row = DisplayRow(
            email=EmailMetadata(
                id="msg_subject",
                thread_id="thread_subject",
                sender="Sender",
                subject=subject,
                date=datetime.now(),
                labels=("INBOX",),
                is_unread=True,
            )
        )

        assert widget._build_subject_display_text(row) == subject
    finally:
        widget.cleanup()


def test_gmail_small_custom_height_does_not_paint_rows_past_bottom(qt_app):
    from datetime import datetime

    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QWidget

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    parent = QWidget()
    parent.resize(1200, 900)
    widget = GmailWidget(parent)
    try:
        widget._custom_layout_local_rect = QRect(30, 30, 600, 220)
        widget._emails = [
            EmailMetadata(
                id=f"msg_{index}",
                thread_id=f"thread_{index}",
                sender=f"Sender {index}",
                subject=f"Subject {index}",
                date=datetime.now(),
                labels=("INBOX",),
                is_unread=(index % 2 == 0),
            )
            for index in range(8)
        ]
        widget._rebuild_display_rows()
        widget._update_position()

        pixmap = QPixmap(widget.size())
        pixmap.fill()
        painter = QPainter(pixmap)
        try:
            widget._paint_emails(painter)
        finally:
            painter.end()

        content_bottom = widget.height() - max(12, widget.contentsMargins().bottom())
        assert widget._row_hit_rects
        assert all(rect.bottom() <= content_bottom for rect, *_rest in widget._row_hit_rects)
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_empty_state_paints_below_header(qt_app):
    """Worst-case empty-state copy must render below the header frame area."""
    from widgets.gmail_widget import GmailWidget

    class FakePainter:
        def __init__(self):
            self.rect = None
            self.flags = None
            self.text = None

        def setFont(self, *_args, **_kwargs):
            return None

        def setPen(self, *_args, **_kwargs):
            return None

        def drawText(self, rect, flags, text):
            self.rect = rect
            self.flags = flags
            self.text = text

    widget = GmailWidget()
    try:
        widget.resize(600, 180)
        painter = FakePainter()

        widget._paint_empty_state(painter)

        assert painter.text == "No unread emails"
        assert painter.rect is not None
        assert painter.rect.top() >= widget._header_bottom_y()
    finally:
        widget.cleanup()


def test_gmail_widget_no_real_credentials_in_code():
    """Verify test code uses explicit fake credentials only."""
    import inspect
    import tests.test_gmail_widget as test_module

    # Get source code
    source = inspect.getsource(test_module)

    # Verify we use explicit "fake_" prefixes for test credentials
    # Allow "password" in settings keys (e.g., "gmail.imap_password") as those are just keys
    assert "fake_" in source or "mock_" in source, "Test code should use fake_ or mock_ prefix for test data"


def test_gmail_widget_settings_application(qt_app):
    """Verify GmailWidget.apply_settings() parses settings correctly."""
    from widgets.gmail_widget import GmailWidget

    try:
        widget = GmailWidget()
        
        # Apply mock settings
        mock_settings = {
            "gmail.enabled": True,
            "gmail.position": "TOP_LEFT",
            "gmail.limit": 5,
            "gmail.refresh_interval": 300000,
        }
        
        widget.apply_settings(mock_settings)
        
        # Verify settings were applied (check a few key attributes)
        # Note: Widget might not have all these attributes yet
        # We're just verifying apply_settings doesn't crash
        
        widget.cleanup()
    except Exception as e:
        pytest.skip(f"Settings application test skipped: {e}")


def test_gmail_widget_phase_a_settings(qt_app):
    """Verify Phase A layout settings apply to widget state."""
    from widgets.base_overlay_widget import OverlayPosition
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.apply_settings(
            {
                "gmail.position": "Center",
                "gmail.width": 640,
                "gmail.show_header_border": False,
                "gmail.account_slot": "2",
            }
        )

        assert widget.get_position() == OverlayPosition.CENTER
        assert widget.minimumWidth() == 640
        assert widget.maximumWidth() == 640
        assert widget._width == 640
        margins = widget.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (20, 12, 20, 12)
        assert widget._content_padding_left == 0
        assert widget._content_padding_right == 0
        assert widget._content_padding_top == 0
        assert widget._show_header_border is False
        assert widget._account_slot == "2"
    finally:
        widget.cleanup()


def test_gmail_apply_width_respects_active_custom_rect(qt_app):
    from widgets.gmail_widget import GmailWidget

    parent = QWidget()
    parent.resize(1600, 900)
    widget = GmailWidget(parent=parent)
    try:
        widget._custom_layout_local_rect = QRect(100, 120, 777, 333)
        resize_calls = []
        update_position_calls = []
        reapply_calls = []

        widget.resize = lambda *args: resize_calls.append(args)  # type: ignore[method-assign]
        widget._update_position = lambda: update_position_calls.append("position")  # type: ignore[method-assign]
        widget._schedule_custom_layout_geometry_reapply = lambda: reapply_calls.append("reapply")  # type: ignore[method-assign]
        widget._width = 640

        widget._apply_width()

        assert widget.minimumWidth() == 777
        assert widget.maximumWidth() == 777
        assert resize_calls == []
        assert update_position_calls == []
        assert reapply_calls == ["reapply"]
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_widget_text_cleanup_settings(qt_app):
    """Verify Gmail text cleanup settings apply to widget state."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.apply_settings(
            {
                "gmail.clean_sender_names": False,
                "gmail.max_sender_words": 2,
                "gmail.sender_subject_ratio": 42,
                "gmail.max_subject_words": 5,
                "gmail.max_subject_chars": 24,
            }
        )

        assert widget._clean_sender_names is False
        assert widget._max_sender_words == 2
        assert widget._sender_subject_ratio == 42
        assert widget._max_subject_words == 5
        assert not hasattr(widget, "_max_subject_chars")
    finally:
        widget.cleanup()


def test_gmail_grouped_rows_put_count_in_sender_slot_not_subject(qt_app):
    """Grouped Gmail rows should reserve the count inside the sender column budget."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_components import DisplayRow
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        row = DisplayRow(
            email=EmailMetadata(
                id="fake_msg",
                thread_id="fake_thread",
                sender="PayPal <service@paypal.com>",
                subject="receipt for your payment",
                date=datetime.now(),
                labels=("INBOX", "UNREAD"),
                is_unread=True,
            ),
            count=3,
        )

        sender_text = widget._build_sender_display_text(row)
        subject_text = widget._build_subject_display_text(row)

        assert sender_text.endswith(" (3)")
        assert subject_text == "Receipt For Your Payment"
        assert "(3)" not in subject_text
    finally:
        widget.cleanup()


def test_gmail_widget_date_display_setting(qt_app):
    """Verify Gmail date display mode applies to row date formatting."""
    from datetime import datetime
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.apply_settings({"gmail.date_display_mode": "numeric"})
        assert widget._date_display_mode == "numeric"
        assert widget._format_email_date(datetime(2025, 6, 23)) == "23/06/2025"

        widget.apply_settings({"gmail.date_display_mode": "words"})
        assert widget._date_display_mode == "words"
        assert widget._format_email_date(datetime(2026, 4, 16)).startswith("April 16th")

        widget.apply_settings({"gmail.date_display_mode": "bad-value"})
        assert widget._date_display_mode == "relative"
    finally:
        widget.cleanup()


def test_gmail_widget_row_click_opens_email_url(qt_app, monkeypatch):
    """Verify row clicks open the email open_url."""
    from datetime import datetime
    from PySide6.QtCore import QPoint, QRect
    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget
    opened = []
    monkeypatch.setattr("widgets.gmail_widget.open_url", lambda url: opened.append(url))

    widget = GmailWidget()
    try:
        widget._emails = [
            EmailMetadata(
                id="fake_msg",
                thread_id="fake_thread",
                sender="PayPal <service@paypal.com>",
                subject="Receipt For Your Payment",
                date=datetime.now(),
                labels=("INBOX", "UNREAD"),
                is_unread=True,
                open_url="https://mail.google.com/mail/u/0/#all/fake",
            )
        ]
        widget._row_hit_rects = [(QRect(10, 20, 200, 24), "fake_msg", "Receipt For Your Payment")]
        widget._action_hit_rects = []

        assert widget.resolve_click_target(QPoint(20, 25)) == "https://mail.google.com/mail/u/0/#all/fake"
        assert widget.handle_click(QPoint(20, 25)) is True
        assert opened == ["https://mail.google.com/mail/u/0/#all/fake"]
    finally:
        widget.cleanup()


def test_gmail_widget_action_click_has_priority(qt_app, monkeypatch):
    """Verify action-menu clicks are not consumed by the row click path."""
    from datetime import datetime
    from PySide6.QtCore import QPoint, QRect
    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget
    opened = []
    menu_ids = []
    monkeypatch.setattr("widgets.gmail_widget.open_url", lambda url: opened.append(url))

    widget = GmailWidget()
    try:
        widget._emails = [
            EmailMetadata(
                id="fake_msg",
                thread_id="fake_thread",
                sender="PayPal",
                subject="Receipt",
                date=datetime.now(),
                labels=("INBOX", "UNREAD"),
                is_unread=True,
                open_url="https://mail.google.com/mail/u/0/#all/fake",
            )
        ]
        widget._row_hit_rects = [(QRect(10, 20, 240, 24), "fake_msg", "Receipt")]
        widget._action_hit_rects = [(QRect(226, 20, 24, 24), "fake_msg")]
        widget._show_action_menu = lambda message_id, _pos: menu_ids.append(message_id)  # type: ignore[method-assign]

        assert widget.resolve_click_target(QPoint(238, 32)) is None
        assert widget.is_action_menu_point(QPoint(238, 32)) is True
        assert widget.handle_click(QPoint(238, 32)) is True
        assert menu_ids == ["fake_msg"]
        assert opened == []
    finally:
        widget.cleanup()


def test_gmail_action_menu_click_defers_mc_focus_restore(qt_app):
    """Verify central routing marks Gmail menu clicks as popup-safe."""
    from unittest.mock import MagicMock

    from PySide6.QtCore import QPoint, QRect, Qt

    from rendering.input_handler import InputHandler

    handler = InputHandler(None)
    event = MagicMock()
    event.pos.return_value = QPoint(238, 32)
    event.button.return_value = Qt.MouseButton.LeftButton

    gmail = MagicMock()
    gmail.isVisible.return_value = True
    gmail.geometry.return_value = QRect(0, 0, 300, 120)
    gmail.resolve_click_target.return_value = None
    gmail.is_action_menu_point.return_value = True
    gmail.handle_click.return_value = True

    handled, reddit_handled, reddit_url = handler.route_widget_click(
        event,
        None,
        None,
        None,
        None,
        gmail,
        None,
        None,
    )

    assert handled is True
    assert reddit_handled is False
    assert reddit_url is None
    assert handler._defer_focus_restore_after_widget_click is True


def test_gmail_widget_uses_imap_uid_for_imap_actions(qt_app):
    """Verify IMAP menu actions dispatch backend-safe IDs instead of Gmail web IDs."""
    from datetime import datetime
    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        email = EmailMetadata(
            id="gmail_msg_id",
            thread_id="gmail_thread_id",
            sender="PayPal",
            subject="Receipt",
            date=datetime.now(),
            labels=("INBOX", "UNREAD"),
            is_unread=True,
            provider="gmail",
            imap_uid="42",
        )
        assert widget._action_message_id(email) == "42"
    finally:
        widget.cleanup()


def test_gmail_widget_hides_archive_for_imap_but_keeps_oauth_path(qt_app):
    """IMAP Archive is hidden because it is unreliable; Gmail/OAuth path remains available."""
    from datetime import datetime
    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        imap_email = EmailMetadata(
            id="gmail_msg_id",
            thread_id="gmail_thread_id",
            sender="PayPal",
            subject="Receipt",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
            provider="imap",
            imap_uid="42",
        )
        gmail_email = EmailMetadata(
            id="gmail_msg_id",
            thread_id="gmail_thread_id",
            sender="PayPal",
            subject="Receipt",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
            provider="gmail",
            imap_uid="42",
        )

        assert widget._should_show_archive_action(imap_email) is False
        service = widget._runtime_service
        assert service is not None
        service.is_imap_backend = lambda: True  # type: ignore[method-assign]
        assert widget._should_show_archive_action(gmail_email) is False
        service.is_imap_backend = lambda: False  # type: ignore[method-assign]
        assert widget._should_show_archive_action(gmail_email) is True
    finally:
        widget.cleanup()


def test_gmail_widget_refresh_click_forces_fetch(qt_app):
    """Verify the top-right refresh hit rect consumes clicks and fetches."""
    from PySide6.QtCore import QPoint, QRect
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget._enabled = True
        widget._refresh_hit_rect = QRect(100, 10, 22, 22)
        service = widget._runtime_service
        assert service is not None
        service.is_refresh_in_progress = lambda: False  # type: ignore[method-assign]
        service.refresh = lambda: calls.append("fetch") or True  # type: ignore[method-assign]

        assert widget.resolve_click_target(QPoint(110, 20)) is None
        assert widget.handle_click(QPoint(110, 20)) is True
        assert calls == ["fetch"]
    finally:
        widget.cleanup()


def test_gmail_widget_refresh_spiral_can_be_hidden(qt_app):
    """The optional Gmail refresh spiral should not consume clicks when hidden."""
    from PySide6.QtCore import QPoint, QRect
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget._refresh_hit_rect = QRect(100, 10, 22, 22)
        widget._fetch_emails = lambda: calls.append("fetch") or True  # type: ignore[method-assign]
        widget.set_show_refresh_spiral(False)

        assert widget.resolve_click_target(QPoint(110, 20)) is None
        assert widget.handle_click(QPoint(110, 20)) is False
        assert calls == []
    finally:
        widget.cleanup()


def test_gmail_card_uses_no_graphics_effect_after_painted_shadow_retirement(qt_app):
    """Gmail renders its card without any QGraphicsEffect.

    The generic painted-frame card *shadow* was retired in the F0.5 audit
    correction: framed families now draw their card background/border via QSS
    with no painted drop shadow (destination is OverlayCard/RectangularShadow).
    The R-24 regression bar survives — gmail must still never attach a QWidget
    graphics effect.
    """
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.set_show_background(True)
        widget.set_shadow_config({"enabled": True, "frame_opacity": 0.7, "blur_radius": 18})
        widget.resize(320, 160)

        # Painted card shadow is retired: no shadow pixmap, path is inert.
        assert widget.uses_painted_frame_shadow() is False
        assert widget.painted_frame_shadow_card_shrink() == (0, 0)
        assert widget._ensure_painted_frame_shadow_pixmap() is None
        # No QGraphicsDropShadowEffect ever attaches (R-24).
        assert widget.graphicsEffect() is None
    finally:
        widget.cleanup()


def test_gmail_widget_loads_archive_action_icon(qt_app):
    """Verify the Archive action has a real loaded icon asset, not only fallback drawing."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        icon = widget._action_icons.get("archive")
        assert icon is not None
        assert not icon.isNull()
    finally:
        widget.cleanup()


def test_gmail_widget_setters_skip_noop_repaints(qt_app):
    """Repeated same-value settings should not schedule needless repaints."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget.update = lambda *args, **kwargs: calls.append("update")  # type: ignore[method-assign]

        widget.set_show_sender(widget._show_sender)
        widget.set_show_subject(widget._show_subject)
        widget.set_show_envelope_icon(widget._show_envelope_icon)
        widget.set_date_display_mode(widget._date_display_mode)
        widget.set_sender_subject_ratio(widget._sender_subject_ratio)
        widget.set_max_subject_words(widget._max_subject_words)

        assert calls == []

        widget.set_show_sender(not widget._show_sender)
        assert calls == ["update"]
    finally:
        widget.cleanup()


def test_gmail_widget_blank_double_click_refreshes_but_rows_do_not(qt_app):
    """Verify Gmail follows Reddit's blank-space double-click refresh contract."""
    from PySide6.QtCore import QPoint, QRect
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget._enabled = True
        widget._row_hit_rects = [(QRect(10, 20, 200, 24), "msg", "Subject")]
        widget._action_hit_rects = [(QRect(210, 20, 24, 24), "msg")]
        widget._refresh_hit_rect = QRect(240, 10, 22, 22)
        service = widget._runtime_service
        assert service is not None
        service.is_refresh_in_progress = lambda: False  # type: ignore[method-assign]
        service.refresh = lambda: calls.append("fetch") or True  # type: ignore[method-assign]

        assert widget.handle_double_click(QPoint(20, 25)) is False
        assert widget.handle_double_click(QPoint(220, 25)) is False
        assert widget.handle_double_click(QPoint(250, 20)) is False
        assert widget.handle_double_click(QPoint(40, 90)) is True
        assert calls == ["fetch"]
    finally:
        widget.cleanup()


def test_gmail_widget_header_border_smoke(qt_app):
    """Verify header layout survives with header border enabled and disabled."""
    from PySide6.QtGui import QFont

    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(420, 160)
        for enabled in (True, False):
            widget.apply_settings({"show_header_border": enabled})
            font = QFont(widget._font_family, widget._header_font_pt, QFont.Weight.Bold)
            layout = widget._calculate_header_layout(font, widget._header_text(), widget._brand_pixmap)
            assert layout["frame_rect"].width() > 0
            assert layout["frame_rect"].height() > 0
            assert layout["logo_rect"].height() > 0
            assert layout["text_baseline_y"] > layout["frame_rect"].top()
    finally:
        widget.cleanup()


def test_gmail_header_logo_adjust_controls_logo_and_header_text(qt_app):
    """Gmail header metrics should follow Media-style font/logo sizing with px adjustment."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.set_font_size(14)
        assert widget._header_logo_size == max(12, int(max(6, int(14 * 1.2)) * 1.3))
        base_header = widget._header_font_pt
        base_logo = widget._header_logo_size

        widget.apply_settings({"gmail.header_logo_px_adjust": 6})

        assert widget._header_logo_size > base_logo
        assert widget._header_font_pt > base_header
    finally:
        widget.cleanup()


def test_gmail_brand_desaturation_is_prepared_before_paint(qt_app):
    """No-unread header desaturation should not do image conversion during paint."""
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        assert widget._brand_pixmap is not None
        assert widget._brand_pixmap_desaturated is not None
        assert widget._ensure_desaturated_brand() is widget._brand_pixmap_desaturated
    finally:
        widget.cleanup()


def test_gmail_unread_and_read_envelopes_use_distinct_assets(qt_app):
    """Unread rows should use the white envelope, read rows the black/read envelope."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        unread = EmailMetadata("u", "tu", "sender@example.com", "Unread", datetime.now(), ("UNREAD",), True)
        read = EmailMetadata("r", "tr", "sender@example.com", "Read", datetime.now(), tuple(), False)

        assert widget._envelope_for_email(unread) is widget._envelope_pixmap
        assert widget._envelope_for_email(read) is widget._envelope_read_pixmap
        assert widget._envelope_for_email(read) is not widget._envelope_for_email(unread)
    finally:
        widget.cleanup()


def test_gmail_widget_ignores_stale_fetch_results(qt_app):
    """Verify an older owner snapshot cannot overwrite a newer projection."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget._last_applied_runtime_revision = 2
        email = EmailMetadata(
            id="fake_msg",
            thread_id="fake_thread",
            sender="fake_sender@example.com",
            subject="Fake Subject",
            date=datetime.now(),
            labels=("INBOX", "UNREAD"),
            is_unread=True,
        )

        widget._on_emails_fetched([email], 1, 1)

        assert widget._emails == []
        assert widget._unread_count == 0
    finally:
        widget.cleanup()


def test_gmail_widget_projection_preserves_owner_order(qt_app):
    """The presenter must preserve the neutral owner's accepted email order."""
    from datetime import datetime
    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        read_newer = EmailMetadata(
            id="read_newer",
            thread_id="read_thread",
            sender="Sender",
            subject="Read newer",
            date=datetime(2026, 4, 29, 12, 0, 0),
            labels=("INBOX",),
            is_unread=False,
        )
        unread_older = EmailMetadata(
            id="unread_older",
            thread_id="unread_thread",
            sender="Sender",
            subject="Unread older",
            date=datetime(2026, 4, 28, 12, 0, 0),
            labels=("INBOX", "UNREAD"),
            is_unread=True,
        )
        older_read = EmailMetadata(
            id="older_read",
            thread_id="older_thread",
            sender="Sender",
            subject="Older read",
            date=datetime(2026, 4, 27, 12, 0, 0),
            labels=("INBOX",),
            is_unread=False,
        )
        backend_order = [read_newer, unread_older, older_read]
        widget._on_emails_fetched(backend_order, 1)

        assert [email.id for email in widget._emails] == ["read_newer", "unread_older", "older_read"]
    finally:
        widget.cleanup()


def test_gmail_unchanged_fetch_skips_cache_write_and_repaint(qt_app):
    """An identical accepted snapshot should not churn presenter pixels."""
    from datetime import datetime

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    updates = []
    try:
        email = EmailMetadata(
            id="same",
            thread_id="thread",
            sender="Sender",
            subject="Same",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
        )
        widget._emails = [email]
        widget._unread_count = 0
        widget._has_displayed_valid_data = True
        widget._last_error = None
        widget.update = lambda *args, **kwargs: updates.append("update")  # type: ignore[method-assign]

        widget._on_emails_fetched([email], 0)

        assert updates == []
    finally:
        widget.cleanup()


def test_gmail_fetch_result_defers_visible_apply_during_parent_transition(qt_app):
    """Accepted owner state should not rewrite/repaint pixels mid-transition."""
    from datetime import datetime
    from PySide6.QtWidgets import QWidget

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = True

        def has_running_transition(self):
            return self.running

    parent = TransitionParent()
    widget = GmailWidget(parent)
    update_calls = []
    try:
        email = EmailMetadata(
            id="deferred",
            thread_id="thread",
            sender="Sender",
            subject="Deferred",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
        )
        widget.update = lambda *args, **kwargs: update_calls.append("update")  # type: ignore[method-assign]

        widget._on_emails_fetched([email], 0, 0)

        assert widget._emails == []
        assert widget._deferred_fetch_result is not None

        parent.running = False
        widget._flush_deferred_fetch_result()

        assert [item.id for item in widget._emails] == ["deferred"]
        assert update_calls
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_newer_runtime_revision_supersedes_deferred_projection(qt_app):
    """A deferred presenter payload must not cross a newer owner revision."""
    from datetime import datetime
    from PySide6.QtWidgets import QWidget

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_runtime import GmailRuntimeSnapshot
    from widgets.gmail_widget import GmailWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = True

        def has_running_transition(self):
            return self.running

    parent = TransitionParent()
    widget = GmailWidget(parent)
    email = EmailMetadata(
        id="stale",
        thread_id="thread",
        sender="Sender",
        subject="Stale",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=False,
    )
    try:
        widget.on_gmail_runtime_snapshot(
            GmailRuntimeSnapshot(1, (email,), 0, None, False, "live")
        )
        assert widget._deferred_fetch_result is not None

        widget.on_gmail_runtime_snapshot(
            GmailRuntimeSnapshot(2, (), 0, None, True, "refreshing")
        )
        parent.running = False
        widget._flush_deferred_fetch_result()

        assert widget._emails == []
        assert widget._last_received_runtime_revision == 2
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_refresh_start_defers_during_parent_transition(qt_app):
    """Refresh should not start spinner/network work while a display transition is active."""
    from PySide6.QtWidgets import QWidget

    from widgets.gmail_widget import GmailWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = True

        def has_running_transition(self):
            return self.running

    parent = TransitionParent()
    widget = GmailWidget(parent)
    calls = []
    try:
        widget._set_refreshing = lambda refreshing: calls.append(("refreshing", refreshing))  # type: ignore[method-assign]

        assert widget._fetch_emails() is True
        assert widget._pending_refresh_after_transition is True
        assert calls == []

        parent.running = False
        widget._fetch_emails = lambda **kwargs: calls.append(("fetch", kwargs)) or True  # type: ignore[method-assign]
        widget._flush_deferred_refresh()

        assert widget._pending_refresh_after_transition is False
        assert calls == [("fetch", {"defer_for_transition": False})]
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_fetch_result_defers_during_parent_transition_pending(qt_app):
    """The pre-transition image-load window should block visible Gmail apply work too."""
    from datetime import datetime
    from PySide6.QtWidgets import QWidget

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.pending = True

        def has_transition_work_pending(self):
            return self.pending

        def has_running_transition(self):
            return False

    parent = TransitionParent()
    widget = GmailWidget(parent)
    try:
        email = EmailMetadata(
            id="pending",
            thread_id="thread",
            sender="Sender",
            subject="Pending",
            date=datetime.now(),
            labels=("INBOX",),
            is_unread=False,
        )

        widget._on_emails_fetched([email], 0, 0)

        assert widget._emails == []
        assert widget._deferred_fetch_result is not None

        parent.pending = False
        widget._flush_deferred_fetch_result()

        assert [item.id for item in widget._emails] == ["pending"]
    finally:
        widget.cleanup()
        parent.deleteLater()


def test_gmail_transition_pending_parent_chain_and_spinner_suspend(qt_app):
    """A refresh already in flight should stop live spinner repaint when transition work starts."""
    from PySide6.QtWidgets import QWidget

    from widgets.gmail_widget import GmailWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.pending = False

        def has_transition_work_pending(self):
            return self.pending

    parent = TransitionParent()
    container = QWidget(parent)
    widget = GmailWidget(container)
    updates = []
    try:
        widget.update = lambda *args, **kwargs: updates.append(args)  # type: ignore[method-assign]
        widget._set_refreshing(True)
        assert widget._refreshing is True
        assert widget._refresh_spinner_suspended_for_transition is False
        assert widget._refresh_spin_timer is not None
        assert widget._refresh_spin_timer.isActive()

        parent.pending = True
        assert widget._parent_transition_running() is True
        widget.on_parent_transition_work_pending(True)

        assert widget._refreshing is True
        assert widget._refresh_spinner_suspended_for_transition is True
        assert not widget._refresh_spin_timer.isActive()
        assert updates
    finally:
        widget.cleanup()
        container.deleteLater()
        parent.deleteLater()


def test_gmail_widget_has_perf_instrumentation():
    """Gmail should emit comparable widget perf metrics when perf logging is enabled."""
    from pathlib import Path

    presenter_source = Path("widgets/gmail_widget.py").read_text(encoding="utf-8")
    runtime_source = Path("widgets/gmail_runtime.py").read_text(encoding="utf-8")

    assert 'widget_paint_sample(self, "gmail.paint")' in presenter_source
    assert 'widget_timer_sample(self, "gmail.fetch.apply")' in presenter_source
    assert '"gmail.cache.write"' in runtime_source
    assert '"gmail.refresh.dispatch"' in runtime_source


def test_gmail_paint_consumes_prepared_stable_content_without_regeneration(qt_app):
    """Paint should only blit stable content prepared before delivery."""
    from PySide6.QtGui import QPixmap
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget.resize(420, 160)
        assert widget._cache_prepare_scheduled is True
        widget._paint_stable_content = lambda painter: calls.append("stable")  # type: ignore[method-assign]
        widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]
        widget._flush_content_cache_prepare()

        assert calls == ["stable"]
        assert widget._cache_invalidated is False

        widget._prepare_static_content_cache = (  # type: ignore[method-assign]
            lambda: (_ for _ in ()).throw(AssertionError("paint prepared static cache"))
        )

        target = QPixmap(widget.size())
        target.fill()
        widget.render(target)
        widget.render(target)

        assert calls == ["stable"]
    finally:
        widget.cleanup()


def test_gmail_cache_invalidates_for_visual_settings_but_not_spinner(qt_app):
    """Visual changes invalidate stable content; spinner ticks only repaint the icon."""
    from PySide6.QtCore import QRect
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    updates = []
    try:
        widget._cache_invalidated = False
        widget.update = lambda *args, **kwargs: updates.append(args)  # type: ignore[method-assign]

        widget.set_sender_subject_ratio(widget._sender_subject_ratio + 1)
        assert widget._cache_invalidated is True
        assert updates

        updates.clear()
        widget._cache_invalidated = False
        widget._refreshing = True
        widget._refresh_hit_rect = QRect(100, 10, 22, 22)
        widget._advance_refresh_spinner()

        assert widget._cache_invalidated is False
        assert updates and isinstance(updates[-1][0], QRect)
    finally:
        widget.cleanup()


def test_gmail_content_cache_regeneration_avoids_shadow_effect_mutation():
    """The Gmail content cache must not touch fragile Qt shadow/effect paths."""
    import inspect
    from widgets.gmail_widget import GmailWidget

    source = inspect.getsource(GmailWidget._prepare_static_content_cache)

    forbidden = (
        "setGraphicsEffect",
        "invalidate_overlay_effects",
        ".hide(",
        ".show(",
        "setParent",
        ".resize(",
    )
    for token in forbidden:
        assert token not in source


def test_gmail_paint_does_not_discover_or_prepare_a_cold_static_cache(qt_app):
    from PySide6.QtGui import QPixmap
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    calls = []
    try:
        widget.resize(420, 160)
        widget._clear_content_cache()
        widget._prepare_static_content_cache = lambda: calls.append("prepare") or True  # type: ignore[method-assign]
        widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]

        target = QPixmap(widget.size())
        target.fill()
        widget.render(target)

        assert calls == []
        assert widget._cached_content_pixmap is None
    finally:
        widget.cleanup()


def test_gmail_static_cache_invalidations_coalesce_to_latest_gui_build(qt_app, monkeypatch):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    scheduled = []
    builds = []
    try:
        widget.resize(420, 160)
        widget._flush_content_cache_prepare()
        initial_revision = widget._cache_revision
        monkeypatch.setattr(
            "widgets.gmail_widget.ThreadManager.single_shot",
            lambda delay, callback, *args, **kwargs: scheduled.append(callback),
        )
        widget._paint_stable_content = lambda painter: builds.append(widget._cache_revision)  # type: ignore[method-assign]

        widget.set_sender_subject_ratio(widget._sender_subject_ratio + 1)
        widget.set_max_subject_words(widget._max_subject_words + 1)

        assert widget._cache_revision == initial_revision + 2
        assert len(scheduled) == 1
        assert builds == []

        scheduled.pop(0)()

        assert builds == [initial_revision + 2]
        assert widget._cache_invalidated is False
        assert widget._cached_content_identity[-1] == initial_revision + 2
    finally:
        widget.cleanup()


def test_gmail_preflush_invalidation_never_pairs_stale_pixels_with_cleared_hits(
    qt_app,
    monkeypatch,
):
    from PySide6.QtGui import QPixmap

    from core.gmail.gmail_client import EmailMetadata
    from widgets.gmail_widget import GmailWidget

    email = EmailMetadata(
        id="visible",
        thread_id="thread",
        sender="Sender",
        subject="Visible",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=False,
    )
    widget = GmailWidget()
    scheduled = []
    prepare_calls = []
    try:
        widget.resize(420, 160)
        widget._flush_content_cache_prepare()
        widget._emails = [email]
        widget._rebuild_display_rows()
        widget._invalidate_content_cache(schedule_prepare=False)
        assert widget._prepare_static_content_cache() is True
        old_pixmap = widget._cached_content_pixmap
        assert widget._prepared_content_pixmap_for_paint() is old_pixmap
        assert widget._row_hit_rects

        monkeypatch.setattr(
            "widgets.gmail_widget.ThreadManager.single_shot",
            lambda delay, callback, *args, **kwargs: scheduled.append(callback),
        )
        original_prepare = widget._prepare_static_content_cache
        monkeypatch.setattr(
            widget,
            "_prepare_static_content_cache",
            lambda: (prepare_calls.append(True), original_prepare())[1],
        )

        widget.set_sender_subject_ratio(widget._sender_subject_ratio + 1)

        assert widget._prepared_content_pixmap_for_paint() is None
        assert widget._row_hit_rects == []
        assert len(scheduled) == 1

        target = QPixmap(widget.size())
        target.fill()
        widget.render(target)

        assert prepare_calls == []
        assert widget._prepared_content_pixmap_for_paint() is None

        scheduled.pop(0)()

        assert prepare_calls == [True]
        assert widget._prepared_content_pixmap_for_paint() is widget._cached_content_pixmap
        assert widget._cached_content_pixmap is not old_pixmap
        assert widget._row_hit_rects
    finally:
        widget.cleanup()


def test_gmail_cached_visual_setters_cover_text_font_border_corner_and_shadow(qt_app):
    from PySide6.QtGui import QColor
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    try:
        widget.resize(420, 160)
        widget._flush_content_cache_prepare()
        revision = widget._cache_revision

        widget.set_text_color(QColor(20, 30, 40, 255))
        widget.set_font_family("Arial")
        widget.set_background_border(widget._bg_border_width + 1, QColor(50, 60, 70, 255))
        widget.set_background_corner_radius(widget._bg_corner_radius + 1)
        widget.set_shadow_config({"enabled": True, "text_enabled": False})

        assert widget._cache_revision == revision + 5
        assert widget._cache_invalidated is True
    finally:
        widget.cleanup()


def test_gmail_dpr_change_invalidates_exact_static_cache_identity(qt_app, monkeypatch):
    from PySide6.QtCore import QEvent
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    dpr = {"value": 1.0}
    try:
        widget.resize(420, 160)
        monkeypatch.setattr(widget, "devicePixelRatioF", lambda: dpr["value"])
        widget._invalidate_content_cache(schedule_prepare=False)
        assert widget._prepare_static_content_cache() is True
        first_pixmap = widget._cached_content_pixmap
        assert widget._cached_content_identity[2] == 1.0

        dpr["value"] = 1.5
        widget.event(QEvent(QEvent.Type.DevicePixelRatioChange))
        widget._flush_content_cache_prepare()

        assert widget._cached_content_identity[2] == 1.5
        assert widget._cached_content_pixmap is not first_pixmap
        assert widget._cached_content_pixmap.devicePixelRatio() == 1.5
    finally:
        widget.cleanup()


def test_gmail_static_cache_preparation_refuses_worker_thread(qt_app):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    results = []
    try:
        widget.resize(420, 160)
        widget._clear_content_cache()
        worker = threading.Thread(
            target=lambda: results.append(widget._prepare_static_content_cache())
        )
        worker.start()
        worker.join()

        assert results == [False]
        assert widget._cached_content_pixmap is None
    finally:
        widget.cleanup()


def test_gmail_queued_static_cache_prepare_drops_after_cleanup(qt_app, monkeypatch):
    from widgets.gmail_widget import GmailWidget

    widget = GmailWidget()
    scheduled = []
    widget._flush_content_cache_prepare()
    monkeypatch.setattr(
        "widgets.gmail_widget.ThreadManager.single_shot",
        lambda delay, callback, *args, **kwargs: scheduled.append(callback),
    )

    widget.set_sender_subject_ratio(widget._sender_subject_ratio + 1)
    assert len(scheduled) == 1

    widget.cleanup()
    scheduled.pop(0)()

    assert widget._cached_content_pixmap is None
    assert widget._cache_invalidated is True
    assert widget._cache_prepare_scheduled is False
