from __future__ import annotations

from unittest.mock import MagicMock

from rendering.widget_manager import WidgetManager


class _ProviderAwareWidget:
    def __init__(self) -> None:
        self.providers = []
        self.runtime_targets = []

    def set_provider_runtime(self, provider):
        self.providers.append(str(provider))

    def set_runtime_volume_source(self, provider, source_app_user_model_id):
        self.runtime_targets.append((str(provider), str(source_app_user_model_id)))


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
    manager.register_widget("media", media_widget)

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
                "spotify_volume_enabled": False,
                "mute_button_enabled": False,
            }
        }
    )

    assert media_widget.providers == ["musicbee"]


def test_handle_spotify_browser_provider_failover_persists_settings():
    manager = WidgetManager(MagicMock())
    media_widget = _ProviderAwareWidget()
    manager.register_widget("media", media_widget)
    manager._settings_manager = _StubSettingsManager(
        {
            "media": {
                "enabled": True,
                "provider": "spotify",
                "spotify_volume_enabled": False,
                "mute_button_enabled": False,
            }
        }
    )

    manager.handle_media_provider_failover("spotify_browser", source="test")

    assert media_widget.providers == ["spotify_browser"]
    assert manager._settings_manager.get("widgets")["media"]["provider"] == "spotify_browser"
    assert manager._settings_manager.get("widgets")["media"] == {
        "enabled": True,
        "provider": "spotify_browser",
        "spotify_volume_enabled": False,
        "mute_button_enabled": False,
    }
    assert manager._settings_manager.saved is True


def test_browser_volume_runtime_target_routes_through_media_anchor_without_persistence():
    from widgets.media_widget import MediaWidget

    manager = WidgetManager(MagicMock())
    volume_owner = _ProviderAwareWidget()
    media_anchor = MagicMock()
    media_anchor._volume_runtime_service = volume_owner
    manager._settings_manager = _StubSettingsManager(
        {"media": {"enabled": True, "provider": "spotify_browser"}}
    )

    MediaWidget.on_media_runtime_volume_target(
        media_anchor, "spotify_browser", "firefox.exe"
    )

    assert volume_owner.runtime_targets == [("spotify_browser", "firefox.exe")]
    assert manager._settings_manager.get("widgets")["media"] == {
        "enabled": True,
        "provider": "spotify_browser",
    }
    assert manager._settings_manager.saved is False


def test_invalid_provider_stays_inert_and_is_not_overwritten_by_failover():
    manager = WidgetManager(MagicMock())
    media_widget = _ProviderAwareWidget()
    manager.register_widget("media", media_widget)
    manager._settings_manager = _StubSettingsManager(
        {"media": {"enabled": True, "provider": "retired_alias"}}
    )

    manager._sync_media_provider_runtime("retired_alias")
    manager.handle_media_provider_failover("spotify_browser", source="stale_callback")

    assert media_widget.providers == ["retired_alias"]
    assert manager._settings_manager.get("widgets")["media"]["provider"] == "retired_alias"
    assert manager._settings_manager.saved is False
