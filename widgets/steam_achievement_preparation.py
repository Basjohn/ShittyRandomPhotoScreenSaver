"""Worker-safe model and image preparation for Steam Achievement Pulse.

The runtime service owns the resulting state. This module maps one neutral
cache snapshot into the Qt-free semantic card model and decodes provider-owned
artwork into QImage payloads off the GUI thread. It owns no QWidget, QPainter,
QPixmap, timer, task scheduler, request generation or provider lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from PySide6.QtGui import QImage

from core.steam.achievement_pulse import AchievementPulseSelection
from widgets.steam_card_models import (
    SteamCardViewModel,
    build_achievement_pulse_view_model,
)


@dataclass(frozen=True)
class AchievementPulseRuntimeConfig:
    """Immutable inputs required by one Achievement Pulse runtime."""

    selection: AchievementPulseSelection = field(default_factory=AchievementPulseSelection)
    field_visibility: Mapping[str, bool] = field(default_factory=dict)
    latest_unlock_count: int = 1
    show_latest_artwork: bool = True
    show_artwork: bool = True
    artwork_shape: str = "portrait"
    refresh_minutes: int = 10
    show_connection_info_icon: bool = True


@dataclass(frozen=True)
class AchievementPulsePreparedPresentation:
    """Stable semantic model and decoded dynamic-image state."""

    model: SteamCardViewModel
    artwork: QImage = field(default_factory=QImage)
    artwork_identity: str = ""
    artwork_key: str = ""
    latest_artwork: QImage = field(default_factory=QImage)
    latest_artwork_identity: str = ""
    latest_artwork_key: str = ""


def prepare_achievement_model(
    config: AchievementPulseRuntimeConfig,
    snapshot: Any,
    *,
    connection_needs_attention: bool = False,
) -> SteamCardViewModel:
    """Build one semantic Achievement Pulse model in the caller's worker."""

    return build_achievement_pulse_view_model(
        snapshot.resolved,
        cache_age_seconds=snapshot.cache_age_seconds,
        connection_needs_attention=connection_needs_attention,
        show_connection_info_icon=config.show_connection_info_icon,
        field_visibility=dict(config.field_visibility),
        latest_unlock_count=config.latest_unlock_count,
    )


def prepare_achievement_artwork(
    *,
    profile_key: str,
    appid: int,
    artwork_shape: str,
) -> tuple[QImage, str]:
    """Fetch/cache and decode one app artwork payload off the GUI thread."""

    from core.settings.storage_paths import get_steam_cache_dir
    from core.steam.assets import SteamAssetRecord, fetch_steam_app_artwork

    asset = fetch_steam_app_artwork(
        cache_dir=get_steam_cache_dir(profile_key=profile_key) / "assets",
        appid=appid,
        artwork_shape=artwork_shape,
    )
    asset_path = asset.path if isinstance(asset, SteamAssetRecord) else None
    image = QImage(str(asset_path)) if asset_path is not None else QImage()
    return image, str(asset_path) if asset_path is not None and not image.isNull() else ""


def prepare_latest_achievement_artwork(
    *,
    profile_key: str,
    icon_url: str,
) -> tuple[QImage, str]:
    """Fetch/cache and decode one schema-owned achievement icon off-thread."""

    from core.settings.storage_paths import get_steam_cache_dir
    from core.steam.assets import SteamAssetRecord, fetch_steam_achievement_icon

    safe_url = str(icon_url or "").strip()
    if not safe_url:
        return QImage(), ""
    asset = fetch_steam_achievement_icon(
        cache_dir=get_steam_cache_dir(profile_key=profile_key) / "assets",
        url=safe_url,
    )
    asset_path = asset.path if isinstance(asset, SteamAssetRecord) else None
    image = QImage(str(asset_path)) if asset_path is not None else QImage()
    return image, str(asset_path) if asset_path is not None and not image.isNull() else ""
