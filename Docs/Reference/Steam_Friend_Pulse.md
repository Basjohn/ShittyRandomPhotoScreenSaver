# Steam Friend Pulse — Current Product Contract

Status: **IMPLEMENTED / PUBLIC — CURRENT ARCHITECTURE REFERENCE**
Current sequencing authority: `Current_Plan.md`  
Stable widget id: `friend_pulse`

## 0. Purpose

Friend Pulse should answer one useful question at a glance:

> **Which of my Steam friends are online, what are they playing, and who else is in my roster?**

The pre-Quick mock card is not a fidelity target. The old scaffold survives only as evidence that the stable id,
Settings shell and family slot already exist. Product behavior is designed against the current Steam source/request
policy and retained Quick widget architecture.

This implementation must not become a Steam social client, chat client, activity-history database or a second Steam
provider. It is a small, privacy-aware activity card fed by the same bounded Steam ownership used by the existing
family.

### 0.1 Current runtime behavior

The retained card defaults to a dynamically spaced and centred **Avatar Grid** with eight authored visible friend slots;
a selectable compact **Activity Rows** view consumes the same stable row model and accepted snapshot. Both are virtualized
viewports: all online friends lead the roster, pinned friends retain priority inside the permitted projection, offline
friends fill remaining visible space, and every accepted friend remains scroll-reachable without allowing source
cardinality to own ordinary card height. Authored/non-CUSTOM grid width respects configured visible capacity; a CUSTOM
horizontal `content_extent` deliberately decouples columns from that baseline capacity and lets readable width admit more
columns up to the project-wide 24-friend ceiling. The final incomplete row remains centred. Grid names are optional,
Title-Case/bold/two-line fit, centred beneath avatars and independently size-adjustable. Tiles/rows show privacy-permitted
identity, ALL-CAPS presence/game chrome, offline-avatar desaturation and hard clipping. The redundant lower-right avatar
presence dot is retired. Strict mode groups anonymously and exposes neither names, avatars nor per-friend actions.

The source/cache/runtime path is cache-first, uses existing Steam locks/request coordination/backoff/redaction, and has
one Friend Pulse owner per runtime generation shared by every display. A coherent successful FriendList/PlayerSummaries
cache has **no age-expiry semantics**: freshness decides whether refresh is due and whether presentation is marked
cached/stale, while refresh failure keeps last-good data visible indefinitely. Rich avatar hydration follows only the
current bounded viewport and delivers local `file:` sources. Zero admitted consumers means no source refresh, avatar work
or live cadence; retirement fences source/avatar completion and discards bounded comparison state without deleting
last-good account cache.

Validated Steam IDs are permitted in the user's account-private Friend Pulse cache and the shared runtime owner. The
owner maps them to opaque fingerprints, strips them before delivering presentation snapshots, and QML emits only a row
index. Hover reveals a separate pin/favourite affordance; any number of accepted friends may be pinned and the
account-private persistence stores opaque friend fingerprints rather than presentation IDs. An admitted friend avatar
requests a directed Steam chat with public-profile fallback. Each friend also has one small three-dot action menu offering
View Profile, Start Chat, Copy Steam ID, and View Game in Store when a current AppID exists. The popup is retained once per
card, revalidates the current row in Python and uses the shared pointer-suppression seam. No Join Game item is shown because
PlayerSummaries proves only an AppID, not a joinable lobby/server/connect token. In interactive MC/diagnostic runs the
action router tries the Steam client; normal screensaver runs send approved HTTPS profile/Store targets through the
existing secure URL helper. The abandoned FriendMessages/unread experiment is not product architecture: no unread source,
message rows/menu, second Steam session, QR auth or message backoff traffic remains.

