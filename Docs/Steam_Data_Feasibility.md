# Steam Data Feasibility

Last updated: 2026-07-14

This document records the supported-source pass for the Steam widget family. Achievement Pulse and Abandonment Issues are normally visible, disabled-by-default cards; this document remains the source gate for Steam Journey and Friend Pulse.

## Rules

- Achievement Pulse, Abandonment Issues, and Steam Settings are visible without a development flag. `--devsteam` exposes only Steam Journey and Friend Pulse prototypes; `steam_progress` remains Steam Journey's compatibility key.
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
| Owned library | `IPlayerService/GetOwnedGames/v1` | Conditional; locally proven | app id, title/icon when appinfo is included, playtime forever, `rtime_last_played` when returned | Returns owned games only when owned-game details are visible to caller. Valve's method page does not promise the response field list, so runtime validation remains required | Library index and Abandonment candidate foundation; cannot fabricate missing apps or dates |
| Per-app achievements | `ISteamUserStats/GetPlayerAchievements/v1` + `GetSchemaForGame/v2` | Conditional | achievement list, unlock state/time, schema totals/names, achieved/unachieved icon URLs when supplied | Requires user key, profile id, app id; per-app availability and icon fields may vary | Achievement Pulse uses schema display names/icons; Abandonment may reuse an already-successful exact-path snapshot for count/latest-unlock shelves and ranking, but never requests one for display |
| Friends | `ISteamUser/GetFriendList/v1` + `GetPlayerSummaries/v2` | Conditional | relationship list, persona/avatar/current game summary | Private friends list returns unauthorized; unavailable must not become “everyone offline” | Friend Pulse can proceed only with privacy-aware empty states |
| App news | `ISteamNews/GetNewsForApp/v2` | Transport/schema proven; product use conditional | app id, stable item id, title/body, date, feed metadata, tags, URL | Public app-specific endpoint; not personalized and not library-wide | Steam Journey may use only bounded watched/focus-app scans after its classifier/noise gate |
| General per-game last played | `IPlayerService/GetOwnedGames/v1` `rtime_last_played` | Conditional; locally proven | Unix timestamp plus explicit verified/unknown provenance | A redacted controlled-account probe found the field on every returned owned row and a positive timestamp on every played row. Missing, zero, non-numeric, or future values remain unknown; account privacy/unavailability is not “never played” | Abandonment Issues may make smart age claims only for individually verified rows |
| Single-game playtime | `IPlayerService/GetSingleGamePlaytime/v1` | Unavailable | app playtime only for associated app key | Requires Web API key associated with that app | Not a general client feature |
| Publisher app ownership / authed news | publisher-only endpoints | Excluded | none | Requires publisher key and secure server, never direct clients | Must not be called or exposed as fallback |

## Card Gates

### Achievement Pulse

- Proceeds through the implemented cache-first path without `--devsteam` because synthetic fixtures cover recent games, owned games, achievement lists, schema names/totals, private/unavailable states, and empty achievement responses; the card remains disabled by default until the user enables it.
- Steam exposes per-app achievement records rather than an account-wide unlock activity feed. Dynamic selection therefore treats up to five recent-play rows as a bounded candidate set, ranks candidates with known positive unlock timestamps newest-first, and retains recent-play order as a stable fallback behind timestamped candidates when evidence is missing or zero.
- Custom selection persists by app id, not title text.
- `Most Recent`, `Recent #2` through `Recent #5`, Previous, and cached Settings labels consume the same achievement-recency order. A stale or forced refresh may fetch at most five candidate achievement records through existing cache/coalescing/backoff work, then fetch schema only for the selected app. The resolver retains that app's newest five unlocked achievements, ordered by unlock time and mapped through schema display names. Missing schema labels fall back to the achievement row without exposing internal ids when a user-facing name is available.
- The primary newest unlock may join to its schema `icon`. Only HTTPS URLs on the validated Steam asset allowlist may be fetched; missing, invalid, or failed icon data removes only the optional 40px flair and never the unlock text/card state.
- The shared Steam freshness window is a non-secret preference with a 5-minute minimum and 10-minute default. It gates bounded startup refresh work; it does not authorize a private polling loop.

### Friend Pulse

- May proceed after fixtures prove private friend list, empty friend list, current-game summaries, missing avatars, and partial player summaries.
- Default display must be currently playing / observed change oriented. Private/unavailable must not be shown as an offline roster.

### Abandonment Issues

