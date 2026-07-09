# Steam Data Feasibility

Last updated: 2026-07-09

This document records the first supported-source pass for the dev-gated Steam widget family. It is not a product changelog; it is the source gate that decides which card concepts may proceed to fixture-backed implementation.

## Rules

- Steam remains hidden unless `--devsteam` is present.
- User Steam API keys/profile identifiers are credentials, not settings.
- Publisher-key endpoints are excluded from client runtime, even if they would solve a product problem.
- Unknown/private/unavailable data is a first-class state. Do not infer dates, ownership, friends, or progress from absence.
- No authenticated Store scraping, cookies, browser automation, Steam Guard handling, or Steam password handling.
- Public app-news is allowed as app-specific source material, not as a personalized whole-library feed.

## Authentication Model

- `Connect ID` uses Steam OpenID as the browser identity-linking step. It establishes the user's SteamID64, but it does not by itself grant access to player-data endpoints.
- `Connect API KEY` opens Steam's Web API key form and captures the user's key through an explicit user-clicked paste action. Steam's form is website-shaped and may ask for a domain label; `localhost` is the intended SRPSS guidance for a local desktop app unless fresh validation proves Steam rejects it.
- The player-data sources in this document require both a user Web API key and linked SteamID64 before runtime account data is considered available.
- OAuth exists in Steamworks for some partner-site and partner-application flows, but it is not the baseline contract for the current Steam widget family unless Valve documents the exact needed scope for a later endpoint.
- Publisher Web API keys remain excluded from client runtime.

## Source Matrix

| Capability | Source | Status | Usable fields | Privacy / failure behavior | Card impact |
|---|---|---|---|---|---|
| Recently played games | `IPlayerService/GetRecentlyPlayedGames/v1` | Conditional | app id, recent playtime, ordered recent app list | Requires user key and profile id; response depends on account visibility and Steam behavior | Achievement Pulse may use this for dynamic recent selection after fixture/live validation |
| Owned library | `IPlayerService/GetOwnedGames/v1` | Conditional | app id, title/icon when appinfo is included, playtime forever | Returns owned games only when owned-game details are visible to caller | Library index foundation; cannot fabricate missing apps |
| Per-app achievements | `ISteamUserStats/GetPlayerAchievements/v1` + `GetSchemaForGame/v2` | Conditional | achievement list, unlock state, schema totals/names | Requires user key, profile id, app id; per-app availability may vary | Achievement Pulse uses schema display names instead of internal ids and can proceed with unavailable/private branches |
| Friends | `ISteamUser/GetFriendList/v1` + `GetPlayerSummaries/v2` | Conditional | relationship list, persona/avatar/current game summary | Private friends list returns unauthorized; unavailable must not become “everyone offline” | Friend Pulse can proceed only with privacy-aware empty states |
| App news | `ISteamNews/GetNewsForApp/v2` | Conditional | app id, headline/blurb/date/feed/url | Public app-specific endpoint; not personalized and not library-wide | Steam Progress may use only bounded watched/focus-app scans |
| General per-game last played | None proven | Unavailable | none | `GetRecentlyPlayedGames` is recent-only; `GetOwnedGames` does not prove a general reliable timestamp in this pass | Abandonment Issues remains blocked from smart last-played claims |
| Single-game playtime | `IPlayerService/GetSingleGamePlaytime/v1` | Unavailable | app playtime only for associated app key | Requires Web API key associated with that app | Not a general client feature |
| Publisher app ownership / authed news | publisher-only endpoints | Excluded | none | Requires publisher key and secure server, never direct clients | Must not be called or exposed as fallback |

## Card Gates

### Achievement Pulse

- May proceed through the implemented cache-first path because synthetic fixtures cover recent games, owned games, achievement lists, schema names/totals, private/unavailable states, and empty achievement responses; live-account validation remains required before promotion.
- Dynamic recent-game selection must stay honest when a recent app lacks achievements.
- Custom selection persists by app id, not title text.
- The resolver may retain the newest three unlocked achievements, ordered by unlock time and mapped through schema display names. Missing schema labels fall back to the achievement row without exposing internal ids when a user-facing name is available.
- The shared Steam freshness window is a non-secret preference with a 5-minute minimum and 10-minute default. It gates bounded startup refresh work; it does not authorize a private polling loop.

### Friend Pulse

- May proceed after fixtures prove private friend list, empty friend list, current-game summaries, missing avatars, and partial player summaries.
- Default display must be currently playing / observed change oriented. Private/unavailable must not be shown as an offline roster.

### Abandonment Issues

- Blocked for smart last-played behavior until a reliable general last-played source is proven.
- A future cache-observation mode could show “not observed recently” only if the copy clearly avoids claiming Steam last-played dates.

### Steam Progress

- Partially viable only as a bounded app-news/focus-app pulse.
- It must not scan the whole library frequently by default and must not pretend public app news is personalized progress.

## Implementation Consequences

- `core/steam/backend.py` owns endpoint metadata, source status, redaction, source exclusion, and fixture-safe transport.
- `core/steam/models.py` owns frozen result/source/view data types.
- `core/steam/cache.py` owns versioned atomic cache envelopes. Failed/private/invalid responses must not freshen cache.
- `core/steam/request_policy.py`, `profile_state.py`, `assets.py`, `events.py`, and `mock_backend.py` complete the Phase 2 non-UI foundation: coalescing, stale-generation drops, bounded backoff, account-private policy state, validated asset cache, narrow data-ready publication, and fixture-only backend injection.
- `core/steam/achievement_pulse.py`, `achievement_pulse_cache.py`, and the Steam card widget/components own the first real card path: cache resolution before first reveal, refresh only after fade, up to three latest unlock labels, validated local artwork, and presentation-only GUI preferences that never become source authority.
- Tests must use injected fake openers and fixtures; no live Steam requests in the suite.

## Primary Source Links

- `IPlayerService`: https://partner.steamgames.com/doc/webapi/IPlayerService
- `ISteamUserStats`: https://partner.steamgames.com/doc/webapi/ISteamUserStats
- `ISteamUser`: https://partner.steamgames.com/doc/webapi/ISteamUser
- `ISteamNews`: https://partner.steamgames.com/doc/webapi/ISteamNews
