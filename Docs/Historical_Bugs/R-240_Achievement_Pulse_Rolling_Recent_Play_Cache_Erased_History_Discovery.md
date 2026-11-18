# R-240: Achievement Pulse lost historical unlock discovery when Steam's recent-play window rolled over

**18 November 2026. Historical cache display operator-verified; live unlock refresh and playtime recovery not yet verified. Status: AWAITING VALIDATION.**

## Observed failure

Achievement Pulse stopped showing the formerly cached unlock history and did not identify newer unlocks. The user explicitly did **not** clear the Steam cache. Two different hypotheses were considered: a regression in SRPSS versus Valve's October/November 2026 rollout of Steam Achievement Sets.

The provided `screensaver_steam.log` records successful local writes to `achievement_pulse_recent_games` immediately after `GetRecentlyPlayedGames` requests at 15:08:02/03 and 15:08:37 on 18 November. It contains **no** `GetPlayerAchievements` or `GetSchemaForGame` request in that capture. The log does not include the API response bodies or the account's private Steam cache directory, so the live responses cannot be proven empty from the uploaded evidence alone. The source can, however, reproduce exactly this request pattern with a successful empty recent-games response.

## Root cause in the checked source

1. `core/steam/cache.py` correctly wrote any successful JSON response as the latest `achievement_pulse_recent_games` record. Steam's `GetRecentlyPlayedGames` is a rolling *play activity* discovery source, not persistent achievement history. A successful response with no games therefore replaced the only cached list of candidate app IDs without deleting any per-app achievement snapshots.
2. `core/steam/achievement_pulse_cache.py` and the pure resolver read per-app records **only for IDs still in that rolling five-game list**. Once an app rolled off, its previously cached achievement JSON remained on disk but could no longer be selected. An empty list yielded no per-app requests and an unavailable card, despite potentially intact historical caches.
3. The transport considered any HTTP 200 JSON mapping successful. A per-app response with `playerstats.success == false` or no `achievements` list could overwrite an earlier usable snapshot; likewise, a malformed successful recent-game envelope could displace the last valid recent-play record.

The Steam Achievement Sets rollout is **not established as the cause**. The public Steamworks Web API documentation still lists `GetRecentlyPlayedGames/v1`, `GetPlayerAchievements/v1`, and `GetSchemaForGame/v2`. This repair does not attempt to reinterpret set totals or group IDs because no changed live achievement payload is in the evidence. References: https://partner.steamgames.com/doc/webapi/IPlayerService and https://partner.steamgames.com/doc/webapi/ISteamUserStats.

## Repair prepared

- Added `core/steam/achievement_pulse_history.py`, a local, account-private, versioned index named `achievement_pulse_history.json`. It retains app IDs, known names/playtime, latest positive unlock timestamps, and last observed order without storing credentials.
- Index-free legacy recovery scans **already-existing per-app achievement cache files**, with no provider calls, then reconstructs the newest known unlock order. Once indexed, subsequent cache loads inspect directory metadata and re-read only app files newer than the index, so updates from another Steam card are not hidden.
- The live recent-games cache remains accurate and may legitimately be empty. The presentation projects **live recent candidates plus cached history**, instead of substituting old history into Steam's live response. `Most Recent`, `Recent #2` through `#5`, Previous, and Settings labels share the projected unlock order.
- The usual refresh still requests at most five **live recent** candidate achievement records. If Steam gives zero recent candidates, it may refresh at most five already-cached historical candidates, then the selected game's schema. No account-wide library sweep, automatic polling loop, timer or request for arbitrary uncached historical games is introduced.
- The local index is atomically written via existing Steam cache persistence and per-profile source locks. A semantically failed HTTP-200 recent-play or per-app achievement response does not replace a last-good record. Safe count/status-only diagnostics expose whether the historical fallback was used.
- No user cache is deleted, migrated destructively, or forcibly reset. No change to the Steam API key/SteamID storage, settings, skin/UI pipeline, or other Steam widget scheduling.

## Checks and validation boundary

