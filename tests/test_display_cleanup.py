from types import SimpleNamespace

from rendering import display_cleanup
from rendering.display_gl_init import cleanup_widget


class _Compositor:
    def __init__(self, events):
        self._events = events

    def cleanup(self):
        self._events.append("compositor_cleanup")

    def hide(self):
        self._events.append("compositor_hide")

    def setParent(self, parent):
        self._events.append(("compositor_parent", parent))


class _Target:
    def __init__(self):
        self.cleaned = 0
        self.hidden = 0

    def cleanup(self):
        self.cleaned += 1

    def hide(self):
        self.hidden += 1


def test_cleanup_widget_clears_owner_attribute():
    target = _Target()
    owner = SimpleNamespace(media_widget=target)

    cleanup_widget(owner, "media_widget", "MEDIA")

    assert target.cleaned == 1
    assert target.hidden == 1
    assert owner.media_widget is None


def test_cleanup_widget_allows_non_widget_manager_without_hide():
    target = SimpleNamespace(cleanup=lambda: None)
    owner = SimpleNamespace(_pixel_shift_manager=target)

    cleanup_widget(owner, "_pixel_shift_manager", "PIXEL_SHIFT")

    assert owner._pixel_shift_manager is None


def test_display_destroy_cleanup_is_idempotent_and_releases_child_gl_before_compositor():
    events = []

    def _cleanup_widget(attr_name, _tag, stop_method="cleanup"):
        events.append(("widget_cleanup", attr_name, stop_method))

    widget = SimpleNamespace(
        _destroy_cleanup_done=False,
        settings_manager=None,
        _settings_listener_connected=False,
        _screen=None,
        _coordinator=SimpleNamespace(
            release_focus=lambda _widget: events.append("release_focus"),
            uninstall_event_filter=lambda _widget: events.append("uninstall_filter"),
        ),
        _gl_compositor=_Compositor(events),
        _destroy_render_surface=lambda: events.append("render_surface_cleanup"),
        _cleanup_widget=_cleanup_widget,
        _ctrl_cursor_hint=None,
        _transition_controller=None,
        _current_transition=None,
        _cancel_transition_watchdog=lambda: events.append("watchdog_cancel"),
    )

    display_cleanup.on_destroyed(widget)
    display_cleanup.on_destroyed(widget)

    assert events.count("compositor_cleanup") == 1
    assert events.count(("widget_cleanup", "spotify_visualizer_widget", "cleanup")) == 1
    assert events.index(("widget_cleanup", "spotify_visualizer_widget", "cleanup")) < events.index(
        "compositor_cleanup"
    )
    assert events.index("compositor_cleanup") < events.index("render_surface_cleanup")
    assert widget._gl_compositor is None
