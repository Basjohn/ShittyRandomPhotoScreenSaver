# Steam Games You Follow — Feasibility-First Product Decomposition

Status: **NEAR-FUTURE / DEV-GATED / NOT IMPLEMENTED**  
Last updated: 2026-09-13  
Current sequencing authority: `Current_Plan.md`  
Stable compatibility id: `steam_progress`  
Product name: **Games You Follow**

## 0. Purpose and admission boundary

Games You Follow is the replacement product meaning for the unfinished Steam
Progress / Steam Journey scaffold. It is a small retained card for recent news
from games the user has explicitly followed. It is not a personalised Steam
news feed, a whole-library scanner, a Store scraper, or a general RSS/browser
client.

`--devsteam` remains the gate for this unfinished replacement only. Achievement
Pulse, Abandonment Issues, and Friend Pulse stay normally visible Steam-family
members. `steam_progress` remains the compatibility id until a caller-proven
migration can retire it; no parallel `games_you_follow` runtime identity,
provider, settings root, or legacy presenter is to be introduced.

The source shape is now concrete enough to plan against without inventing a
second authentication model. Steam exposes `IStoreService/GetGamesFollowed/v1`
for the account's followed AppIDs. Current Steam protocol metadata marks that
method `eWebAPIKeyRequirement=1`; the request body itself is only the linked
SteamID64, so the intended SRPSS route is the **same user Web API key + linked
SteamID64 credential class already admitted for the Steam family**. This must
still be fixture/live-proved with the exact client request form before product
code is admitted; if Valve rejects the current user-key path, the feature stays
dev-gated. Do not add QR/Steam Guard auth, cookies, browser automation, a second
Steam login/session, or relabel owned/recent/wishlist data as follows.

For each admitted followed AppID, public app-specific
`ISteamNews/GetNewsForApp/v2` (`APP_NEWS`) supplies bounded news material. It has
transport/schema evidence for app id, stable item id, title/body, date, feed
metadata/tags, and source URL and does not require the publisher-only
`GetNewsForAppAuthed` path. It is not a library-wide personalised feed. The
remaining G0 work is therefore **credential/request-shape proof, bounded fan-out
measurement, URL/image policy and fixtures**, not discovery of a speculative
follow authority.

## 1. Product contract

- Show accepted news only for a bounded explicit follow set. The card never
  infers follows from owned, recently played, wishlisted, or friend activity.
- One card has two retained presentation choices: `single_row` (one selected
  story) and `double_row` (two selected stories). Both consume the same stable
  model and accepted snapshot.
- Each visible story has a source-proven news-item image when one is safely
  available, game/title context, headline, and truthful published/source
  metadata when supplied. Shape-matched app-id artwork is the fallback when the
  item has no admitted news image or that image cannot be accepted.
- The chosen artwork shape is `wide` by default, with `square` and `portrait`
  options matching the existing Steam asset contract. A missing requested shape
  may make exactly one bounded alternate-shape attempt; transient asset failure
  does not fan out.
- Clicking the rendered news/app artwork is a semantic Store action. Clicking a headline is a semantic
  source-article action only when its exact URL passes the approved policy.
- Alignment is a presentation preference (`left`, `center`, `right`) applied to
  title/headline metadata as a coherent layout, not to provider ranking.
- Text remains single-purpose and legible: bounded lines plus normal QML elision
  are authoritative. `headline_truncation_chars` is an explicit source-text
  threshold before model delivery. A full headline may use the existing
  event-driven tooltip/focus pattern when, and only when, text is actually
  elided; there is no ticker, carousel, or recurring text timer.
- Private, unavailable, empty-follow-list, stale-cache, invalid-source-URL, and
  no-usable-news states are distinct. The card must not substitute unrelated
  games/news or claim that no news exists when its source is unavailable.

## 2. G0 — required feasibility decisions before any product code

- [ ] Fixture/live-prove the existing-credential follow-set route:
  `IStoreService/GetGamesFollowed/v1` + linked SteamID64 + the already configured
  user Web API key, through the existing backend/request/redaction machinery.
  Confirm response shape, private/unavailable behavior and whether the current
  client request form is accepted. If this exact route fails, stop the feature at
  G0; do **not** add QR/Steam Guard auth, cookies, a second Steam session, Store
  scraping, or an owned/recent/wishlist semantic substitute.
