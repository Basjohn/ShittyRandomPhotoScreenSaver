# SRPSS Steam Subwidgets — Design Proposal

**Status:** Draft 0.1 — product, data, visual, and settings contract  
**Scope:** Four independently enabled Steam cards for SRPSS: **Steam Progress**, **Achievement Pulse**, **Abandonment Issues**, and **Friend Pulse**.  
**Deliberately excluded:** any dependency on Steam's personalised Calendar or an undocumented authenticated Store feed.

---

## 1. Purpose and Design Position

These are not four views inside one oversized Steam widget. They are four separately controllable SRPSS overlay cards that share one Steam account/data layer and one coherent visual language. Think of them as a Widget Family if Subwidgets is too confusing.

Each subwidget must have its own:

- enabled toggle;
- normal authored position plus `Custom` position/size memory;
- display-field settings;
- cached visible state and local selection history;
- refresh cadence and last-success metadata;
- artwork/asset references appropriate to its own content.

They should still feel unmistakably like one family: the same Steam-logo header treatment, the same card/chrome language, the same clipped artwork wells, the same painter-owned art shadows, and the same field-row behaviour.

The shared Steam layer should own connection/authentication (we have OAuth functionality to genericify), library indexing, asset download/cache reuse, and bounded service requests. It must not become a giant widget that knows how every card paints itself. Each card owns its own presentation, scoring/selection logic, visible-state cache, and settings.

### Widget identity

| Runtime card | Header label | Purpose |
|---|---|---|
| `Steam Progress` | `STEAM  |  Steam Progress` | Surface the few meaningful changes in games already owned. |
| `Achievement Pulse` | `STEAM  |  Achievement Pulse` | Track one chosen game’s achievement progress in a visually satisfying way. |
| `Abandonment Issues` | `STEAM  |  Abandonment Issues` | Re-surface a previously played game that has been left behind, without confusing a short bounce with a neglected game. |
| `Friend Pulse` | `STEAM  |  Friend Pulse` | Show a small, attractive pulse of friends currently playing or recently detected changing games. |

---

## 2. Shared Family Contract

### 2.1 Steam account and data boundary

Create one explicit Steam provider/data layer, owned through SRPSS’s normal service/runtime seam. It should expose cached, typed results rather than let four widgets independently hit endpoints and reimplement cache rules.

The minimum shared records are:

- **Library index** — `appid`, canonical title, normalised search title, owned state, cumulative playtime, available artwork references, and any reliable last-played value.
- **Recent-games snapshot** — ordered recent app IDs, titles, playtime, and snapshot timestamp.
- **Game metadata/art cache** — header/capsule/library art variants, logos where available, local paths, dimensions, and asset validation timestamp.
- **Achievement snapshots per app** — full achievement set, unlocked state/timestamp, icons, global percentages where available, and selection metadata.
- **Owned-game event ledger** — previously seen announcement/update fingerprints, score, last-seen time, and dismissal/expiry state.
- **Friend snapshot ledger** — friend IDs, current observable status, game state if available, avatar reference, previous observed state, and event cooldowns.

The shared layer should use the existing SRPSS manager ownership model rather than private worker threads, timers, queues, or one-off cache paths.

### 2.2 First run and offline behaviour

Every Steam card should be cache-first:

1. Use its last valid cached card state immediately.
2. Begin an ordinary deferred refresh only once the display is idle and the widget is actually enabled.
3. Preserve the visible cached card when a refresh fails, yields an empty response, or is blocked by privacy.
4. Not fade in when no cache exists, but fade in when it does. Our Fade co-ordinator is already robust.

A settings tab opening must never be the trigger for a provider request, cache migration, asset scan, or credential check. A deliberate `Refresh Steam Library` / `Refresh Steam Data` action may do that through normal background ownership.

### 2.3 Refresh pacing

The cards should feel current without behaving like live dashboards.

