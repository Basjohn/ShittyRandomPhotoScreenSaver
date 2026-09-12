# Steam Friend Pulse — Current-Architecture Product Decomposition

Status: **IMPLEMENTED / DEV-GATED / AWAITING LIVE + INSTALLED ACCEPTANCE**
Last updated: 2026-09-13
Current sequencing authority: `Current_Plan.md`  
Stable widget id: `friend_pulse`

## 0. Purpose

Friend Pulse should answer one useful question at a glance:

> **What are my Steam friends actually playing now, and what meaningfully changed since the last accepted Steam observation?**

The pre-Quick mock card is not a fidelity target. The old scaffold survives only as evidence that the stable id,
Settings shell and family slot already exist. Product behavior is designed against the current Steam source/request
policy and retained Quick widget architecture.

This implementation must not become a Steam social client, chat client, activity-history database or a second Steam
provider. It is a small, privacy-aware activity card fed by the same bounded Steam ownership used by the existing
family.

### 0.1 Landed implementation state

F0-F6 are implemented. The retained card defaults to a dynamically centred two-column **Avatar Grid** at the canonical
capacity of four, expands to three columns for capacities five/six at canonical width, and keeps two readable columns
at narrow widths. A selectable compact **Activity Rows** view consumes the same stable row model and accepted snapshot.
Tiles/rows show privacy-permitted identity, normalized persona presence and the current game; Strict mode groups by
game and exposes neither names nor avatars.

The source/cache/runtime path is cache-first, uses existing Steam locks/request coordination/backoff/redaction, and has
one Friend Pulse owner per runtime generation shared by every display. Rich avatar hydration runs only for ranked
visible rows and delivers local `file:` sources. Zero admitted consumers means no source refresh, avatar work or live
cadence; retirement fences source and avatar completion and discards bounded comparison state.

Validated Steam IDs are permitted in the user's account-private Friend Pulse cache and the shared runtime owner. The
owner maps them to opaque fingerprints, strips them before delivering presentation snapshots, and QML emits only a row
index. In interactive MC/diagnostic runs an admitted friend avatar or NEW-marker click attempts a directed Steam chat
and falls back to the public profile when the protocol is rejected; normal screensaver runs use the HTTPS profile via
the existing secure URL helper and then exit normally. Game actions use the same seam to open the Steam Store: game
labels in Friend Pulse, plus existing Achievement Pulse and Abandonment Issues artwork, are actionable. No Steam
message body or individual message notification is sourced or rendered.

Focused automated source/runtime/privacy/cache/request/Settings/QML/binder/cardinality/normalization checks and real
Quick standard/busy/40%-floor captures are GREEN. F7 remains open only for a real connected-account readability/privacy
pass and installed two-display/DPI/theme/CUSTOM/retirement soak. The `--devsteam` gate remains until those cells close.

## 1. Current foundation to reuse

Current source already provides useful pieces that must remain the authority:

- `core/settings/widget_family_catalog.py` already registers `friend_pulse` inside the Steam family;
- canonical defaults already contain `widgets.friend_pulse` and the Steam family connection settings;
- `ui/tabs/widgets_tab_steam.py` already knows the stable card id and keeps unfinished cards behind the Steam dev gate;
- `rendering/widget_descriptors.py` already exposes the stable Settings member identity;
- `core/steam/backend.py` already declares `FRIEND_LIST` and `PLAYER_SUMMARIES` as conditional client-safe sources;
- `core/steam/request_policy.py`, Steam cache/credential/redaction infrastructure and shared request ownership already
  define rate/backoff/secret behavior;
- the existing Steam family `privacy_mode` (`Strict` / `Balanced` / `Rich`) is canonical persisted state and should
  become real Friend Pulse presentation policy rather than gaining a second card-local privacy switch;
- `Docs/Guides/10_WIDGET_GUIDELINES.md` owns ordinary retained-card normalization, styling, global-CUSTOM behavior,
  stacking, lifecycle, retirement and dormancy expectations.

Do not add parallel credentials, a second API key path, browser-cookie scraping, authenticated Store scraping, a
card-local network timer, private Steam session handling or a second settings/default authority.

## 2. Rollback / comparison boundary

Before implementation:

1. pin the exact pre-feature GODZIP/HEAD;
2. preserve current Steam backend/request/cache tests and the stable `friend_pulse` settings/default payload;
3. capture accepted Achievement Pulse + Abandonment Issues Steam-family source/lifecycle tests so new shared work cannot
   regress them;
4. preserve the dev-gated scaffold only as a stable-id/settings migration input, not as presentation goldens.

The feature is removable until accepted: its new substantive provider/preparation/runtime/QML files should have a
bounded deletion boundary.