Friend Pulse is a normal visible Steam-family member, disabled by default at its ordinary member toggle. The implementation
also exposes a default-on themed `Show Friends Online Count` option that renders `X FRIEND(S) ONLINE` in the top-right
summary area from the already-owned snapshot count; it adds no source work. Shared CUSTOM side-axis reflow and Restore Size
are current architecture, not Friend Pulse-local geometry systems. `--devsteam` now owns only unfinished Games You Follow.
Live/installed acceptance debt is tracked only in `Current_Plan.md`; this document describes the landed product contract.

## 1. Current foundation to reuse

Current source already provides useful pieces that must remain the authority:

- `core/settings/widget_family_catalog.py` already registers `friend_pulse` inside the Steam family;
- canonical defaults already contain `widgets.friend_pulse` and the Steam family connection settings;
- `ui/tabs/widgets_tab_steam.py` exposes Friend Pulse normally and keeps only unfinished Games You Follow behind the
  Steam dev gate;
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

## 2. Product contract

### 2.1 Primary information

The card is a **complete observable friend roster**, ordered online first and offline last. Each accepted entry needs only
source-backed information:

- display identity when privacy policy allows it;
- current game name / app id when Steam reports it;
- optional avatar only in Rich mode and only for rows within the bounded current viewport;
- a small change cue when the accepted observation proves that friend newly entered or changed a game since the
  immediately preceding accepted observation.

Do not claim joinability, shared ownership, party availability, session start time, recent session duration or other
facts unless a current allowed Steam source explicitly supplies them. The historical mock phrase “playing a game you
own” is not a product requirement.

### 2.2 Useful summary

The compact card provides:

- header: **FRIEND PULSE** using the current shared Steam/branded-header vocabulary;
- optional default-on top-right **`X FRIEND(S) ONLINE`** summary when a ready/stale snapshot exists;
- bounded visible viewport with every accepted friend retained in the scrollable model;
- a brief theme-colored event glow only for transitions proven from two accepted snapshots.

The former `playing / total friends` summary rail and the abandoned unread-message summary are not current UI contracts.

All online friends precede offline friends. Playing/change state may order friends within the online partition, but must
never erase online-idle friends. Offline friends fill any remaining visible slots and remain available by scrolling.

### 2.3 Stable visible capacity

The default visible capacity is **eight**, user-adjustable from one through twenty-four. It is configuration-owned rather
than a height that expands/contracts with every refresh.

Configured capacity and authored width own the baseline preferred geometry. Momentary source count never owns ordinary
card height. A retained `GridView`/`ListView` scrolls the full model instead of truncating it or creating an eager delegate
tree. CUSTOM horizontal content extent is presentation state and may admit additional readable grid columns beyond the
configured baseline capacity; this does not mutate `visible_row_capacity` or the card's authored defaults.

### 2.4 Empty / private / stale / failure states

These states are semantically distinct:

- authoritative success + empty accepted roster -> honest **No friends** / equivalent quiet state;
- private friend list -> **Private / unavailable**, never “0 friends”;
- missing credentials/profile -> existing Steam connection/setup semantics;
- rate-limited/network failure with usable cache -> keep the last-good roster visible indefinitely and mark it cached/stale
  using the Steam family’s existing connection/staleness vocabulary; age never deletes a coherent successful cache;
- failure with no accepted cache -> explicit unavailable/error state;
- source response missing a friend/game field -> omit/unknown, never fabricate.

A stale accepted snapshot may remain visually useful, but stale data may not generate a new “just changed” cue.

## 3. Privacy contract

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
- the finite event glow is a non-interactive change cue and never pretends to be a Steam message notification;
- the game label may request the public/app-client Store action.

### Rich

- display names + current game;
- avatars may be shown for the current bounded visible viewport only;
- a visible avatar may request the admitted friend chat/profile action;
- all actions use source-provided validated identity and the existing semantic action-routing seam.

Changing privacy mode must reproject already accepted neutral state where possible. It must not force an unnecessary
network refresh merely to change pixels.

### 3.1 Semantic action boundary

