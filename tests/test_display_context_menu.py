from types import SimpleNamespace

from rendering.display_context_menu import _get_current_visualizer_mode, on_context_visualizer_selected


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


class _VisualizerSwitchTarget:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def switch_to_mode(self, mode_id: str) -> None:
        self.calls.append(mode_id)


def test_context_visualizer_mode_switch_prefers_invoking_display_visualizer() -> None:
    local = _VisualizerSwitchTarget()
    remote = _VisualizerSwitchTarget()
    widget = SimpleNamespace(
        spotify_visualizer_widget=local,
        get_all_instances=lambda: [
            SimpleNamespace(spotify_visualizer_widget=remote),
        ],
    )

    on_context_visualizer_selected(widget, "spectrum")

    assert local.calls == ["spectrum"]
    assert remote.calls == []


def test_context_visualizer_mode_switch_targets_sole_global_visualizer_when_local_missing() -> None:
    remote = _VisualizerSwitchTarget()
    widget = SimpleNamespace(
        spotify_visualizer_widget=None,
        get_all_instances=lambda: [
            SimpleNamespace(spotify_visualizer_widget=None),
            SimpleNamespace(spotify_visualizer_widget=remote),
        ],
    )

    on_context_visualizer_selected(widget, "bubble")

    assert remote.calls == ["bubble"]


def test_context_visualizer_mode_switch_does_not_guess_when_multiple_global_visualizers_exist() -> None:
    first = _VisualizerSwitchTarget()
    second = _VisualizerSwitchTarget()
    widget = SimpleNamespace(
        spotify_visualizer_widget=None,
        get_all_instances=lambda: [
            SimpleNamespace(spotify_visualizer_widget=first),
            SimpleNamespace(spotify_visualizer_widget=second),
        ],
    )

    on_context_visualizer_selected(widget, "devcurve")

    assert first.calls == []
    assert second.calls == []