## 3. Product contract

### 3.1 Primary information

The card prioritizes **currently-playing friends**. Each accepted playing entry needs only source-backed information:

- display identity when privacy policy allows it;
- current game name / app id when Steam reports it;
- optional avatar only in Rich mode and only for rows that survive visible ranking;
- a small change cue when the accepted observation proves that friend newly entered or changed a game since the
  immediately preceding accepted observation.

Do not claim joinability, shared ownership, party availability, session start time, recent session duration or other
facts unless a current allowed Steam source explicitly supplies them. The historical mock phrase “playing a game you
own” is not a product requirement.

### 3.2 Useful summary

The compact card should provide:

- header: **FRIEND PULSE** using the current shared Steam/branded-header vocabulary;
- primary metric: number of friends currently playing, when source state is authoritative;
- bounded visible rows ranked for usefulness;
- secondary aggregate such as additional-playing count when more rows exist than configured capacity;
- a subtle “changed” marker only for transitions proven from two accepted snapshots.

Online-but-not-playing friends may contribute to a small secondary count if source evidence is reliable, but they do
not displace currently-playing rows. Offline friend enumeration is not the point of the card.

### 3.3 Stable visible capacity

The initial product capacity is **four**. It is configuration-owned rather than a height that expands/contracts with
every refresh.

Configured capacity owns preferred geometry. Momentary source count never owns card height. Overflow is summarized
rather than causing layout churn.

### 3.4 Empty / private / stale / failure states

These states are semantically distinct:

- authoritative success + nobody playing -> honest **No friends playing** / equivalent quiet state;
- private friend list -> **Private / unavailable**, never “0 friends”;
- missing credentials/profile -> existing Steam connection/setup semantics;
- rate-limited/network failure with usable cache -> cached state visibly marked stale using the Steam family’s existing
  connection/staleness vocabulary;
- failure with no accepted cache -> explicit unavailable/error state;
- source response missing a friend/game field -> omit/unknown, never fabricate.

A stale accepted snapshot may remain visually useful, but stale data may not generate a new “just changed” cue.

## 4. Privacy contract

The existing Steam family `privacy_mode` is the only privacy-mode authority.

### Strict

- no friend persona names in the card;
- no avatars;
- no individual friend profile/chat action; game-group rows may open their public Steam Store page;
- aggregate by current game where useful, e.g. “2 friends playing <game>”;
- Steam IDs never enter presentation or normal logs.

### Balanced

- friend display names may be shown;
- no avatars;
- game activity may be shown;
- the NEW marker may request the same admitted friend chat/profile action without exposing an identifier to QML;
- the game label may request the public/app-client Store action.

### Rich

- display names + current game;
- avatars may be shown for visible ranked rows only;
- a visible avatar or NEW marker may request the admitted friend chat/profile action;
- all actions use source-provided validated identity and the existing semantic action-routing seam.

Changing privacy mode must reproject already accepted neutral state where possible. It must not force an unnecessary
network refresh merely to change pixels.

### 4.1 Semantic action boundary

- the account-private normalized cache may retain validated numeric Steam IDs; API keys remain credential-store only;
- the shared runtime owner holds the current fingerprint-to-ID map and clears it on last lease/retirement/failure;
- presentation snapshots and rows contain no Steam ID or URL, and QML emits only semantic signals plus a row index;
- the Python model revalidates the current visible row and owner map before forwarding an action;
- interactive MC/diagnostic runs try `steam://friends/message/<id>` or `steam://store/<appid>` and use the HTTPS
  profile/Store route when Qt rejects the protocol;
- normal screensaver runs send only the HTTPS profile/Store route through the existing secure helper and request the
  ordinary saver exit exactly once after successful handoff; if the helper cannot accept it, the action fails closed
  without a direct secure-desktop browser attempt or saver exit;
- a NEW marker means a newly observed game transition, not a Steam message notification. The current allowed Steam
  sources cannot deep-link to a particular chat message.

## 5. Source / request architecture

### 5.1 Allowed sources

Use the existing allowed Steam source metadata:

```text
FRIEND_LIST
    -> bounded friend ids
PLAYER_SUMMARIES
    -> observable persona/avatar/current-game fields
```

No additional source is added merely to decorate the card.

### 5.2 Shared refresh ownership

Friend Pulse owns one generation-scoped semantic source cadence, not one cadence per card/display. Its interval comes
only from canonical `steam.refresh_minutes`; there is no Friend Pulse-local interval or second provider. Endpoint work
continues to use the existing Steam request coordinator/backoff and source locks shared with the family.

Required behavior:

- cache-first preparation;
- one accepted Friend Pulse refresh generation feeds every Friend Pulse presentation consumer;
- multi-display instances never multiply the FriendList request or summary batches;
- request batching/chunking follows the endpoint/provider’s bounded policy rather than one request per friend;
- existing rate-limit/backoff/timeout/redaction contracts remain authoritative;
- no QML `Timer`, per-card timer, polling thread or presentation-owned HTTP.

### 5.3 Accepted neutral state

Introduce a small immutable presentation-neutral source state, conceptually:

```text
FriendPulseSnapshot
    revision / accepted_at
    source_status / stale/cache metadata
    authoritative friend count if known
    playing entries[]
        internal stable identity (not logged/presented raw)
        display name if source supplies it
        app id / game label if supplied
        avatar reference if supplied
        persona/playing state needed for projection
    change evidence derived only from previous accepted snapshot
```

The exact types belong in a Friend Pulse-owned source/preparation module unless an existing neutral Steam model is a
literal semantic match. Do not inflate shared Steam models for speculative reuse.

### 5.4 Change detection

Change emphasis is derived only between coherent accepted snapshots. It is presentation/product state, not a second
poller.

- newly observed playing -> eligible subtle change marker;
- game A -> game B -> eligible subtle change marker;
- stale/error/private transition -> does not fabricate a game change;
- first accepted snapshot -> no “just started” claims;
- history is bounded to the minimum previous accepted identity/game mapping needed for the next comparison.

Do not build a persistent social-activity history database.

## 6. Avatar / asset policy

Avatar work is optional enrichment, never admission-critical.

- only Rich mode may request/render avatars;
- rank visible rows first, then hydrate only those rows;
- use bounded cache/request ownership and the existing async image/resource path where it actually fits;
- no avatar prefetch for every friend;
- a failed avatar does not reject the row;
- avatar completion must be generation/revision fenced so stale rows cannot mutate a newer list.

If this creates a second independent image-downloader architecture, stop and reuse/extract the smallest current asset
seam instead.

## 7. Runtime / dormancy contract

Friend Pulse is admitted only when **all** applicable gates are true:

```text
widgets.family_activation.steam
AND widgets.steam.enabled
AND widgets.friend_pulse.enabled
AND temporary dev/member gate while experimental
AND at least one admitted Friend Pulse presentation consumer
```

The dev/member gate is temporary implementation isolation, not permanent product state.

When the effective consumer count becomes zero:

- no Friend Pulse-triggered refresh work;
- no avatar hydration;
- no Friend Pulse worker/cadence;
- no hidden source subscription kept alive solely for Friend Pulse;
- discard bounded Friend Pulse-only transient comparison state when its owner retires, unless the shared Steam cache
  independently owns the accepted source payload for another legitimate consumer;
- fence stale completion by generation/revision.

Do **not** tear down shared Steam infrastructure still required by Achievement Pulse or Abandonment Issues. Shared owner
lifetime follows real Steam consumer cardinality.

Opening Settings must not instantiate source/runtime work.

## 8. Retained Quick presentation

Use the existing process engine/window and ordinary retained widget host.

Expected shape:

```text
Steam source/request owner
  -> Friend Pulse preparation / immutable model
  -> runtime manager / lease
  -> retained Quick Friend Pulse component
```

Presentation requirements:

- stable root/list-model identity across ordinary snapshot updates;
- selectable Avatar Grid and Activity Rows views over that same retained model;
- deterministic bounded grid spacing and incomplete-row centering derived from configured capacity;
- presentation-safe presence plus current-game details in both views;
- unchanged accepted snapshot = no row tree rebuild / no avatar churn;
- mutate existing model roles where possible;
- no QWidget/QPainter fallback presenter;
- no business/source object exposed directly to QML;
- finite presentation-only animation for new-change emphasis is acceptable;
- no continuous hidden animation cadence.

## 9. Ordinary-widget normalization

Friend Pulse inherits the ordinary-widget contract, including:

- descriptor `custom_layout_resize_mode="ordinary_uniform"` / current equivalent;
- shared whole-card uniform CUSTOM resizing and absolute 40% floor;
- global CUSTOM disables authored stacking/adjacency rather than family code compensating locally;
- non-CUSTOM shared stacking/auto-fit participation;
- configured-capacity preferred geometry;
- shared Widget Theme / Style Overrides / card border / header semantics;
- shared hover/click glow behavior;
- shared edit-mode X / duplicate / Save / Cancel ownership;
- no family-local geometry persistence or theme cascade.

The default `420x180` scaffold geometry is only a starting authoring hint; eyes-on Quick layout may revise canonical
preferred dimensions if the actual useful row design needs it. Normalization contracts, not old pixels, are binding.

## 10. Settings design

Keep Settings small. Reuse the existing Steam family Connection / Privacy controls.