- the account-private normalized cache may retain validated numeric Steam IDs; API keys remain credential-store only;
- the shared runtime owner holds the current fingerprint-to-ID map and clears it on last lease/retirement/failure;
- presentation snapshots and rows contain no Steam ID or URL, and QML emits only semantic signals plus a row index;
- the Python model revalidates the current visible row and owner map before forwarding an action;
- the per-friend menu offers only currently truthful actions: Profile, Chat, Copy Steam ID and Store when an AppID exists;
- Join Game remains absent until an admitted source provides a current joinable lobby/server/connect target;
- interactive MC/diagnostic runs try `steam://friends/message/<id>` or `steam://store/<appid>` and use the HTTPS
  profile/Store route when Qt rejects the protocol;
- normal screensaver runs send only the HTTPS profile/Store route through the existing secure helper and request the
  ordinary saver exit exactly once after successful handoff; if the helper cannot accept it, the action fails closed
  without a direct secure-desktop browser attempt or saver exit;
- a finite event glow means a newly observed game transition, not a Steam message notification. The current allowed Steam
  sources cannot deep-link to a particular chat message.

## 4. Source / request architecture

### 4.1 Allowed sources

Use the existing allowed Steam source metadata:

```text
FRIEND_LIST
    -> bounded friend ids
PLAYER_SUMMARIES
    -> observable persona/avatar/current-game fields
```

No additional source is added merely to decorate the card.

### 4.2 Shared refresh ownership

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

### 4.3 Accepted neutral state

Introduce a small immutable presentation-neutral source state, conceptually:

```text
FriendPulseSnapshot
    revision / accepted_at
    source_status / stale/cache metadata
    authoritative friend count if known
    roster entries[]
        internal stable identity (not logged/presented raw)
        display name if source supplies it
        app id / game label if supplied
        avatar reference if supplied
        persona/playing state needed for projection
    change evidence derived only from previous accepted snapshot
```

The exact types belong in a Friend Pulse-owned source/preparation module unless an existing neutral Steam model is a
literal semantic match. Do not inflate shared Steam models for speculative reuse.

### 4.4 Change detection

Change emphasis is derived only between coherent accepted snapshots. It is presentation/product state, not a second
poller.

- newly observed playing -> eligible subtle change marker;
- game A -> game B -> eligible subtle change marker;
- stale/error/private transition -> does not fabricate a game change;
- first accepted snapshot -> no “just started” claims;
- history is bounded to the minimum previous accepted identity/game mapping needed for the next comparison.

Do not build a persistent social-activity history database.

## 5. Avatar / asset policy

Avatar work is optional enrichment, never admission-critical.

- only Rich mode may request/render avatars;
- publish the current bounded viewport, then hydrate only those rows;
- use bounded cache/request ownership and the existing async image/resource path where it actually fits;
- no avatar prefetch for every friend;
- a failed avatar does not reject the row;
- avatar completion must be generation/revision fenced so stale rows cannot mutate a newer list.

If this creates a second independent image-downloader architecture, stop and reuse/extract the smallest current asset
seam instead.

## 6. Runtime / dormancy contract

Friend Pulse is admitted only when **all** runtime conditions are true:

```text
widgets.family_activation.steam
AND widgets.steam.enabled
AND widgets.friend_pulse.enabled
AND at least one admitted Friend Pulse presentation consumer
```

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

## 7. Retained Quick presentation

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
- deterministic width-derived grid spacing and incomplete-row centering: authored layout respects configured capacity,
  while CUSTOM horizontal extent may use additional readable columns up to the 24-friend ceiling;
- optional centred grid names plus a bounded independent name-font setting;
- one retained per-card three-dot action popup; never one popup per delegate and never the global right-click menu;
- presentation-safe presence plus current-game details in both views;
- unchanged accepted snapshot = no row tree rebuild / no avatar churn;
- mutate existing model roles where possible;
- no QWidget/QPainter fallback presenter;
- no business/source object exposed directly to QML;
- finite theme-colored presentation-only glow for proven game-change emphasis is acceptable;
- no continuous hidden animation cadence.

## 8. Ordinary-widget normalization