- Proceeds through the implemented cache-first path without `--devsteam`; the card remains disabled by default until the user enables it.
- Smart candidates must be owned, have a displayable title, exceed the configured accidental-launch floor, have an individually verified `rtime_last_played`, exceed the configured minimum inactivity threshold, not appear in the bounded recent list, and not be in Never Show.
- Default ranking prefers games with 15-119 minutes of play and at least 26 weeks of verified inactivity. An already-existing local Achievement Pulse snapshot may further prefer two or fewer unlocked achievements or demote an all-unlocked snapshot, but this is ranking evidence only and never a claim that the game is finished.
- Achievement evidence is cache-only: runtime probes at most 12 exact cache paths on the IO worker, prioritizing current/pinned identity before the shortlist. It does not enumerate cache directories, request achievements, or sweep the library; unknown counts remain neutral.
- Missing, zero, malformed, or future timestamps are excluded rather than estimated. Pinned games with unknown provenance render an honest unavailable state instead of a fabricated age or substitute game.
- The default user ledger is `PLAYED`, `ACHIEVEMENTS`, `LAST UNLOCK`, exact UTC `LAST PLAYED`, and derived `ARCHIVE CLASS`. The date uses only the selected row's verified `rtime_last_played`; when that evidence is unavailable, no date shelf is drawn. Achievement count/latest unlock require a successful cached per-app snapshot, and a proven zero-unlock snapshot may say `NO UNLOCKS`; private, failed, or missing evidence removes those shelves. Archive class is engagement-depth copy only and makes no completion claim. Queue/source/selection diagnostics remain optional and default off.
- Ledger settings are presentation-only. The authored card grows by complete two-column rows for every enabled shelf instead of capping at four, shrinking existing content, or initiating provider/timer/paint work.
- Profile-private selection, exposure cooldowns, and rotation draw state are shared across displays. Smart rotation draws preference tiers with fixed tier weights and then a candidate within the selected tier, so library size cannot drown out the preferred old/short/low-unlock scope; every tier remains reachable and the current game is excluded when an alternative exists. `ARCHIVE N/M` reports the selected candidate's preference-rank position and is not a sequential cursor. Persisted selection age survives widget rebuilds, so the first rebuilt interval is only the remaining time and overdue state rotates immediately. A widget-level manual refresh forces one non-repeating cache-backed draw and restarts the configured cadence. Semantic rotation reads cache only and cannot request owned/recent/achievement data. A missing allowlisted public asset for the one selected app may hydrate on that existing IO job when automatic updates are allowed; `--noupdates` remains cache-only for artwork. Rotation defers rather than discards an expiry that collides with a parent transition.
- Guilt Desaturater is optional presentation only: it prepares bucketed local artwork off the UI thread and never changes eligibility or source meaning.

### Steam Journey

- The public app-news transport and stable item/date/url/feed fields are proven for a bounded app-specific request.
- Production remains blocked on the editorial classifier, candidate budget, history/dismissal policy, and noise/failure fixtures. It must not scan the whole library frequently by default or pretend public app news is personalized progress.

## Implementation Consequences

- `core/steam/backend.py` owns endpoint metadata, source status, redaction, source exclusion, and fixture-safe transport.
- `core/steam/models.py` owns frozen result/source/view data types.
- `core/steam/cache.py` owns versioned atomic cache envelopes. Failed/private/invalid responses must not freshen cache.
- Source refreshes are process-coordinated by opaque profile/cache identity. A successful response authoritatively freshens its source record even when byte-equivalent; immediate followers reuse that fresh record, while unchanged visible models avoid repaint/artwork churn.
- `core/steam/request_policy.py`, `profile_state.py`, `assets.py`, `events.py`, and `mock_backend.py` complete the Phase 2 non-UI foundation: coalescing, stale-generation drops, bounded backoff, account-private policy state, validated asset cache, narrow data-ready publication, and fixture-only backend injection.
- `core/steam/achievement_pulse.py`, `achievement_pulse_cache.py`, and the Steam card widget/components own the first real card path and current family baseline: cache resolution before first reveal, up-to-five recent candidate achievement probes followed by selected-schema-only refresh, positive-unlock-time selection order with stable missing-evidence fallback, immediate multi-display follower suppression after a successful source batch, up to five latest unlock labels, optional measured-text-adjacent primary schema-icon flair, achievement-recency Previous presentation, validated Wide header plus Square/default Portrait library artwork, widened fitted Unlocked geometry, collision-free whole-rail compositions, compact or default-on all-field double capsules with independent font-driven growth, alpha-capable capsule styling, and presentation-only GUI preferences that never become source authority.
- `core/steam/abandonment_issues.py`, `abandonment_cache.py`, `widgets/steam_abandonment_components.py`, and `widgets/abandonment_issues_widget.py` own the second production card: strict timestamp/latest-unlock provenance, short-start/age/cache-only-achievement ranking tiers, profile-shared policy-aware cooldown rotation with persisted remaining cadence and forced manual draws, worker-prepared optional desaturation, an evidence-gated adaptive archival ledger, and sparse manager-owned content crossfades.
- Tests must use injected fake openers and fixtures; no live Steam requests in the suite.

## Primary Source Links

- `IPlayerService`: https://partner.steamgames.com/doc/webapi/IPlayerService
- `ISteamUserStats`: https://partner.steamgames.com/doc/webapi/ISteamUserStats
- Steam Achievements: https://partner.steamgames.com/doc/features/achievements
- `ISteamUser`: https://partner.steamgames.com/doc/webapi/ISteamUser
- `ISteamNews`: https://partner.steamgames.com/doc/webapi/ISteamNews
- Steam Library Assets: https://partner.steamgames.com/doc/store/assets/libraryassets
