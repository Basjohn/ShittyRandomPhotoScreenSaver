"""Steam Web API endpoint metadata and safe fixture-friendly transport.

The Steam widget family is still dev-gated. This module may describe supported
sources and fetch through an injected opener, but tests must not perform live
network calls.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.logging.logger import get_logger
from core.steam.credentials import safe_fingerprint
from core.steam.models import (
    SteamResult,
    SteamResultStatus,
    SteamSourceEvidence,
    SteamSourceId,
    SteamSourceStatus,
)

logger = get_logger(__name__)

MAX_RESPONSE_BYTES = 1_500_000
DEFAULT_TIMEOUT_SECONDS = 12.0
STEAM_USER_AGENT = "SRPSS-Steam-DevGate/0.1"

_SECRET_PARAM_KEYS = frozenset({"key", "steamid", "steamids", "profile_identifier"})


@dataclass(frozen=True)
class SteamEndpoint:
    """Concrete endpoint call description with redaction/source metadata."""

    source_id: SteamSourceId
    url: str
    params: Mapping[str, Any]
    requires_user_key: bool
    publisher_only: bool = False
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def redacted_params(self) -> dict[str, Any]:
        return redact_params(self.params)

    def redacted_url(self) -> str:
        return build_url(self.url, self.redacted_params())


SOURCE_EVIDENCE: dict[SteamSourceId, SteamSourceEvidence] = {
    SteamSourceId.RECENTLY_PLAYED: SteamSourceEvidence(
        source_id=SteamSourceId.RECENTLY_PLAYED,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="IPlayerService/GetRecentlyPlayedGames/v1",
        requires_user_key=True,
        notes=("Recent-only game data; depends on profile visibility/API response.",),
    ),
    SteamSourceId.OWNED_GAMES: SteamSourceEvidence(
        source_id=SteamSourceId.OWNED_GAMES,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="IPlayerService/GetOwnedGames/v1",
        requires_user_key=True,
        notes=("Owned-game details are only returned when visible to the caller.",),
    ),
    SteamSourceId.PLAYER_ACHIEVEMENTS: SteamSourceEvidence(
        source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="ISteamUserStats/GetPlayerAchievements/v1",
        requires_user_key=True,
        notes=("Per-app achievement data; app/profile availability may vary.",),
    ),
    SteamSourceId.ACHIEVEMENT_SCHEMA: SteamSourceEvidence(
        source_id=SteamSourceId.ACHIEVEMENT_SCHEMA,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="ISteamUserStats/GetSchemaForGame/v2",
        requires_user_key=True,
        notes=("Per-app schema for achievement totals/names.",),
    ),
    SteamSourceId.FRIEND_LIST: SteamSourceEvidence(
        source_id=SteamSourceId.FRIEND_LIST,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="ISteamUser/GetFriendList/v1",
        requires_user_key=True,
        notes=("Private friend lists return unauthorized rather than offline data.",),
    ),
    SteamSourceId.PLAYER_SUMMARIES: SteamSourceEvidence(
        source_id=SteamSourceId.PLAYER_SUMMARIES,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="ISteamUser/GetPlayerSummaries/v2",
        requires_user_key=True,
        notes=("Useful for observable persona/avatar/current-game details.",),
    ),
    SteamSourceId.APP_NEWS: SteamSourceEvidence(
        source_id=SteamSourceId.APP_NEWS,
        status=SteamSourceStatus.CONDITIONAL,
        endpoint="ISteamNews/GetNewsForApp/v2",
        requires_user_key=False,
        public_without_key=True,
        notes=("Public app-specific news; not a personalized library-wide update feed.",),
    ),
    SteamSourceId.SINGLE_GAME_PLAYTIME: SteamSourceEvidence(
        source_id=SteamSourceId.SINGLE_GAME_PLAYTIME,
        status=SteamSourceStatus.UNAVAILABLE,
        endpoint="IPlayerService/GetSingleGamePlaytime/v1",
        requires_user_key=True,
        notes=("Requires a Web API key associated with the queried app; not general-user viable.",),
    ),
    SteamSourceId.NEWS_AUTHED: SteamSourceEvidence(
        source_id=SteamSourceId.NEWS_AUTHED,
        status=SteamSourceStatus.EXCLUDED,
        endpoint="ISteamNews/GetNewsForAppAuthed/v2",
        requires_user_key=False,
        publisher_only=True,
        notes=("Publisher-key endpoint; never client-side.",),
    ),
    SteamSourceId.CHECK_APP_OWNERSHIP: SteamSourceEvidence(
        source_id=SteamSourceId.CHECK_APP_OWNERSHIP,
        status=SteamSourceStatus.EXCLUDED,
        endpoint="ISteamUser/CheckAppOwnership/v4",
        requires_user_key=False,
        publisher_only=True,
        notes=("Publisher-key endpoint; never client-side.",),
    ),
    SteamSourceId.PUBLISHER_APP_OWNERSHIP: SteamSourceEvidence(
        source_id=SteamSourceId.PUBLISHER_APP_OWNERSHIP,
        status=SteamSourceStatus.EXCLUDED,
        endpoint="ISteamUser/GetPublisherAppOwnership/v3",
        requires_user_key=False,
        publisher_only=True,
        notes=("Publisher-key endpoint; never client-side.",),
    ),
}


def require_client_source(source_id: SteamSourceId) -> SteamSourceEvidence:
    """Return source metadata or raise if a client call would violate policy."""
    evidence = SOURCE_EVIDENCE[source_id]
    if evidence.publisher_only or evidence.status == SteamSourceStatus.EXCLUDED:
        raise ValueError(f"Steam source {source_id.value} is not allowed in client runtime")
    return evidence


def redact_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Return URL/log-safe params with user key and account ids removed."""
    redacted: dict[str, Any] = {}
    for key, value in params.items():
        lowered = str(key).lower()
        if lowered in _SECRET_PARAM_KEYS:
            redacted[str(key)] = _redact_value(value, lowered)
        else:
            redacted[str(key)] = value
    return redacted


