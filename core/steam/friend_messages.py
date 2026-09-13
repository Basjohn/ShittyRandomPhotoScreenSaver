"""Private Steam Friend Messages unread-state adapter.

Steam's FriendMessages service is intentionally treated as a conditional
capability rather than a requirement for Friend Pulse.  The roster remains
healthy when the user's normal Web API key is rejected by this undocumented
service.  Accepted responses are immediately reduced to opaque friend
fingerprints, unread counts and source timestamps; message bodies are never
persisted here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

from core.steam.backend import build_endpoint, fetch_json
from core.steam.credentials import SteamCredentialPayload, safe_fingerprint
from core.steam.models import SteamResultStatus, SteamSourceId


@dataclass(frozen=True)
class FriendMessageSession:
    """Presentation-safe unread state for one known roster friend."""

    identity_fingerprint: str
    unread_count: int
    last_message_at: int | None = None
    last_view_at: int | None = None


@dataclass(frozen=True)
class FriendMessageSnapshot:
    """One bounded unread-state observation from Steam."""

    status: SteamResultStatus
    accepted_at: float | None = None
    sessions: tuple[FriendMessageSession, ...] = ()
    source_available: bool = False

    @property
    def total_unread(self) -> int:
        return sum(max(0, int(session.unread_count)) for session in self.sessions)


def fetch_friend_message_sessions(
    *,
    credential: SteamCredentialPayload,
    friend_steam_ids: Mapping[str, str],
    opener: Any | None = None,
    now: float | None = None,
) -> FriendMessageSnapshot:
    """Fetch one historical unread-session snapshot with no extra cadence owner.

    The caller supplies the current private Friend Pulse fingerprint -> SteamID
    map.  Steam returns only 32-bit friend account ids, so matching is performed
    against the low 32 bits of already-authorized roster SteamIDs rather than
    manufacturing or exposing new identifiers.
    """

    endpoint = build_endpoint(
        SteamSourceId.FRIEND_MESSAGE_SESSIONS,
        api_key=credential.api_key,
        only_sessions_with_messages=1,
    )
    result = fetch_json(endpoint, opener=opener)
    reference_now = time.time() if now is None else float(now)
    if not result.ok:
        return FriendMessageSnapshot(
            status=result.status,
            accepted_at=result.fetched_at or reference_now,
            source_available=False,
        )
    return parse_friend_message_sessions(
        result.payload or {},
        friend_steam_ids=friend_steam_ids,
        accepted_at=result.fetched_at or reference_now,
    )


def parse_friend_message_sessions(
    payload: Mapping[str, Any],
    *,
    friend_steam_ids: Mapping[str, str],
    accepted_at: float | None = None,
) -> FriendMessageSnapshot:
    """Reduce a Steam response to known-friend opaque unread state."""

    body = payload.get("response", payload)
    if not isinstance(body, Mapping):
        return FriendMessageSnapshot(
            status=SteamResultStatus.INVALID_RESPONSE,
            accepted_at=accepted_at,
            source_available=False,
        )
    raw_sessions = body.get("message_sessions", ())
    if not isinstance(raw_sessions, (list, tuple)):
        return FriendMessageSnapshot(
            status=SteamResultStatus.INVALID_RESPONSE,
            accepted_at=accepted_at,
            source_available=False,
        )

    account_to_fingerprint: dict[int, str] = {}
    for fingerprint, steam_id in friend_steam_ids.items():
        try:
            account_id = int(str(steam_id)) & 0xFFFFFFFF
        except (TypeError, ValueError):
            continue
        if account_id > 0:
            account_to_fingerprint[account_id] = str(fingerprint)

    sessions: list[FriendMessageSession] = []
    for raw in raw_sessions:
        if not isinstance(raw, Mapping):
            continue
        account_id = _nonnegative_int(raw.get("accountid_friend"))
        unread = _nonnegative_int(raw.get("unread_message_count"))
        if account_id is None or unread is None or unread <= 0:
            continue
        fingerprint = account_to_fingerprint.get(account_id)
        if not fingerprint:
            continue
        # Re-derive the expected opaque fingerprint from the matched private ID
        # before admission.  This guards against a caller-supplied mismatched map.
        private_id = friend_steam_ids.get(fingerprint)
        if not private_id or safe_fingerprint(str(private_id)) != fingerprint:
            continue
        sessions.append(
            FriendMessageSession(
                identity_fingerprint=fingerprint,
                unread_count=unread,
                last_message_at=_nonnegative_int(raw.get("last_message")),
                last_view_at=_nonnegative_int(raw.get("last_view")),
            )
        )
    sessions.sort(
        key=lambda session: (
            -(session.last_message_at or 0),
            session.identity_fingerprint,
        )
    )
    return FriendMessageSnapshot(
        status=SteamResultStatus.SUCCESS,
        accepted_at=accepted_at,
        sessions=tuple(sessions),
        source_available=True,
    )


def _nonnegative_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None