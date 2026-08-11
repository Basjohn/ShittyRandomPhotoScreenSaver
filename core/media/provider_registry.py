"""Canonical identities for media providers exposed through Windows GSMTC.

Provider ids are persisted settings values.  Session matching deliberately uses
explicit source-app identities only: browser GSMTC sessions identify the
browser host, not the web site that supplied the media.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class MediaProviderDescriptor:
    """Stable provider metadata used by media discovery and presentation."""

    provider_id: str
    display_name: str
    header_name: str
    description: str
    source_app_user_model_ids: frozenset[str]
    process_exe_names: frozenset[str]
    supports_app_volume: bool


_BROWSER_HOST_IDS = frozenset(
    {
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
        "vivaldi.exe",
    }
)
_BROWSER_GSMTC_SOURCE_IDS = frozenset(
    {*_BROWSER_HOST_IDS, *(name.removesuffix(".exe") for name in _BROWSER_HOST_IDS)}
)


MEDIA_PROVIDER_REGISTRY: dict[str, MediaProviderDescriptor] = {
    "spotify": MediaProviderDescriptor(
        provider_id="spotify",
        display_name="Spotify",
        header_name="SPOTIFY",
        description="Spotify desktop app via Windows GSMTC.",
        source_app_user_model_ids=frozenset(
            {
                "spotify.exe",
                "spotify",
                "spotifyab.spotifymusic_zpdnekdrzrea0!spotify",
            }
        ),
        process_exe_names=frozenset({"spotify.exe"}),
        supports_app_volume=True,
    ),
    "spotify_browser": MediaProviderDescriptor(
        provider_id="spotify_browser",
        display_name="Spotify Browser (GSMTC)",
        header_name="SPOTIFY BROWSER",
        description=(
            "Uses the active GSMTC session from a supported browser. Windows "
            "identifies the browser host, not the website or tab."
        ),
        source_app_user_model_ids=_BROWSER_GSMTC_SOURCE_IDS,
        process_exe_names=_BROWSER_HOST_IDS,
        # Core Audio can only address the browser process, not a Spotify tab.
        supports_app_volume=False,
    ),
    "musicbee": MediaProviderDescriptor(
        provider_id="musicbee",
        display_name="MusicBee",
        header_name="MUSICBEE",
        description="MusicBee via its Windows GSMTC plugin.",
        source_app_user_model_ids=frozenset({"musicbee.exe", "musicbee"}),
        process_exe_names=frozenset({"musicbee.exe"}),
        supports_app_volume=True,
    ),
}


def normalize_provider_id(value: object) -> Optional[str]:
    """Return a registered provider id, or ``None`` for an unknown value.

    Unknown persisted values must remain visible to their caller rather than
    silently selecting desktop Spotify.
    """

    if not isinstance(value, str):
        return None
    provider_id = value.strip().casefold()
    return provider_id if provider_id in MEDIA_PROVIDER_REGISTRY else None


def preserve_provider_setting(value: object, *, default: str = "spotify") -> str:
    """Return a canonical registered id or preserve an unsupported setting.

    Missing/blank values use the canonical default.  A non-empty unknown value
    is kept visible and therefore remains inert at runtime instead of silently
    selecting and later persisting a different provider.
    """

    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return normalize_provider_id(text) or text


def get_media_provider(value: object) -> Optional[MediaProviderDescriptor]:
    """Return the registered descriptor for *value*, if any."""

    provider_id = normalize_provider_id(value)
    return MEDIA_PROVIDER_REGISTRY.get(provider_id) if provider_id is not None else None


def get_media_provider_display_name(value: object) -> Optional[str]:
    """Return the registered user-facing provider label, if any."""

    provider = get_media_provider(value)
    return provider.display_name if provider is not None else None


def get_media_provider_header_name(value: object) -> Optional[str]:
    """Return the concise provider name painted in the media card header."""

    provider = get_media_provider(value)
    return provider.header_name if provider is not None else None


def _source_id_basename(source_app_user_model_id: str) -> str:
    """Return a Windows-path basename without applying fuzzy matching."""

    return source_app_user_model_id.replace("/", "\\").rsplit("\\", 1)[-1].casefold()


def provider_matches_source_app_user_model_id(
    provider: object,
    source_app_user_model_id: object,
) -> bool:
    """Return whether an explicit GSMTC identity belongs to *provider*.

    Full identifiers and path basenames are compared for exact equality.  In
    particular, this never treats a browser source id as Spotify merely
    because the tab happens to be playing spotify.com.
    """

    descriptor = get_media_provider(provider)
    if descriptor is None or not isinstance(source_app_user_model_id, str):
        return False
    source_id = source_app_user_model_id.strip().casefold()
    if not source_id:
        return False
    return (
        source_id in descriptor.source_app_user_model_ids
        or _source_id_basename(source_id) in descriptor.source_app_user_model_ids
    )


def get_provider_process_exe_names(provider: object) -> tuple[str, ...]:
    """Return deterministic process identities used for idle-poll detection."""

    descriptor = get_media_provider(provider)
    if descriptor is None:
        return ()
    return tuple(sorted(descriptor.process_exe_names))


def get_provider_process_exe_name_for_source(
    provider: object,
    source_app_user_model_id: object,
) -> Optional[str]:
    """Resolve one exact GSMTC source identity to its registered process.

    This is intentionally narrower than :func:`get_provider_process_exe_names`:
    callers must never turn an unknown Browser GSMTC identity into a scan of
    every supported browser audio session.
    """

    if not provider_matches_source_app_user_model_id(provider, source_app_user_model_id):
        return None
    if not isinstance(source_app_user_model_id, str):
        return None

    source_id = source_app_user_model_id.strip().casefold()
    basename = _source_id_basename(source_id)
    for process_name in get_provider_process_exe_names(provider):
        process_id = process_name.casefold()
        process_stem = process_id.removesuffix(".exe")
        if source_id in (process_id, process_stem) or basename in (
            process_id,
            process_stem,
        ):
            return process_name
    return None


def provider_supports_app_volume(provider: object) -> bool:
    """Return whether a provider has a session-specific Core Audio contract."""

    descriptor = get_media_provider(provider)
    return bool(descriptor is not None and descriptor.supports_app_volume)


def get_provider_failover_candidates(provider: object) -> tuple[str, ...]:
    """Return the other registered provider ids in stable registry order."""

    normalized = normalize_provider_id(provider)
    if normalized is None:
        return ()
    return tuple(
        provider_id
        for provider_id in MEDIA_PROVIDER_REGISTRY
        if provider_id != normalized
    )


def iter_media_providers() -> Iterable[MediaProviderDescriptor]:
    """Yield provider descriptors in stable UI/failover order."""

    return tuple(MEDIA_PROVIDER_REGISTRY.values())