def build_url(base_url: str, params: Mapping[str, Any]) -> str:
    query = urllib.parse.urlencode({str(k): v for k, v in params.items() if v is not None}, doseq=True)
    if not query:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query}"


def build_endpoint(source_id: SteamSourceId, *, api_key: str | None = None, steamid: str | None = None, **params: Any) -> SteamEndpoint:
    """Build a known Steam endpoint without performing IO."""
    evidence = require_client_source(source_id)
    endpoint_params: dict[str, Any] = dict(params)
    if evidence.requires_user_key:
        if not api_key:
            raise ValueError(f"Steam source {source_id.value} requires an API key")
        endpoint_params["key"] = api_key
    if source_id in {
        SteamSourceId.RECENTLY_PLAYED,
        SteamSourceId.OWNED_GAMES,
        SteamSourceId.PLAYER_ACHIEVEMENTS,
        SteamSourceId.FRIEND_LIST,
    }:
        if not steamid:
            raise ValueError(f"Steam source {source_id.value} requires a Steam profile id")
        endpoint_params["steamid"] = steamid
    elif source_id == SteamSourceId.PLAYER_SUMMARIES:
        if steamid and "steamids" not in endpoint_params:
            endpoint_params["steamids"] = steamid

    return SteamEndpoint(
        source_id=source_id,
        url=_source_url(source_id),
        params=endpoint_params,
        requires_user_key=evidence.requires_user_key,
        publisher_only=evidence.publisher_only,
    )


def classify_http_status(status: int) -> SteamResultStatus:
    if status == 401:
        return SteamResultStatus.PRIVATE
    if status == 403:
        return SteamResultStatus.UNAUTHORIZED
    if status == 404:
        return SteamResultStatus.NOT_FOUND
    if status == 429:
        return SteamResultStatus.RATE_LIMITED
    if 200 <= status < 300:
        return SteamResultStatus.SUCCESS
    return SteamResultStatus.NETWORK_ERROR