| Data | Default cadence | Notes |
|---|---:|---|
| Recent games | 15 minutes while at least one Steam card is active | Provides the dynamic source for Most Recent and the recent slots. |
| Friend state | 15 minutes while Friend Pulse is active | Snapshot/delta based; no per-frame “presence” polling. |
| Selected-game achievements | 30 minutes while Achievement Pulse is active | One app only, plus a manual refresh route. |
| Library ownership/index | 24 hours, manual refresh available | Refresh only when needed; this is the autocomplete source. |
| Steam Progress candidate news/events | 6 hours for a bounded candidate set | Never brute-force the whole library in one pass. |
| Artwork/avatar downloads | On demand, then cache validated by asset metadata | Never download, decode, or scale in paint paths. |

The exact minutes can be tuned later, but the contract matters more than the starting values: no network work from `paintEvent`, no polling merely because a card is visible for another frame, and no redundant cache writes/repaints when the resolved visible state is unchanged.

### 2.4 Shared visual language

Every card uses:

- a compact Steam logo + subwidget-name header in the same family as the existing Gmail/Spotify/Reddit headers;
- a framed translucent customizable dark card with the established border, type hierarchy, and spacing; (Same colour options/border/etc all our widgets have!)
- heavily used artwork, clipped cleanly within rounded internal artwork wells;
- painter-owned, cached multi-pass art shadows and highlights rather than a new Qt graphics effect attached to each artwork element; Ideally use our existing shadow system as that is functioning well.
- soft dark gradients over art so text remains legible while the image still matters;
- high-DPI-aware cached image variants;
- card-level styling inherited from SRPSS global card/chrome controls, with only the new Steam-specific visual settings local to the Steam family.

No subwidget should invent a new visual system, duplicate a large QSS block, or use a default-looking Qt control for a custom runtime surface.

### 2.5 Common optional-field layout

All four widgets need a shared **visible fields** convention.

- Each card has a small set of primary visual content that always remains structurally stable: its header, main artwork, title/context, and core metric or event.
- Supporting fields are individually toggleable.
- Enabled supporting fields render in a defined priority order, compactly left-to-right in an information rail.
- The first four enabled fields occupy the first rail.
- When a fifth field is enabled, a second aligned rail appears automatically; fields 5–8 occupy it.
- Disabled fields leave no holes. A card must not keep empty placeholders merely to preserve an old layout.
- `Custom` dimensions reflow the internal layout without changing the committed outer geometry.
- Customizability is core. Each displayable section of each widget should be able to be turned on or off and the layout should adjust the size, padding and spacing of the card to suite this. Options presented in Settings GUI as circle checkboxes or Styled comboboxes when relevant. Avoid making Settings Dialog load/start up worse or churn as a basic policy from the start of this. 


The default order is intentionally curated per widget; users should not have to hand-sort labels just to prevent a messy card.

---

## 3. Steam Progress

### 3.1 Product statement

**Steam Progress** answers: *“What materially changed in games I already own and might actually care about?”*

It must not become an unfiltered announcement ticker. The point is a short, curated pulse of meaningful game changes: substantial content updates, expansions, 1.0 releases, major events, or a meaningful return of a game the user previously played.

### 3.2 Content acquisition

The widget should maintain a bounded candidate pool rather than attempt to scan every owned game repeatedly.

#### Default candidate pool: Focus Library

The default pool combines:

1. **Recently played games** — strongest relevance signal.
2. **High-playtime owned games** — configurable count, for games that have a real history with the user.
3. **Manually watched games** — a small optional list for games the user wants tracked regardless of playtime.
4. **Recent Steam Progress winners** — retained briefly to prevent an important update disappearing before it has been displayed.

The default pool should be capped, for example around 30–50 titles after de-duplication. News/event retrieval runs only against this bounded pool.

#### Optional scope: Broad Library

`Broad Library` is optional and off by default. It slowly round-robins through the remaining eligible library in small batches across the day. It is a coverage mode, not a promise that every owned title is checked in real time.

#### Event classification and anti-mess scoring

Each candidate announcement gets a local score. It is not pretending to reproduce Valve’s personal Calendar logic.

Suggested scoring signals:

- **Strong positive**: game 1.0 release, major expansion, new chapter/region/class, large content event, official sequel/crossover event, major Early Access milestone.
- **Moderate positive**: substantial update or a meaningful DLC release for a game the user has played.
- **Low positive**: normal patch note or seasonal event.
- **Strong negative / exclusion**: localisation-only post, routine server maintenance, cosmetic item post, tiny hotfix, duplicate repost, generic sale reminder, old announcement that has already been shown.
- **Relationship score**: recent play, total playtime, manual watch state, whether the game has appeared in the user’s recent library history.
- **Recency score**: newest matters, but it should not outrank a genuinely major update solely because it is two hours newer.