Friend Pulse inherits the ordinary-widget contract, including:

- descriptor/shared `ordinary_uniform` outer scale plus horizontal/vertical `content_extent` presentation reflow;
- corners/wheel remain whole-card uniform; side extent changes logical content only and does not mutate Settings;
- shared Restore Size clears extent and returns to separately retained authored geometry while preserving X/Y/display and
  remaining in CUSTOM;
- shared whole-card uniform normalization/40% floor outside family side-drag policy;
- global CUSTOM disables authored stacking/adjacency rather than family code compensating locally;
- non-CUSTOM shared stacking/auto-fit participation;
- configured-capacity preferred baseline geometry;
- shared Widget Theme / Style Overrides / card border / header semantics;
- shared hover/click glow behavior;
- shared edit-mode X / duplicate / Save / Cancel ownership;
- no family-local geometry persistence or theme cascade.
- CUSTOM child geometry is roster-shared, not delegate-owned: singleton Header / Online Count / Separator plus one shared Friend Frames, Avatars and Usernames record each. Repeated roles affect every row/tile consistently and never create per-friend persistence. The shared frame remains family-positioned and exposes size only; avatar/username placement is a shared offset applied uniformly across repeated items.
- selected-Edit collision may ignore only the structural frame↔avatar/username containment pairs so a containing frame does not block its own children; snapping/guides and collision against unrelated roles remain active.

The default `420x180` scaffold geometry is only a starting authoring hint; eyes-on Quick layout may revise canonical
preferred dimensions if the actual useful row design needs it. Normalization contracts, not old pixels, are binding.

## 9. Settings design

Keep Settings small. Reuse the existing Steam family Connection / Privacy controls.

Friend Pulse-owned controls are limited to durable product behavior:

- Enabled;
- ordinary Position / Monitor;
- ordinary font/layout controls already expected by the family shell;
- View: **Avatar Grid** / **Activity Rows**;
- visible friend slots: one through twenty-four, default eight;
- Show Names under Avatars;
- Name Font Size: eight through eighteen pixels.

Do not add:

- Refresh interval (Steam family already owns it);
- Privacy mode (Steam family already owns it);
- per-source fallbacks;
- avatar cache knobs;
- request batching knobs;
- diagnostic/source internals.

Any new collapsible Settings bucket identity must be added to canonical UI-state defaults in the same slice and obey the
current closed-by-default / one-open-per-local-scope contract.

## 10. Logging / security

- Steam API key never appears in logs/export/test fixtures/screenshots;
- validated Steam IDs may exist only in the account-private cache and owner-only runtime action map;
- Steam IDs and full action URLs are absent from QML roles, presentation snapshots, ordinary logs and generated
  Settings/default artifacts;
- logging may report counts, source status, batch counts, cache age, revision and lifecycle generation;
- no full friend payload dump in normal diagnostics;
- failure logs distinguish private/rate-limited/network/invalid response where current Steam result types support it.

## 11. Performance bars

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

## 12. Removal boundary

The implementation remains deliberately removable as:

- Friend Pulse preparation/runtime/model/QML implementation;
- bounded descriptor/registration wiring;
- its canonical Settings/default additions;
- focused tests/docs;
- explicit compatibility cleanup for any retired scaffold keys.

Removing Friend Pulse must not require editing Achievement Pulse or Abandonment Issues business logic.

## 13. Acceptance summary

The durable Friend Pulse contract is:

- it retains the complete accepted roster, orders all online friends first and fills remaining space with offline friends;
- private/unavailable is never misrepresented as zero activity;
- Strict/Balanced/Rich materially enforce identity exposure policy;
- source requests are shared/bounded and existing Steam policy remains authoritative;
- multiple displays do not multiply source work;
- no effective consumer means no Friend Pulse-owned work;
- retained presentation obeys ordinary widget normalization/theme/CUSTOM rules;
- no secrets or private-cache IDs escape their admitted boundary;
- performance is effectively static between accepted Steam source updates.