**48 fixture-only tests passed** in the available environment: the 19 existing Achievement Pulse tests, existing Steam cache/backend/request-policy tests, and six new historical-recovery regressions. The new cases cover historical discovery after an empty recent-response overwrote the former roster; a bounded empty-recent refresh and index persistence; a newly unlocked game's priority without losing archived candidates; semantic HTTP-200 achievement failure preserving prior data; detection of per-app updates performed by another Steam consumer; and malformed HTTP-200 recent-game envelopes preserving the previous valid recent discovery record. Compilation and imports of the changed pure-Python modules passed.

**Awaiting validation on the user's Windows runtime and actual Steam profile cache.** The uploaded archives contain working-tree files and logs, not the account's private cached achievement JSON or live Web API response bodies. The specific presence/health of old cached per-app records and the actual source payload at failure time are unverified. A future Steam response with zero games still cannot disclose *previously unknown* game IDs: no compliant account-wide achievement activity endpoint exists in these sources. Validation requires loading the repaired runtime without clearing Steam cache, confirming the old cached card/Settings history appears, then earning or refreshing an unlock and checking `screensaver_steam.log` for the count-only `ACHIEVEMENT_PULSE` source-selection line and per-app calls. If no per-app files remain, history cannot be reconstructed from a nonexistent local record.

**Disposition: AWAITING VALIDATION. Do not mark resolved/accepted until checked in the user's normal runtime.**

## Follow-up on 18 November: historical recovery did not restore playtime

The operator confirmed that the R-240 repair restores the cached achievement history, but reported that **Playtime** remains **Unavailable**. Live unlock refresh behaviour has not yet been validated. This is a separate manifestation of the same rolling-source loss: legacy per-app achievement JSON has unlock rows but no `playtime_forever`, while the former recent-play cache holding that field may already have been replaced by Steam's empty rolling response. R-240's rebuilt history index can recover unlocks and titles but cannot manufacture lost playtime.

### Scoped repair

- The pure resolver resolves playtime for the **selected app ID**, preferring the raw recently-played response, then the existing shared `achievement_pulse_owned_games` record, then the durable historical candidate. It does not mistakenly treat a historical projection as a fresh recent response. Custom app selection also uses any existing historical playtime.
- Cache-only projection reconciles known historical achievement apps with cached owned-library playtime without promoting every owned game into achievement discovery. Once refreshed, the history index persists the maximum known lifetime minutes, keeping a valid last-known value when Steam later omits `playtime_forever` or the owned-games cache is missing. No old cache entries are purged or rewritten destructively.
- **Only when the selected game has no playtime** may Achievement Pulse request `IPlayerService/GetOwnedGames/v1` via its existing bounded Steam fetch boundary, with `include_appinfo=True` and `include_played_free_games=True`. This shares Abandonment Issues' existing cache key and source lock. A successful owned-games record is reused for **24 hours**, even after a forced refresh or a successful empty/private-looking response; no additional timer or per-game sweep is introduced. The existing request backoff applies to failures.
- The owned-game source is a conditional Steam API, dependent on game-details privacy and Steam response availability. If the field is absent from recent play, owned games, **and** retained history, its actual value remains unknowable from achievement data alone. In that case the card correctly stays unavailable rather than guessing zero.

### Validation state

**55 cache/transport/selection fixture-only tests passed** in the Qt-free test environment (the original focused tests plus seven playtime regression cases). Tested recovery from pre-index caches, source precedence, durable retention after library loss, single owned refresh over repeated forced refreshes, a fresh-achievement-cache/absent-playtime case, omitted/private owned-game data, and custom selections. The two pre-existing coalescing tests were made realistic by supplying `playtime_forever` in their synthetic recent-game payloads; their request-count invariants still pass. All modified source modules compile.

**Disposition remains AWAITING VALIDATION:** the user has validated restored cached achievements, but not the new owned-games playtime fallback or a new live unlock in the Windows runtime. No unrelated plans, reference specifications, or operational documentation were edited.