A minimum score filters noise. The card uses the top result by default, while a small internal rotation queue may hold the next few legitimate candidates.

### 3.3 Display

**Default composition**

- Header: `STEAM | Steam Progress`.
- Large clipped game header art.
- Game title.
- Strong event label: `Major Update`, `Expansion`, `1.0 Release`, or `Game Event`.
- Event headline, one line by default.
- Small “newness” cue such as `Today`, `2 days ago`, or `New since last shown`.

**Optional display fields**

- event date/age;
- event category;
- one-line event summary;
- total playtime;
- last played, only when the underlying timestamp is reliable;
- “watched” marker;
- source/newness marker;
- a second/third queued event count.

A multi-item mode may show two compact event strips beneath the hero item. It should be limited to avoid turning into another Reddit list.

### 3.4 Settings

- enabled;
- standard position/scale/opacity plus `Custom` position and size;
- content scope: `Focus Library` (default), `Broad Library`, `Watched Games Only`;
- maximum visible items: 1, 2, or 3;
- significance threshold: `Major Only`, `Balanced` (default), `Include Patches`;
- watched-game editor;
- event categories to include;
- individual optional-field toggles;
- artwork style: wide header art / portrait art where available;
- manual refresh;
- optional click action, routed through SRPSS’s shared input/opening path rather than a private browser helper.

### 3.5 Cache

Store the top resolved display candidates, source fingerprints, classification result, score, display history, and a bounded local event ledger. This prevents repeated re-display of the same announcement after each refresh and lets cache-first startup show a valid card without waiting for a network request.

---

## 4. Achievement Pulse

### 4.1 Product statement

**Achievement Pulse** is the most focused Steam subwidget. It follows one game at a time and treats achievement progress as a visual object, not a spreadsheet.

### 4.2 Game-selection contract

The game source is a saved mode, not merely a temporary title string.

| Mode | Meaning |
|---|---|
| **Most Recent** — default | Resolve the current most recently played eligible game whenever the recent-games snapshot updates. |
| **Recent #2** through **Recent #5** | Resolve that live position in the ordered recent list. The settings label displays the current resolved title beside the slot. |
| **Custom** | Persist a selected `appid` as the authoritative tracked game. It remains selected even when it leaves recent history. |

`Custom` is the solution to the important persistence problem: it stores an app ID, not “whatever was fifth in the recent list when the user clicked it.”

#### Custom autocomplete

`Custom` should use the local Steam library index, not an online search service:

- an editable search field searches canonical/normalised owned-game titles;
- results show title and small artwork/icon;
- choosing a result commits `appid` + canonical display title;
- the persisted value is the app ID;
- an old custom selection remains valid from cache even if it no longer appears in the current recent list;
- an explicit `Refresh Steam Library` action rebuilds/updates the local index when needed.

On a first installation with no library index yet, the field should say that the Steam library needs to be indexed and provide the explicit refresh action. It should not quietly make a network request merely because the Achievement Pulse settings page was opened.

#### Eligibility

Dynamic modes should have a `Skip games with unavailable achievements` toggle, default on. This prevents a recent utility, soundtrack, or achievement-less title from turning the card into a dead panel. A Custom selection remains literal: if the chosen game has no retrievable achievement data, show a concise unavailable state rather than silently substituting another game.

### 4.3 Display

**Default composition**

- Header: `STEAM | Achievement Pulse`.
- Large game header/cover art, clipped and shadowed.
- A large adjustable-colour circular progress ring.
- Completion percentage inside the ring.
- Game title.
- `Unlocked X / Y` beneath or beside the ring.
- One achievement tile with its actual icon: by default the most recently unlocked achievement.

The percentage ring must be a proper painter-drawn circular element with an adjustable colour setting. It should not be a static image or a generic progress bar.

**Optional display fields**

- unlocked / total;
- total game playtime;
- latest unlocked achievement;
- date of latest unlock;
- rarest unlocked achievement;
- global rarity of the highlighted achievement;
- rarest locked “collector target”;
- last played;
- current tracking source, for example `Most Recent` or `Custom`.