Friend Pulse-owned controls are limited to durable product behavior:

- Enabled;
- ordinary Position / Monitor;
- ordinary font/layout controls already expected by the family shell;
- View: **Avatar Grid** / **Activity Rows**.

Visible capacity is canonical at four and is not exposed as a user knob in v1.

Do not add:

- Refresh interval (Steam family already owns it);
- Privacy mode (Steam family already owns it);
- per-source fallbacks;
- avatar cache knobs;
- request batching knobs;
- diagnostic/source internals.

Any new collapsible Settings bucket identity must be added to canonical UI-state defaults in the same slice and obey the
current closed-by-default / one-open-per-local-scope contract.

## 11. Logging / security

- Steam API key never appears in logs/export/test fixtures/screenshots;
- validated Steam IDs may exist only in the account-private cache and owner-only runtime action map;
- Steam IDs and full action URLs are absent from QML roles, presentation snapshots, ordinary logs and generated
  Settings/default artifacts;
- logging may report counts, source status, batch counts, cache age, revision and lifecycle generation;
- no full friend payload dump in normal diagnostics;
- failure logs distinguish private/rate-limited/network/invalid response where current Steam result types support it.

## 12. Implementation phases

### F0 — evidence + rollback — implemented

- pin GODZIP/HEAD;
- audit current `friend_pulse` scaffold/default/descriptor hits;
- record which scaffold fields are still valid generic settings and which are dead mock residue;
- freeze current Steam sibling tests.

### F1 — source fixture contract — implemented

- add fixture-only FriendList + PlayerSummaries coverage;
- prove private/empty/rate-limited/malformed behavior;
- prove IDs remain inside the private cache/runtime boundary and secrets remain redacted;
- define accepted neutral snapshot types.

### F2 — bounded source preparation — implemented

- implement cache-first friend/source preparation through existing request policy;
- batch summaries without per-friend request fan-out;
- build previous-accepted-snapshot change evidence;
- no UI yet.

### F3 — lease / dormancy owner — implemented

- wire the standard Steam/runtime manager admission gates;
- prove two displays share one source result;
- prove zero Friend Pulse work with no effective consumer;
- prove stale completion rejected after disable/recreation.

### F4 — retained Quick card — implemented

- implement useful playing-first hierarchy;
- stable rows / configured capacity;
- private/empty/stale/error states;
- no avatars yet.

### F5 — privacy + Rich avatar enrichment — implemented

- Strict/Balanced/Rich projection;
- visible-row-only avatar hydration;
- cache/revision fences;
- no presentation identity leak in Strict.

### F6 — normalization / Settings / theming — implemented

- ordinary resize, stacking, global CUSTOM, glow, theme semantics;
- bucket/default schema updates only where genuinely needed;
- remove obsolete mock card presentation path if caller proof says it is dead.

### F7 — acceptance / ungate — automated gate GREEN, live/installed cells pending

- deterministic fixtures;
- request/backoff/cache tests;
- multi-display cardinality;
- enable/disable/family-deactivate/recreate soak;
- Settings-open dormancy;
- eyes-on long names/game names/privacy modes/theme contrast;
- performance comparison against Steam family disabled;
- ungate only after all are green.

## 13. Performance bars

Friend Pulse should be nearly static between Steam refreshes.

Reject implementation if it:

- creates presentation work at frame cadence;
- rebuilds unchanged rows every frame/refresh tick;
- downloads avatars outside visible Rich rows;
- performs one HTTP request per friend;
- creates one provider/timer/thread per display;
- measurably worsens Visualizer freshness/presentation tails merely by being enabled with unchanged Steam state.

The preferred optimization is always **less work / shared work / event-owned work**, never lowering another subsystem’s
reactivity or freshness.

## 14. Removal boundary

Until accepted, the implementation should remain removable as:

- Friend Pulse preparation/runtime/model/QML implementation;
- bounded descriptor/registration wiring;
- its canonical Settings/default additions;
- focused tests/docs;
- explicit migration cleanup for any retired scaffold keys.

Removing Friend Pulse must not require editing Achievement Pulse or Abandonment Issues business logic.

## 15. Acceptance summary

Friend Pulse is GREEN only when:

- it tells the truth about currently-playing friends;
- private/unavailable is never misrepresented as zero activity;
- Strict/Balanced/Rich materially enforce identity exposure policy;
- source requests are shared/bounded and existing Steam policy remains authoritative;
- multiple displays do not multiply source work;
- no effective consumer means no Friend Pulse-owned work;
- retained presentation obeys ordinary widget normalization/theme/CUSTOM rules;
- no secrets or private-cache IDs escape their admitted boundary;
- performance is effectively static between accepted Steam source updates.
