from types import SimpleNamespace

from rendering.display_context_menu import _get_current_visualizer_mode


def test_get_current_visualizer_mode_prefers_live_visualizer_widget() -> None:
    class _Settings:
        def get(self, key: str, default=None):
            if key == "widgets":
                return {"spotify_visualizer": {"mode": "devcurve"}}
            return default

    widget = SimpleNamespace(
        spotify_visualizer_widget=SimpleNamespace(_vis_mode_str="blob"),
        settings_manager=_Settings(),
    )

    assert _get_current_visualizer_mode(widget) == "devcurve"


def test_get_current_visualizer_mode_falls_back_to_settings_when_local_widget_missing() -> None:
    class _Settings:
        def get(self, key: str, default=None):
            if key == "widgets":
                return {"spotify_visualizer": {"mode": "devcurve"}}
            return default

    widget = SimpleNamespace(
        spotify_visualizer_widget=None,
        settings_manager=_Settings(),
    )

    assert _get_current_visualizer_mode(widget) == "devcurve"


def test_get_current_visualizer_mode_uses_live_widget_only_when_settings_missing() -> None:
    widget = SimpleNamespace(
        spotify_visualizer_widget=SimpleNamespace(_vis_mode_str="blob"),
        settings_manager=None,
    )

    assert _get_current_visualizer_mode(widget) == "blob"