“Collector target” must not imply the app knows the logical next achievement to pursue. It only means the most globally rare currently locked achievement selected by the chosen rule.

### 4.4 Settings

- enabled;
- standard position/scale/opacity plus `Custom` position and size;
- tracking mode: Most Recent, Recent #2–#5, Custom;
- local-library autocomplete for Custom;
- skip-unavailable toggle for dynamic modes;
- progress-ring colour;
- artwork style;
- highlighted-achievement mode: `Latest Unlock` (default), `Rarest Unlock`, `Rare Target`;
- individual optional-field toggles;
- manual refresh.

### 4.5 Cache

Cache the selected app snapshot separately from the global Steam library index:

- resolved app ID/title and selection source;
- achievement state and icons;
- ring metrics;
- highlighted achievement;
- prior unlock set and timestamps;
- globally rare percentages when available;
- source and refresh status.

A change in the selected app’s unlocked set should create a small local “pulse” state for later visual treatment, but must not cause continuous repainting or a permanent animation loop.

---

## 5. Abandonment Issues

### 5.1 Product statement

**Abandonment Issues** is a deliberate library resurfacer. It should identify games that have enough real playtime to suggest the user was engaged, then have been untouched long enough to feel like a forgotten world rather than a 12-minute bounce.

### 5.2 Data requirement: reliable last-played time

This widget must not fabricate inactivity dates from total playtime or the short recent-games list.

Before implementation, the Steam data discovery pass must prove a reliable last-played source for the user’s owned games. If the current Web API response provides it consistently for the intended account, use it. If it does not, establish a narrowly scoped local Steam-client source or omit unprovable candidates. The widget should never show a confident “you last played this 84 weeks ago” line based on a guess.

### 5.3 Candidate selection

**Default eligibility**

- owned game;
- playtime above a configurable minimum, default **2 hours**;
- reliable last-played timestamp;
- last played more than a configurable minimum, default **12 weeks**;
- not currently in the recent-games source;
- not displayed by this card inside its cooldown window.

**Default score**

1. More meaningful historical playtime raises relevance.
2. Longer inactivity raises relevance.
3. Recent card exposure lowers relevance sharply.
4. Games marked `Never Show` are excluded.
5. A manually `Pin`ned title can become the current card regardless of smart scoring.
6. Known completion, where it is already available from a tracked achievement snapshot, can lower priority; it must not trigger a huge library-wide achievement scan merely to find completions.

The default card rotates locally through the top qualified candidates on a slow visual schedule. Rotation is from cache; it is not a reason to run another Steam request.

### 5.4 Display

**Default composition**

- Header: `STEAM | Abandonment Issues`.
- Large game artwork treated like a treasured dusty box on a shelf rather than a shame screen.
- Game title.
- total hours played;
- last played age, only from a reliable source;
- a short line such as `A world left behind` or `You had 37 hours here`, kept restrained and not excessively naggy.

**Guilt Desaturater**

A `Guilt Desaturater` toggle exists and defaults **off**.

When enabled, the currently chosen game’s artwork becomes increasingly monochrome as its recorded inactivity increases. The art treatment is the only expression of the score:

- no visible percentage;
- no “weeks guilty” counter;
- no hidden label explaining a punishment score;
- the card still shows its ordinary last-played text when that optional field is enabled;
- the implementation uses a smooth capped curve so a game left for years looks weathered, not badly broken.

The default off state preserves the game’s full artwork colour.

**Optional display fields**

- total hours;
- last played age;
- title/subtitle;
- first/last seen by SRPSS;
- candidate source: smart rotation or pinned;
- completion context when already known;
- small `Pinned` marker;
- queue position, off by default.

### 5.5 Settings

- enabled;
- standard position/scale/opacity plus `Custom` position and size;
- selection mode: Smart Rotation / Pinned Game;
- minimum playtime;
- minimum inactivity;
- rotate interval;
- `Guilt Desaturater` — default off;
- `Never Show` list;
- optional pinned-game picker using the same local-library autocomplete source;
- individual optional-field toggles;
- manual refresh.

### 5.6 Cache

