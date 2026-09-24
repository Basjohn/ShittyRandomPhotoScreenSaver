"""Bounded CUSTOM feed slot identity and headless source configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.settings.default_contract import require_canonical_default

from .models import FeedSourceSpec, FeedViewMode
from .normalization import endpoint_fingerprint
from .transport import normalize_feed_address, validate_feed_url


CUSTOM_FEED_WIDGET_IDS = tuple(f"feeds_custom_{index}" for index in range(1, 5))
_VALID_VIEW_MODES = frozenset({"list", "grid", "compact"})


@dataclass(frozen=True)
class CustomFeedConfig:
    widget_id: str
    enabled: bool
    name: str
    feed_url: str
    view_mode: FeedViewMode
    item_limit: int
    refresh_minutes: int
    show_images: bool
    show_subtitle: bool

    @classmethod
    def from_mapping(cls, widget_id: str, value: Mapping[str, object] | None) -> "CustomFeedConfig":
        if widget_id not in CUSTOM_FEED_WIDGET_IDS:
            raise ValueError(f"unknown custom feed slot: {widget_id!r}")
        defaults = require_canonical_default(f"widgets.{widget_id}")
        if not isinstance(defaults, Mapping):
            raise TypeError(f"canonical widgets.{widget_id} default must be a mapping")
        raw = value if isinstance(value, Mapping) else {}
        name = str(raw.get("name", defaults["name"]) or defaults["name"]).strip()[:80]
        # A feed or site address; a bare host such as ``example.com`` means HTTPS.
        feed_url = normalize_feed_address(raw.get("feed_url", defaults["feed_url"]) or "")[:8192]
        view = str(raw.get("view_mode", defaults["view_mode"]) or defaults["view_mode"]).strip().casefold()
        if view not in _VALID_VIEW_MODES:
            view = str(defaults["view_mode"]).casefold()
        try:
            item_limit = int(raw.get("item_limit", defaults["item_limit"]))
        except (TypeError, ValueError):
            item_limit = int(defaults["item_limit"])
        try:
            refresh_minutes = int(raw.get("refresh_minutes", defaults["refresh_minutes"]))
        except (TypeError, ValueError):
            refresh_minutes = int(defaults["refresh_minutes"])
        raw_enabled = raw.get("enabled", defaults["enabled"])
        default_enabled = bool(defaults["enabled"])
        if isinstance(raw_enabled, bool):
            enabled = raw_enabled
        elif isinstance(raw_enabled, str):
            normalized_enabled = raw_enabled.strip().casefold()
            if normalized_enabled in {"true", "1", "yes", "on"}:
                enabled = True
            elif normalized_enabled in {"false", "0", "no", "off"}:
                enabled = False
            else:
                enabled = default_enabled
        elif raw_enabled is None:
            enabled = default_enabled
        else:
            enabled = bool(raw_enabled)

        raw_show_images = raw.get("show_images", defaults["show_images"])
        default_show_images = bool(defaults["show_images"])
        if isinstance(raw_show_images, bool):
            show_images = raw_show_images
        elif isinstance(raw_show_images, str):
            normalized = raw_show_images.strip().casefold()
            if normalized in {"true", "1", "yes", "on"}:
                show_images = True
            elif normalized in {"false", "0", "no", "off"}:
                show_images = False
            else:
                show_images = default_show_images
        elif raw_show_images is None:
            show_images = default_show_images
        else:
            show_images = bool(raw_show_images)
        raw_show_subtitle = raw.get("show_subtitle", defaults["show_subtitle"])
        default_show_subtitle = bool(defaults["show_subtitle"])
        if isinstance(raw_show_subtitle, bool):
            show_subtitle = raw_show_subtitle
        elif isinstance(raw_show_subtitle, str):
            normalized_subtitle = raw_show_subtitle.strip().casefold()
            if normalized_subtitle in {"true", "1", "yes", "on"}:
                show_subtitle = True
            elif normalized_subtitle in {"false", "0", "no", "off"}:
                show_subtitle = False
            else:
                show_subtitle = default_show_subtitle
        elif raw_show_subtitle is None:
            show_subtitle = default_show_subtitle
        else:
            show_subtitle = bool(raw_show_subtitle)
        return cls(
            widget_id=widget_id,
            enabled=enabled,
            name=name or str(defaults["name"]),
            feed_url=feed_url,
            view_mode=view,  # type: ignore[arg-type]
            item_limit=max(3, min(40, item_limit)),
            refresh_minutes=max(5, min(24 * 60, refresh_minutes)),
            show_images=show_images,
            show_subtitle=show_subtitle,
        )

    @property
    def configured(self) -> bool:
        if not self.feed_url:
            return False
        try:
            validate_feed_url(self.feed_url)
        except ValueError:
            return False
        return True

    def source_spec(self) -> FeedSourceSpec:
        url = validate_feed_url(self.feed_url)
        fingerprint = endpoint_fingerprint(url)
        # Endpoint fingerprint is the CUSTOM acquisition identity. A slot changing
        # A -> B can never render A's cache, while two slots intentionally pointed
        # at the same endpoint share one durable snapshot/network cadence instead
        # of duplicating work. Presentation name/layout remain slot-owned.
        return FeedSourceSpec(
            source_id=f"custom:endpoint:{fingerprint}",
            url=url,
            cache_key=f"custom_endpoint_{fingerprint}",
            display_name=self.name,
            max_items=max(40, self.item_limit),
        )
