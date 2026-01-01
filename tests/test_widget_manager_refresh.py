from rendering.widget_manager import WidgetManager


class _FakeSpotifyVis:
    def __init__(self):
        self.last_sensitivity = None
        self.last_floor = None

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        self.last_sensitivity = (recommended, sensitivity)

    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        self.last_floor = (dynamic_enabled, manual_floor)


def test_refresh_spotify_visualizer_config_applies_typed_settings():
    """Ensure live refresh applies typed sensitivity/floor settings to the widget."""
    manager = WidgetManager(parent=None, resource_manager=None)
    fake_vis = _FakeSpotifyVis()
    manager._widgets["spotify_visualizer"] = fake_vis

    cfg = {
        "spotify_visualizer": {
            "adaptive_sensitivity": False,
            "sensitivity": 2.2,
            "dynamic_floor": False,
            "manual_floor": 1.4,
        }
    }

    manager._refresh_spotify_visualizer_config(cfg)

    assert fake_vis.last_sensitivity == (False, 2.2)
    assert fake_vis.last_floor == (False, 1.4)