Persist candidate history, last shown time, pinned/excluded app IDs, resolved image path, and any reliably sourced last-played timestamp. The cache must distinguish “we do not know last played” from “last played is unknown because refresh failed.”

---

## 6. Friend Pulse

### 6.1 Product statement

**Friend Pulse** should feel social and alive without degrading into a constant online-status list.

Version one should focus on observable, low-noise events:

- a friend currently playing a game;
- a friend newly detected as having started a game since SRPSS’s last valid snapshot;
- a friend playing a game the user owns;
- optionally, a selected favourite friend coming online or returning to a game.
Part of this is every feature that could have multiple simultaneous results such as online friends will have the option of "Single Rotating" (Focus on an individual friend avatar and stats default rotates 15 minutes) "Adaptive Grid" (Shrink avatars into a grid based on how many) "List" Small avatars with user names next to them. Offline friend avatars are desaturated.
It should not promise retrospective achievement, review, completion, or purchase events that the supported data cannot reliably provide.

### 6.2 Source and privacy contract

Friend Pulse is inherently privacy-sensitive. It needs graceful branches for:

- friend list unavailable/private;
- individual profile details unavailable;
- friend visible but no current game state;
- no usable artwork for a game;
- a fresh installation with no prior snapshot, meaning “started playing” cannot yet be inferred.

The widget should never treat an empty/unauthorised friend response as proof that every friend is offline. Preserve a valid prior cache, record the error through the normal diagnostic path, and show a compact unavailable state only when there is no cached content.

### 6.3 Event ledger

Friend Pulse becomes interesting through a tiny local event ledger.

At each bounded friend snapshot:

1. resolve friend identities and avatars;
2. resolve observable current game state;
3. compare to the prior valid snapshot;
4. create a local pulse event only for meaningful changes;
5. apply a per-friend/per-game cooldown so the same friend does not dominate the card.

Examples:

- `Mira started playing Hades II`
- `Alex is playing Baldur’s Gate 3`
- `Jon returned to a game in your library`
- `Three friends are playing now`

A “started playing” time is the time SRPSS first observed the change, not a claim to know their exact Steam session start.

### 6.4 Display

**Default composition**

- Header: `STEAM | Friend Pulse`.
- Wide clipped header art for the active game.
- One large circular friend avatar partly overlapping the art frame.
- Friend name.
- One short status line: `is playing <game>`.
- A small `In Your Library` marker when app ID overlap is known.
- Optional secondary avatar stack for additional currently active friends.

**Optional display fields**

- friend avatar;
- friend name;
- game title;
- shared-library marker;
- observed “started playing” age;
- approximate number of other active friends;
- persona/status indicator;
- secondary avatar stack;
- event type label.

The widget should default to showing only playing/game-change content. A broader `Include Online Idle Friends` option can exist, but should default off because idle-presence rows are less visually meaningful.

### 6.5 Settings

- enabled;
- standard position/scale/opacity plus `Custom` position and size;
- friend scope: All Friends / Favourites / Selected Friends;
- content filter: Currently Playing, New Game Pulse, Shared-Library Priority;
- maximum active friend cards/avatars;
- same-friend event cooldown;
- `Include Online Idle Friends` — default off;
- local favourites/selected-friend editor populated from the cached friend directory;
- artwork style;
- individual optional-field toggles;
- manual refresh.

### 6.6 Cache

Persist:

- friend directory snapshot;
- avatar asset references;
- last observed game/presence state;
- generated local pulse events and expiry;
- favourite/selected friend IDs;
- per-friend/per-game cooldowns;
- last successful refresh and privacy/error state.

---

## 7. Settings and Persistence Shape

The final settings UI should follow SRPSS’s descriptor and lazy-build conventions after the codebase pass. The product shape is:

### Shared Steam settings

- Steam account/API configuration;
- Steam ID/profile resolution;
- `Refresh Steam Library`;
- cache/status summary;
- shared asset cache settings;
- shared refresh diagnostics/status;
- a global “Steam integration enabled” state only if SRPSS’s existing services use that convention.

### Four independent subwidget settings blocks

Each card receives its own settings, its own enabled toggle, its own location/Custom data, its own field toggles, and its own cache/selection state. A tidy UI is desirable, but not at the cost of adding a special second routing system outside the established descriptor registry.