def fetch_json(
    endpoint: SteamEndpoint,
    *,
    opener: Callable[[urllib.request.Request, float], Any] | None = None,
) -> SteamResult:
    """Fetch JSON through an injectable opener and return a safe result."""
    if endpoint.publisher_only:
        logger.warning("[STEAM][FALLBACK] Refused publisher-only source=%s", endpoint.source_id.value)
        return SteamResult(
            status=SteamResultStatus.PUBLISHER_ONLY,
            source_id=endpoint.source_id,
            message="Publisher-only Steam endpoint is not allowed in client runtime.",
            attempted_sources=(endpoint.source_id,),
        )

    url = build_url(endpoint.url, endpoint.params)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": STEAM_USER_AGENT,
        },
    )
    safe_url = endpoint.redacted_url()
    logger.debug("[STEAM] Source request start source=%s url=%s", endpoint.source_id.value, safe_url)
    try:
        call = opener or _default_open
        response = call(request, endpoint.timeout_seconds)
        status = int(getattr(response, "status", getattr(response, "code", 200)))
        if classify_http_status(status) != SteamResultStatus.SUCCESS:
            return SteamResult(
                status=classify_http_status(status),
                source_id=endpoint.source_id,
                http_status=status,
                message=f"Steam source returned HTTP {status}",
                attempted_sources=(endpoint.source_id,),
            )
        data = response.read(endpoint.max_response_bytes + 1)
        if len(data) > endpoint.max_response_bytes:
            return SteamResult(
                status=SteamResultStatus.INVALID_RESPONSE,
                source_id=endpoint.source_id,
                message="Steam response exceeded the configured size limit.",
                attempted_sources=(endpoint.source_id,),
            )
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, Mapping):
            return SteamResult(
                status=SteamResultStatus.INVALID_RESPONSE,
                source_id=endpoint.source_id,
                message="Steam response was not a JSON object.",
                attempted_sources=(endpoint.source_id,),
            )
        return SteamResult(
            status=SteamResultStatus.SUCCESS,
            source_id=endpoint.source_id,
            payload=payload,
            http_status=status,
            attempted_sources=(endpoint.source_id,),
        )
    except urllib.error.HTTPError as exc:
        return SteamResult(
            status=classify_http_status(int(exc.code)),
            source_id=endpoint.source_id,
            http_status=int(exc.code),
            message=f"Steam source returned HTTP {exc.code}",
            attempted_sources=(endpoint.source_id,),
        )
    except Exception as exc:
        logger.warning("[STEAM] Source request failed source=%s url=%s error=%s", endpoint.source_id.value, safe_url, exc)
        return SteamResult(
            status=SteamResultStatus.NETWORK_ERROR,
            source_id=endpoint.source_id,
            message="Steam source request failed.",
            attempted_sources=(endpoint.source_id,),
        )


def validate_connection(
    *,
    api_key: str,
    steamid: str,
    opener: Callable[[urllib.request.Request, float], Any] | None = None,
) -> SteamResult:
    """Validate an explicitly user-submitted Steam key/identity pair.

    This deliberately performs one narrow, redacted player-summary request and
    does not write cache records or schedule card refresh work.  It is used by
    the Settings ``Save & Test`` action before DPAPI persistence.
    """
    endpoint = build_endpoint(
        SteamSourceId.PLAYER_SUMMARIES,
        api_key=api_key,
        steamid=steamid,
    )
    return fetch_json(endpoint, opener=opener)


def _default_open(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)


def _source_url(source_id: SteamSourceId) -> str:
    if source_id == SteamSourceId.APP_NEWS:
        return "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
    if source_id == SteamSourceId.RECENTLY_PLAYED:
        return "https://partner.steam-api.com/IPlayerService/GetRecentlyPlayedGames/v1/"
    if source_id == SteamSourceId.OWNED_GAMES:
        return "https://partner.steam-api.com/IPlayerService/GetOwnedGames/v1/"
    if source_id == SteamSourceId.PLAYER_ACHIEVEMENTS:
        return "https://partner.steam-api.com/ISteamUserStats/GetPlayerAchievements/v1/"
    if source_id == SteamSourceId.ACHIEVEMENT_SCHEMA:
        return "https://partner.steam-api.com/ISteamUserStats/GetSchemaForGame/v2/"
    if source_id == SteamSourceId.FRIEND_LIST:
        return "https://partner.steam-api.com/ISteamUser/GetFriendList/v1/"
    if source_id == SteamSourceId.PLAYER_SUMMARIES:
        return "https://partner.steam-api.com/ISteamUser/GetPlayerSummaries/v2/"
    raise ValueError(f"Unsupported Steam source: {source_id.value}")


def _redact_value(value: Any, key: str) -> str:
    if value is None or value == "":
        return f"<{key}:empty>"
    return f"<{key}:{safe_fingerprint(str(value))}>"