- [ ] Capture fixture-backed `APP_NEWS` response evidence: identity/date/title,
  direct news-image fields or safely extractable structured media, missing/
  malformed fields, URL forms, empty response, 401/403/429, cache use, and
  per-app result size. Set a measured per-follow-set request/candidate budget
  from that evidence; do not scrape article pages, scan an unbounded library or
  add a fallback source.
- [ ] Establish the source-article URL policy. The current Steam asset host
  allowlist validates images, not arbitrary article navigation. Prove which
  HTTPS hosts/redirect rules can be accepted and routed by the existing secure
  helper. Until then, source URLs are display metadata and headline navigation
  is disabled/fails closed rather than opened directly.
- [ ] Establish the news-image URL policy independently of article navigation.
  Admit only a direct structured source field or bounded, safely parsed media
  reference proven by fixtures, then validate host, scheme, bytes and image
  signature before local caching. If that evidence is absent, use app artwork;
  never fetch or scrape the article page merely to discover an image.
- [ ] Verify the exact public `APP_NEWS` client request form and keep the
  publisher-only `GetNewsForAppAuthed` endpoint excluded. Define the privacy
  behavior of `GetGamesFollowed`: key/SteamID stay in existing
  credential/account-private storage, never in Settings, QML roles, logs,
  fixtures, cache filenames, or action URLs.
- [ ] Pin pre-feature HEAD and preserve the `steam_progress` scaffold/default
  migration inputs only. It is not a visual or runtime fidelity target.

G0 is the admission gate. A failed spike leaves the feature dev-gated and
unimplemented; it does not authorize Store scraping, cookies, browser automation,
publisher-only `NEWS_AUTHED`, a bundled key, or a substitute provider.

## 3. Target source, cache, and model seam after G0 passes

```text
existing-key GetGamesFollowed authority
    -> bounded APP_NEWS requests through existing backend/request policy
    -> account-private versioned cache records per approved app/batch
    -> immutable GamesYouFollowSnapshot
    -> one generation-scoped shared runtime owner + display leases
    -> stable retained presentation model
    -> existing Quick scene / ordinary host
```

### 3.1 Source and cache rules

- Reuse `core/steam/backend.py` source metadata, redaction, transport bounds,
  `SteamRequestCoordinator`, per-source locks/backoff, and `SteamResult` status
  vocabulary. Add no card-local HTTP, API-key path, timer, or thread.
- Add a feature-owned cache module/key namespace, not overloaded achievement or
  Friend Pulse cache records. Use `SteamCacheRecord`'s versioned atomic envelope
  beneath the opaque profile cache directory when the selected follow authority
  is account-private; use no raw SteamID in a path or cache key.
- Cache a minimal normalised payload: schema/revision, follow-set fingerprint or
  revision, app id, source item id, normalised headline, published timestamp,
  feed/tags needed for selected ranking, source URL and news-image reference only
  when policy-approved, and source/cache freshness provenance. Never cache raw
  response bodies merely for convenience.
- Cache only successful coherent results. Private, failed, malformed, rejected
  URL, or stale-generation completions never freshen a record. **Successful
  cache records do not expire merely because their freshness window passes.**
  Freshness controls refresh admission and stale labeling, not usability or
  deletion. On source failure keep the last-good followed set and last-good news
  visible indefinitely as cached/stale evidence until a later coherent refresh
  succeeds. Only explicit account/cache reset, schema rejection/corruption, or a
  proven identity change may remove that retained evidence. Never substitute
  owned/recent/wishlist games or unrelated news just because fresh follow data is
  unavailable.
- Deduplicate by app id plus stable source item id; define a deterministic
  fallback identity only after the endpoint fixture proves which stable fields
  survive. No persistent reading-history/dismissal database enters v1 unless a
  separately admitted product requirement needs it.

### 3.2 Neutral and presentation-safe models

Create feature-owned frozen types rather than expanding generic Steam models
prematurely:

```text
GamesYouFollowItem
    appid, item_identity, headline, published_at, feed_name/tags
    approved_article_url?     # never a QML role
    approved_news_image?      # private owner target, never a QML network URL
    artwork_state/shape       # selected local-file source after hydration

GamesYouFollowSnapshot
    status, accepted_at, from_cache/stale, authoritative
    follow_set_state, items[], source counts/revision

GamesYouFollowRow
    game label, display headline, source metadata, local artwork source
    store_action_available, article_action_available
```