All Steam sections are registered yet lazy-built. Opening the general settings dialog must not construct their controls, query Steam, authenticate, inspect a cache, or create live runtime widgets. First visit builds the UI once and reuses it; saving without visiting a Steam section must preserve its prior persisted values.

---

## 8. Architecture Boundaries

### Shared ownership

- shared provider/data cache;
- shared library autocomplete index;
- shared artwork/avatar download and local asset cache;
- shared Steam connection/error diagnostics;
- shared timer/worker ownership through existing managers;
- shared settings/defaults/descriptor infrastructure.

### Widget-local ownership

- painter/layout code;
- event scoring/presentation;
- current card selection;
- display-field priority;
- widget-local visible cache;
- custom-card geometry response;
- local settings and local cache validity decisions;
- optional click semantics.

### Explicit non-goals

- no dependency on Steam Personal Calendar;
- no logged-in Store scraping or fragile undocumented private endpoints;
- no continual per-frame updates;
- no whole-library news scan at every refresh;
- no giant cross-widget mutable “Steam state” blob;
- no private timer/thread/queue framework;
- no Qt artwork shadow effects newly layered onto every card;
- no made-up inactivity dates or friend-history claims.

---

## 9. Discovery Gate Before Implementation

A short targeted feasibility pass should precede UI implementation.

1. Confirm the current SRPSS Steam authentication/key approach and how credentials are stored.
2. Confirm the exact returned payloads for:
   - owned library and recent games;
   - one achievement-rich owned game;
   - global achievement percentages;
   - friend list and batched player summaries.
3. Prove the reliable source for per-game last-played dates needed by Abandonment Issues.
4. Verify the best image/art sources and their cache behaviour for a representative sample of games.
5. Inspect the current runtime base-overlay/header/shadow/asset helpers and the descriptor/settings flows, then map this proposal onto actual module names.
6. Decide whether the settings UI should expose four standard lazy sections or a descriptor-supported Steam family hub.
7. Build a small mock-data render harness for all four cards before real Steam data is allowed to shape layout.

The resulting technical note should state which fields are confirmed, conditional, unavailable, or intentionally excluded. This prevents a pretty card design from committing SRPSS to data Steam cannot actually supply.

---

## 10. Suggested Implementation Order

1. **Steam data discovery + local library index**
2. **Shared Steam asset/cache service**
3. **Achievement Pulse** — smallest, richest, and most self-contained data contract
4. **Abandonment Issues** — only after reliable last-played data is established
5. **Friend Pulse** — privacy-aware snapshot/delta implementation
6. **Steam Progress** — most editorial/scoring-heavy and therefore best built once the family data/cache infrastructure is proven

---

## 11. Acceptance Criteria

### Family-wide

- Four independent descriptor-backed cards can be enabled, disabled, positioned, custom-positioned, and reset without affecting each other.
- Shared Steam data is fetched once per needed refresh category, not once per widget.
- Cache-first startup works without a blank flash.
- No provider/cache/auth work occurs merely by opening or hydrating settings.
- No paint path performs network work, image decoding, lazy pixmap conversion, or unnecessary full repaint loops.
- Artwork is visibly strong, properly clipped, and uses painter-owned rather than new Qt-effect shadows.
- Any fifth enabled optional field creates the next aligned data row rather than squeezing or clipping the first row.
- `Custom` geometry remains authoritative while dynamic content updates.

### Steam Progress

- Never displays routine noise by default.
- Never repeats the same event on every refresh.
- Uses a bounded candidate pool and bounded scan schedule.

### Achievement Pulse

- Default mode is Most Recent.
- Custom autocomplete selects and persists an app ID.
- A Custom game remains tracked after it leaves the recent-games list.
- Progress ring colour is user-adjustable and percentage is inside the circle.

### Abandonment Issues

- Default eligibility excludes brief bounces.
- No last-played age is displayed without a reliable source.
- Guilt Desaturater exists, is default off, and affects only art saturation.

### Friend Pulse

- Uses avatar plus game artwork for real game-state cards.
- Does not convert unknown/private data into “everyone is offline.”
- “Started playing” is clearly treated as an SRPSS-observed local change, not an exact Steam session time.
