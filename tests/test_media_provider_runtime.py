from __future__ import annotations

from unittest.mock import MagicMock

from rendering.widget_manager import WidgetManager


class _ProviderAwareWidget:
    def __init__(self) -> None:
        self.providers = []

    def set_provider_runtime(self, provider):
        self.providers.append(str(provider))


class _StubSettingsManager:
    class _Signal:
        def connect(self, _handler):
            return None

        def disconnect(self, _handler):
            return None

    def __init__(self, widgets):
        self._widgets = widgets
        self.saved = False
        self.settings_changed = self._Signal()

    def get(self, key, default=None):
        if key == "widgets":
            return self._widgets
        return default

    def set(self, key, value):
        if key == "widgets":
            self._widgets = value

    def save(self):
        self.saved = True


def test_refresh_media_config_syncs_provider_runtime():
    manager = WidgetManager(MagicMock())
    media_widget = _ProviderAwareWidget()
    volume_widget = _ProviderAwareWidget()
    manager.register_widget("media", media_widget)
    manager.register_widget("spotify_volume", volume_widget)

    manager._refresh_media_config(
        {
            "media": {
                "enabled": True,
                "provider": "musicbee",
                "color": [255, 255, 255, 255],
                "bg_color": [0, 0, 0, 255],
                "border_color": [255, 255, 255, 255],
                "border_opacity": 0.8,
                "background_opacity": 0.5,
                "show_controls": True,
                "show_header_frame": True,
            }
        }
    )

    assert media_widget.providers == ["musicbee"]
    assert volume_widget.providers == ["musicbee"]


def test_handle_media_provider_failover_persists_settings():
    manager = WidgetManager(MagicMock())
    media_widget = _ProviderAwareWidget()
    volume_widget = _ProviderAwareWidget()
    manager.register_widget("media", media_widget)
    manager.register_widget("spotify_volume", volume_widget)
    manager._settings_manager = _StubSettingsManager(
        {
            "media": {
                "enabled": True,
                "provider": "spotify",
            }
        }
    )

    manager.handle_media_provider_failover("musicbee", source="test")

    assert media_widget.providers == ["musicbee"]
    assert volume_widget.providers == ["musicbee"]
    assert manager._settings_manager.get("widgets")["media"]["provider"] == "musicbee"
    assert manager._settings_manager.saved is True