The runtime owns action targets. QML gets text, local `file:` artwork, action
availability, and an index only; it never receives AppIDs, article URLs,
credentials, profile identifiers, raw endpoint payloads, or raw asset URLs.
Ranking is explicitly a G0/product decision, but must be deterministic and
bounded (for example: approved newest published item per followed app, then
newest timestamp and stable identity). Do not call it “personalised” unless a
proven source supplies that meaning.

### 3.3 News image and artwork fallback

- Prefer an admitted, source-proven news-item image. Download it only through
  the same bounded host/scheme/byte/signature validation and atomic local-cache
  discipline used by Steam assets; QML receives only a local `file:` source.
- When no news image is admitted, is missing, or is definitively invalid, reuse
  `core/steam/assets.py` app-art URL construction and its one bounded
  alternate-shape order. `wide` is the canonical default; square/portrait
  retain their existing semantics. Transient news-image failure does not fan
  out through speculative hosts or article scraping.
- Apply the selected `wide`/`square`/`portrait` crop contract to news images as
  presentation geometry; app-art fallback requests the matching canonical
  shape. Preserve aspect ratio with bounded cropping rather than distortion.
- Rank visible rows before enrichment; only hydrate artwork for selected visible
  rows. A failed or missing image leaves a styled local no-art state and does not
  reject otherwise useful headline text.
- All image completion is generation, snapshot-revision, item identity, AppID,
  requested shape, source kind and selected-row fenced. Old local image
  completion cannot alter a newer story.

## 4. Runtime, dormancy, and interactions

Admission must require all of:

```text
widgets.family_activation.steam
AND widgets.steam.enabled
AND widgets.steam_progress.enabled
AND --devsteam
AND a real Games You Follow presentation consumer
AND the G0-proved existing-key GetGamesFollowed source configuration
```

- Build one shared owner per runtime generation and one lease per admitted
  display. Leases differ only in presentation configuration; they do not create
  duplicate source requests, cache loads, workers, cadence, or asset jobs.
- Use only canonical `widgets.steam.refresh_minutes` for periodic refresh after
  G0 proves an appropriate bounded request budget. Manual refresh is one bounded
  source request through that same owner, never a new loop.
- Cache-first startup delivers the last-good accepted snapshot before optional
  refresh, regardless of age. An old snapshot is marked cached/stale but remains
  useful; refresh failure never clears it. Unchanged snapshot/model data causes
  no row rebuild, image churn, or layout solve. Settings opening imports/starts
  nothing.
- Last effective lease release stops/suppresses schedule work, cancels/fences
  completion, clears feature-only selected/action/artwork state, and retires the
  shared owner. It must not shut down Steam work legitimately owned by the other
  Steam cards.
- Use a stable Python list model and retained QML component; no QWidget/QPainter
  presenter, QML network object, provider business object, `Timer`, polling,
  second Quick surface, or compatibility facade.
- App art emits `store` plus row index. Python revalidates its current private
target and uses the existing Steam Store action route. Headline emits
`source_article` plus row index; Python resolves only an approved current URL.
Interactive MC/diagnostic use must use the established action router. Normal
screensaver use goes through the existing HTTPS secure-helper path and exits
exactly once only after accepted handoff; helper rejection fails closed with no
direct browser attempt or exit.

## 5. Retained Quick and geometry contract

- Add one retained `GamesYouFollowPresentation.qml` under the existing ordinary
widget registry/binder path, with a presentation model owned in Python and one
stable list-model identity.
- `single_row` and `double_row` are configuration-owned, complete-card geometry
variants. Source count never changes ordinary-card height; excess accepted items
are represented truthfully (for example “N more followed updates”) rather than
silently triggering geometry churn.
- Use the shared branded Steam header/card/theme vocabulary and semantic Widget
Theme resolver. No family-local theme cascade, raw QML colour authority, or
runtime material/effect surface.
- Each row owns a fixed artwork/text allocation appropriate to `wide`, `square`,
or `portrait`; headline line clamp, alignment, and explicit truncation policy
must leave a measured readable text rectangle. The optional reveal is only a
short-lived event-driven tooltip on an elided visible title, not a persistent
animation/cadence.
- Declare stable preferred **outer** dimensions for both `single_row` and
  `double_row` from the start. They are authored presentation variants, not
  content-count-derived sizes, and each must expose truthful preferred width and
  height to the ordinary host/predictor.
