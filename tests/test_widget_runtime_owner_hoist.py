from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

from core.resources.manager import ResourceManager
from rendering.display_cleanup import cleanup_runtime
from rendering.display_modes import DisplayMode
from rendering.display_widget import DisplayWidget
from rendering.widget_manager import WidgetManager
from rendering.widget_runtime_manager import WidgetRuntimeManager
from rendering.widget_runtime_services import RuntimeServiceSpec


def test_production_display_owns_exact_injected_widget_runtime_manager(qt_app) -> None:
    display = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=None,
        resource_manager=ResourceManager(),
        runtime_generation=901,
    )
    owner = display._widget_runtime_manager
    manager = display._widget_manager
    try:
        assert owner is not None
        assert manager is not None
        assert manager.runtime_manager is owner
        assert manager._runtime_manager is owner
        assert manager._owns_runtime_manager is False
        assert owner.has_bound_host is True

        display.cleanup_runtime(reason="owner_hoist_test")

        assert display._widget_manager is None
        assert display._widget_runtime_manager is None
        assert owner.is_retired is True
        assert owner.has_bound_host is False
    finally:
        if not display._runtime_cleanup_complete:
            display.cleanup_runtime(reason="owner_hoist_test_finally")
        display.deleteLater()


def test_direct_widget_manager_retains_isolated_owner_compatibility(qt_app) -> None:
    parent = QWidget()
    manager = WidgetManager(parent, ResourceManager())
    owner = manager.runtime_manager
    try:
        assert owner is not None
        assert manager._owns_runtime_manager is True
        assert owner.has_bound_host is True

        manager.cleanup()

        assert owner.is_retired is True
        assert owner.has_bound_host is False
    finally:
        manager.cleanup()
        parent.deleteLater()


def test_injected_widget_manager_detaches_without_retiring_display_owner(qt_app) -> None:
    parent = QWidget()
    owner = WidgetRuntimeManager()
    manager = WidgetManager(
        parent,
        ResourceManager(),
        runtime_manager=owner,
    )
    try:
        manager.cleanup()

        assert manager.runtime_manager is None
        assert owner.is_retired is False
        assert owner.has_bound_host is False
    finally:
        manager.cleanup()
        owner.cleanup()
        parent.deleteLater()


def test_display_cleanup_detaches_presenter_before_retiring_services(
    qt_app, monkeypatch
) -> None:
    from rendering import widget_runtime_services

    events: list[str] = []

    class _Service:
        pass

    class _Consumer(QWidget):
        def __init__(self, parent: QWidget) -> None:
            super().__init__(parent)
            self.service = None

        def set_runtime_service(self, service) -> None:
            self.service = service

        def cleanup(self) -> None:
            events.append("widget_cleanup")
            self.service = None

    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "hoist_probe",
        RuntimeServiceSpec(
            build=lambda _widget_id, _config: _Service(),
            inject=lambda widget, service: widget.set_runtime_service(service),
            retire=lambda _service: events.append("service_retire"),
        ),
    )

    parent = QWidget()
    owner = WidgetRuntimeManager()
    manager = WidgetManager(
        parent,
        ResourceManager(),
        runtime_manager=owner,
    )
    consumer = _Consumer(parent)
    manager.register_widget("hoist_probe", consumer)
    service = owner.ensure_widget_service("hoist_probe", consumer, {})
    assert service is not None

    class _Display:
        screen_index = 0
        _runtime_cleanup_complete = False
        _custom_layout_manager = None
        settings_manager = None
        _settings_listener_connected = False
        _screen = None
        _transition_controller = None
        _current_transition = None
        _input_handler = None
        _image_presenter = None
        _transition_factory = None
        _ctrl_cursor_hint = None
        _gl_compositor = None

        def __init__(self) -> None:
            self._widget_manager = manager
            self._widget_runtime_manager = owner
            self._coordinator = SimpleNamespace(
                unregister_instance=lambda *_args: None,
                release_focus=lambda *_args: None,
                uninstall_event_filter=lambda *_args: None,
            )

        def shutdown_render_pipeline(self, _reason: str) -> None:
            return None

        def _cleanup_widget(self, attr_name: str, *_args, **_kwargs) -> None:
            setattr(self, attr_name, None)

        def _cancel_transition_watchdog(self) -> None:
            return None

        def _destroy_render_surface(self) -> None:
            return None

    display = _Display()
    try:
        cleanup_runtime(display, reason="owner_hoist_order_test")

        assert events == ["widget_cleanup", "service_retire"]
        assert display._widget_manager is None
        assert display._widget_runtime_manager is None
        assert display._runtime_cleanup_complete is True
        assert owner.is_retired is True
    finally:
        manager.cleanup()
        owner.cleanup()
        consumer.deleteLater()
        parent.deleteLater()
