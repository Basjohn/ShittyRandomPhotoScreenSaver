"""Worker-safe model and dynamic-image preparation for Steam Abandonment.

The runtime service owns the resulting state. This module only converts one
neutral cache snapshot into a semantic card model plus a decoded QImage
payload and stable artwork identity. It owns no QWidget, timer, provider,
request generation, cache cadence or source lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtGui import QImage

from core.logging.logger import get_logger
from core.steam.abandonment_issues import AbandonmentSelection


logger = get_logger(__name__)


@dataclass(frozen=True)
class AbandonmentRuntimeConfig:
    """Presentation-neutral inputs required by one Abandonment runtime."""

    selection: AbandonmentSelection = field(default_factory=AbandonmentSelection)
    field_visibility: Mapping[str, bool] = field(default_factory=dict)
    show_artwork: bool = True
    artwork_shape: str = "portrait"
    guilt_desaturater: bool = False
    guilt_desaturation_strength: int = 55
    refresh_minutes: int = 10
    show_connection_info_icon: bool = True
    show_rediscovery_message: bool = True


@dataclass(frozen=True)
class AbandonmentPreparedPresentation:
    """Stable model/image payload delivered to the current presenter."""

    model: Any
    artwork: QImage
    artwork_identity: str
    desaturation_bucket: int


def achievement_evidence_requested(field_visibility: Mapping[str, bool]) -> bool:
    """Return whether visible shelves require selected-game achievement data."""

    from widgets.steam_abandonment_components import ABANDONMENT_FIELD_DEFAULTS

    return any(
        bool(field_visibility.get(field_id, ABANDONMENT_FIELD_DEFAULTS[field_id]))
        for field_id in ("achievements", "last_unlock")
    )


def decode_abandonment_artwork(source_path: Path | None) -> QImage:
    """Decode source-resolution artwork in the caller's worker job."""

    if source_path is None:
        return QImage()
    image = QImage(str(source_path))
    return image if not image.isNull() else QImage()


def prepare_abandonment_presentation(
    config: AbandonmentRuntimeConfig,
    snapshot: Any,
    *,
    profile_key: str,
    allow_asset_network: bool,
    connection_needs_attention: bool = False,
) -> AbandonmentPreparedPresentation:
    """Build one semantic model and decoded artwork payload off the GUI thread."""

    from core.settings.storage_paths import get_steam_cache_dir
    from core.steam.assets import (
        SteamAssetRecord,
        abandonment_desaturation_bucket,
        fetch_steam_app_artwork,
        find_cached_steam_app_artwork,
        prepare_desaturated_steam_artwork,
        steam_app_artwork_variant_order,
    )
    from core.steam.models import SteamResultStatus
    from widgets.steam_abandonment_components import (
        abandonment_shelf_diagnostics,
        build_abandonment_view_model,
    )

    field_visibility = dict(config.field_visibility)
    model = build_abandonment_view_model(
        snapshot.resolved,
        cache_age_seconds=snapshot.cache_age_seconds,
        connection_needs_attention=connection_needs_attention,
        show_connection_info_icon=config.show_connection_info_icon,
        show_rediscovery_message=config.show_rediscovery_message,
        field_visibility=field_visibility,
    )
    requested, rendered, unavailable, evidence = abandonment_shelf_diagnostics(
        snapshot.resolved,
        model,
        field_visibility,
    )
    logger.info(
        "[STEAM][ABANDONMENT_SHELVES] appid=%s requested=%s rendered=%s "
        "unavailable=%s evidence=%s",
        model.appid,
        ",".join(requested) or "none",
        ",".join(rendered) or "none",
        ",".join(unavailable) or "none",
        ",".join(evidence) or "none",
    )

    asset_path: Path | None = None
    artwork_outcome = "disabled"
    resolved_artwork_shape = "none"
    bucket = 0
    if config.show_artwork and model.appid is not None:
        asset_dir = get_steam_cache_dir(profile_key=profile_key) / "assets"
        artwork_shapes = steam_app_artwork_variant_order(config.artwork_shape)
        for index, artwork_shape in enumerate(artwork_shapes):
            asset_path = find_cached_steam_app_artwork(
                cache_dir=asset_dir,
                appid=model.appid,
                artwork_shape=artwork_shape,
            )
            if asset_path is None:
                continue
            resolved_artwork_shape = artwork_shape
            artwork_outcome = (
                "cache_hit" if index == 0 else f"fallback_cache_hit:{artwork_shape}"
            )
            break

        if asset_path is None and allow_asset_network:
            asset = fetch_steam_app_artwork(
                cache_dir=asset_dir,
                appid=model.appid,
                artwork_shape=artwork_shapes[0],
            )
            if isinstance(asset, SteamAssetRecord):
                asset_path = asset.path
                resolved_artwork_shape = artwork_shapes[0]
                artwork_outcome = "hydrated"
            else:
                status = getattr(getattr(asset, "status", None), "value", "unavailable")
                artwork_outcome = f"unavailable:{status}"
                if getattr(asset, "status", None) in {
                    SteamResultStatus.NOT_FOUND,
                    SteamResultStatus.ASSET_INVALID,
                }:
                    fallback_shape = artwork_shapes[1]
                    fallback_asset = fetch_steam_app_artwork(
                        cache_dir=asset_dir,
                        appid=model.appid,
                        artwork_shape=fallback_shape,
                    )
                    if isinstance(fallback_asset, SteamAssetRecord):
                        asset_path = fallback_asset.path
                        resolved_artwork_shape = fallback_shape
                        artwork_outcome = f"fallback_hydrated:{fallback_shape}"
                    else:
                        fallback_status = getattr(
                            getattr(fallback_asset, "status", None),
                            "value",
                            "unavailable",
                        )
                        artwork_outcome = f"unavailable:{fallback_status}"
        elif asset_path is None:
            artwork_outcome = "cache_miss_network_disabled"

        if asset_path is not None:
            bucket = abandonment_desaturation_bucket(
                inactivity_days=snapshot.resolved.inactivity_days,
                enabled=(
                    config.guilt_desaturater
                    and snapshot.resolved.last_played_confidence == "verified"
                ),
                maximum_percent=config.guilt_desaturation_strength,
                threshold_days=config.selection.minimum_inactivity_days,
            )
            asset_path = prepare_desaturated_steam_artwork(
                source_path=asset_path,
                cache_dir=asset_dir,
                desaturation_percent=bucket,
            )

    artwork_identity = str(asset_path or "")
    artwork = decode_abandonment_artwork(asset_path)
    if asset_path is not None and artwork.isNull():
        artwork_outcome = "decode_failed"
    if config.show_artwork and model.appid is not None:
        logger.info(
            "[STEAM][ABANDONMENT_ARTWORK] appid=%s backlog=%s/%s outcome=%s "
            "requested_shape=%s resolved_shape=%s network_allowed=%s",
            model.appid,
            snapshot.resolved.queue_position,
            snapshot.resolved.queue_count,
            artwork_outcome,
            config.artwork_shape,
            resolved_artwork_shape,
            allow_asset_network,
        )

    return AbandonmentPreparedPresentation(
        model=model,
        artwork=artwork,
        artwork_identity=artwork_identity,
        desaturation_bucket=bucket,
    )