- Opt into the already-landed shared `content_extent` contract on **both axes in
  the first implementation**. This is not deferred polish. Horizontal and
  vertical side handles must reflow the retained card at constant uniform scale;
  corners and wheel must continue to use the one shared whole-card uniform
  transform. No Games You Follow code may add family-local resize persistence,
  a second geometry owner, a QML resize timer/debounce, or a private placement
  solver.
- Horizontal `content_extent` changes only the logical content width: artwork and
  text lanes reallocate inside the existing row count, headline/source metadata
  gain or lose measured readable width, and normal elision/truncation remains
  authoritative. It must not silently switch `single_row`/`double_row`, change
  source ranking, or alter the configured visible story count.
- Vertical `content_extent` changes only the logical content height: row height,
  internal spacing/padding and artwork crop/allocation may reflow within the
  selected `single_row` or `double_row` variant. It must not create additional
  source rows, mutate the persisted `view`, or turn accepted-item count into a
  geometry authority.
- Family-owned direct-axis readability floors are allowed only through the
  shared descriptor/session policy. G3 must measure and declare the minimum
  logical width/height needed for the selected row variant and artwork/text
  contract; do not hide a second clamp in QML or persist those floors as product
  Settings. The generic shared whole-card uniform floor still governs
  corner/wheel scaling.
- A side-reflowed card remains one retained presentation: subsequent
  corner/wheel resize uniformly scales the complete reflowed result, including
  branded header, artwork, text and interaction surfaces. Save/Cancel/re-entry
  must round-trip uniform scale and `content_extent` without compounding either.
- Shared Restore Size clears Games You Follow `content_extent` and returns to the
  active view variant's canonical authored outer size/shape while preserving
  current X/Y/display. It must not invoke stacking/auto-fit or learn its target
  from committed CUSTOM extent.
- Layout slots must round-trip the visible `view` (`single_row`/`double_row`),
  ordinary ON/OFF, uniform CUSTOM geometry and `content_extent` together, while
  source/cache/account state remains excluded. A slot load may therefore restore
  the same row variant and the same horizontal/vertical reflow that was visible
  when saved without creating another settings authority.
- Outside global CUSTOM, enter the normal stacking/autofit predictor with the
  active variant's exact preferred outer geometry. Global CUSTOM disables
  stacking for this card just as for every other ordinary widget. Cross-display
  edit transfer must preserve the logical extent/scale contract across DPRs via
  the existing session/owner path rather than pixel-copying a family-local box.

## 6. Settings, defaults, and migration

- Retain stable settings root `widgets.steam_progress` for v1 compatibility,
but change all new Settings labels to **Games You Follow**. Do not create a
second `widgets.games_you_follow` authority.
- The product follow list is source-owned by the G0-proved
  `GetGamesFollowed` route. Do not create a parallel Settings-authored follow
  list while that contract is valid; that would become a second semantic
  authority. Never store titles, source URLs, keys, or account identity in the
  Games You Follow settings payload.
- Required card settings: enabled; ordinary position/monitor; font family/size;
  view (`single_row`/`double_row`); text alignment (`left`/`center`/`right`);
  artwork shape (`wide` default, `square`, `portrait`); headline truncation
  threshold. Steam refresh/privacy/credentials and the followed-game set remain
  family/source-owned, not duplicated here.
- Bound and normalise every persisted enum/int at the settings/config seam.
Migration retains existing generic scaffold position/font/card-style fields,
sets all new fields to canonical defaults, and removes only caller-proven dead
mock fields. `core/settings/default_settings.py` remains the sole default
authority; regenerate snapshot/JSON/SST artifacts and update descriptor,
family/UI-bucket, preview, and defaults-authority tests in the same slice.
- Settings labels/tooltips must state that news is app-specific public source
material from the chosen follows, not a Steam-wide personalised feed.

## 7. Test and acceptance plan

### Deterministic/source gates

- [ ] Fixture-only G0 source/auth/privacy/URL-host/redirect/response-budget
coverage; prove excluded publisher/news-authed and scraping paths are absent.
- [ ] Follow-set validation/migration/default authority and no inference from
owned/recent games.
- [ ] Normalisation/dedupe/ranking with timestamp ties, missing fields, empty,
private, rate-limited, malformed, cache/stale and rejected URL states.
- [ ] Cache envelope/version/opaque-key behavior; failure never freshens cache;
stale-generation completion cannot replace an accepted revision.
- [ ] News-image-first then shape-matched app-art fallback, local-file-only model
  role, byte/host/signature validation, no article-page scraping, no all-item
  prefetch, and late completion fencing.

### Runtime and retained presentation gates

- [ ] Multi-display leases prove one owner/request cadence/cache result and no
work with zero effective consumers or when Settings opens.
- [ ] Consumer/family/member/dev-gate teardown proves last lease retirement and
surviving Steam sibling work remains alive.
- [ ] Stable model identity/no-op updates, single/double-row fixed preferred
  geometry, alignment/truncation/full-title affordance only when actually elided,
  and long/mixed Unicode headlines remain readable.
- [ ] QML contains no `Timer`, network URL, provider/service business object,
QWidget/QPainter fallback, or new accelerated surface; interaction signals carry
only index plus semantic action.
- [ ] Python action admission rejects stale index, unavailable art/article,
unapproved URL, and helper failure; Store/source routes use the established
diagnostic versus normal-screensaver behavior.
- [ ] Predictor/descriptor/normalisation tests prove normal stacking, global
  CUSTOM dormancy, horizontal-only `content_extent`, vertical-only
  `content_extent`, corner/wheel whole-card uniform scaling, direct-axis logical
  floors, Restore Size, stale Save/Cancel/re-entry replay, slot replay of
  `single_row`/`double_row` + extent state, and one truthful overflow summary.
- [ ] Geometry integration covers both row variants at authored size, after
  horizontal-only reflow, after vertical-only reflow, after combined side
  reflow followed by corner/wheel scale, and after cross-display/DPR transfer;
  no path may compound scale, mutate source settings, or create a family-local
  geometry payload.

### Physical acceptance

- [ ] Real connected-account or approved local-follow-list pass: correctly
  scoped follows, stale/private/failure copy, one- and two-row readability,
  long headlines, all alignments, truncation/full-title behavior, news-image-first
  selection, all shapes/app-art fallback, and Store/article click routes.
- [ ] Installed geometry pass on both row variants: drag left/right and top/bottom
  side handles through compact and expanded extents, then corner/wheel-scale the
  reflowed card, Save/Cancel/re-enter, Restore Size, load a saved layout slot,
  and move between mixed-DPI displays. Require stable X/Y/display ownership,
  no row-mode mutation, no scale compounding and no clipped interaction lanes.
- [ ] Installed two-display/DPI/theme/CUSTOM/stacking soak: one owner, no
  refresh multiplication, bounded task/cache/image count, clean last-card/family
  retirement, and helper fail-closed behavior.
- [ ] Compare enabled versus disabled Steam family under a realistic background;
do not close on average FPS alone. Reject added frame-cadence work, repeated
unchanged model mutation, unbounded follow scans, or source/image request fanout.

## 8. Phases and removal boundary

### G0 — feasibility and rollback

- [ ] Complete every §2 spike and record the exact selected follow authority,
  safe article/news-image policy, and measured request budget in
  `Steam_Data_Feasibility.md`.
- [ ] Pin rollback and preserve fixture/default/migration inputs.

### G1 — neutral source/cache

- [ ] Add bounded preparation, feature-owned cache schema, normalised immutable
snapshot, and deterministic fixture gates with no UI/runtime.

### G2 — shared owner and dormancy

- [ ] Add the single generation-scoped lease owner, cache-first delivery,
canonical cadence, source/action/artwork fencing, and cardinality tests.

### G3 — retained presentation and actions

- [ ] Add one retained Quick model/QML card, both row variants, semantic
  Store/article signals, and no business/network exposure in QML.
- [ ] Implement both-axis shared `content_extent` consumption in that first
  retained card: measured horizontal/vertical reflow, family logical side floors,
  corner/wheel whole-card scale, Restore Size, and no local geometry owner.

### G4 — settings, normalisation, and admission

- [ ] Add lazy transactional Settings/default/migration/descriptor/predictor
  work, including both content-extent axes, active-view preferred geometry,
  layout-slot view/extent replay, ordinary/CUSTOM proof, mixed-DPI edit transfer,
  and dev-gated preview admission.

### G5 — acceptance and public-admission decision

- [ ] Complete focused automated and physical cells. Only then decide whether
  `--devsteam` can retire for this member; public Friend Pulse remains unaffected.

Until G5, all new substantive files should be feature-named and removable as one
bounded slice: Games You Follow preparation/cache/runtime/presentation/QML/tests
and the caller-proven `steam_progress` scaffold replacement. Do not retain a
parallel old presenter, compatibility provider, or permanent dead scaffold after
the replacement is accepted.
