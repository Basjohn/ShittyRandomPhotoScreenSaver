# FEEDS | Live decomposition and acceptance plan

**Status:** active implementation track. This document is the durable decomposition/checklist for the Feeds family; it is not a changelog. `Current_Plan.md` controls immediate sequencing. `Docs/Reference/Feeds.md` records contracts that have already become architecture.

## Product boundary

FEEDS is one bounded ordinary-widget family with four fixed CUSTOM identities and, after provider probation, five fixed NEWS identities. It is not an arbitrary runtime widget factory.

Stable CUSTOM widget IDs:

- `feeds_custom_1`
- `feeds_custom_2`
- `feeds_custom_3`
- `feeds_custom_4`

Reserved NEWS identities once their category has passed native provider probation:

- `feeds_news_world`
- `feeds_news_us`
- `feeds_news_politics`
- `feeds_news_gaming`
- `feeds_news_tech`

A CUSTOM slot may be renamed freely, but the display name is never its persistence identity. Four slots is the product ceiling unless a later measured design explicitly changes it. Disabled/unconfigured slots are dormant.

## Non-negotiable durability contract

- Cache first. A valid last-good snapshot remains renderable across network failure, parser failure, provider outage, process restart and ordinary backoff. A failed/partial/empty replacement never destroys established state.
- CUSTOM endpoint identity is strict. Changing Custom 1 from feed A to feed B can never display feed A's cache while B is warming or failing.
- Built-in NEWS provider identity is stable and separate from today's endpoint. An official URL may be replaced after validation without changing the widget/provider identity; old conditional validators are never sent to a different endpoint.
- Feed validity does not depend on an image. Title/action/text/date are primary data; feed-advertised images are optional presentation candidates.
- No article-page scraping in the first product architecture. Do not add OpenGraph/HTML fetches merely to decorate cards. That multiplies traffic, bot blocking, parser surface and cache churn.
- No live-network pytest. Deterministic tests use frozen bytes/records. Real publisher reachability is measured by the native probation tool through the same production transport/parser.
- No per-widget pollers or QML timers. Later runtime refresh must have one shared source/coordinator owner per active generation/family, with cancellable due work and source deduplication.
- No data-driven GUI churn. A refresh with an identical normalized document does not republish presentation. Resize/edit/hover never perform network or Settings I/O.
- No direct remote QML `Image.source`. Future artwork warming validates/caches locally before presentation.
- No generic external-open helper. HTTP/S, magnet and managed `.torrent` actions are separate allowlisted capabilities.
- Feed URLs may contain private query tokens. Logs and diagnostics must redact query/fragment data.
- Configuration is durable product state and is never deleted by cache maintenance. Cache clearing removes last-good/feed artwork only.

## Recurring three-pillar acceptance audit

Every few meaningful FEEDS slices, and always before multiplying providers/instances, re-run this audit. A red pillar blocks expansion.

### Durability

- Last-good survives transport, parser, empty-document, cache-write and provider failures.
- Cache/config identities cannot cross-contaminate after URL/provider changes.
- Async callbacks are generation/lifetime fenced; Settings probes must verify their Qt owner still exists.
- Persisted backoff/conditional validators cannot become restart loops or be sent to the wrong endpoint.
- Cache corruption is quarantined, never partially admitted.

### User adaptability

- User-authored name/URL survive Reset and are independent of visual defaults.
- A syntactically valid URL can be saved even when the network is temporarily unavailable.
- Display modes degrade coherently when optional media is missing.
- Card geometry never creates half-visible rows/tiles or hidden wheel/scroll ownership that conflicts with Edit. Item limits are maxima bounded by actual presentation capacity.
- A control is not exposed before it has a working runtime consequence.

### Performance neutrality

- Inactive/unconfigured family means no coordinator, feed fetch, parser work, QML timer or remote image work.
- Fresh-cache startup does not wake HTTP/session machinery until refresh is actually due.
- Same endpoint across cards/displays shares one source/cache/due transaction.
- Cadence is derived from currently active leases and cannot remain permanently ratcheted by a retired fast consumer.
- Identical normalized/presentation revisions do not republish retained models.
- Resize/Edit/hover/Settings typing perform no network/cache writes.

### Audit 1 — F2 CUSTOM 1 candidate

- [x] **Durability:** empty successful responses cannot replace last-good; strict cache shapes/quarantine remain; TEST FEED late callback is weak + `Shiboken.isValid()` fenced; probe/tool share one production viability seam; the product-action boundary independently rejects non-HTTP/S targets instead of trusting QML admission alone.
- [x] **User adaptability:** F2 removed the former unwired image toggle; F3 now exposes the functional local-image preference. Max Items caps instead of clipping through card bounds; only whole List/Compact rows and Grid cells that fit are painted; responsive text-grid columns and explicit `+N MORE` overflow; no internal scrolling/wheel owner.
- [x] **Performance neutrality:** endpoint acquisition shared across future slots/displays; active cadence recomputes after lease retirement; idle source transport is released; cache-only startup avoids importing `requests`/`feedparser` or constructing HTTP transport/session; reactivation reuses retained in-memory last-good without rereading disk merely to recreate source state; no QML network/timer.
- [~] Custom 1 has native and partial physical F2/F3 evidence (real NASA source, List/Grid rendering, Winlogon click handoff and diagnostic sidecar). Final current-tree artwork identity, independent X/Y reflow, offline persistence and retirement checks remain the acceptance gate before multiplying CUSTOM sources.


## F0 | Native probation and deterministic corpus

**Goal:** prove the transport/parser and candidate-source assumptions before NEWS becomes product UI.

- [x] Add a native `tools/feed_probe.py` that uses the exact production bounded transport and parser.
- [x] Report RSS/Atom format, bounded item count, actionable-link coverage, image coverage, response bytes, redirect endpoint, validator presence, newest timestamp and latency.
- [x] Keep the research candidate catalog inert; its presence is not a shipping promise.
- [x] Establish current official candidates for World, U.S., Politics, Tech and Gaming without API keys/accounts.
- [x] Keep live reachability outside pytest.
- [ ] Run repeated native probation on Windows for every NEWS candidate and retain dated evidence across multiple sessions/days rather than accepting a single lucky HTTP 200.
- [ ] Require **at least two independent viable providers per NEWS category** before that category is admitted to product settings/runtime.
- [ ] Reject sources that require API keys, sign-up, third-party RSS reconstruction, article scraping, browser automation or credentials.
- [ ] Record provider attribution/homepage/terms-reference metadata before promotion into a shipped catalog.
- [ ] Add frozen malformed/edge fixtures encountered during native probation to deterministic parser tests so real-world weirdness becomes permanent coverage.

A provider's technical health is not a ranking of its journalism. For Politics in particular, SRPSS presents selected source material chronologically and does not assign ideological scores, quality rankings or inferred equivalence between stories.

## F1 | Shared bounded feed core

**Goal:** one parser/transport/cache foundation that CUSTOM and NEWS can both consume without Qt ownership.

- [x] Bounded HTTP/S transport with explicit connect/read timeouts, redirect ceiling, decompressed byte ceiling and cancellation checks.
- [x] Conditional GET via ETag/Last-Modified.
- [x] Transport returns final redirect URL so relative feed content resolves against what was actually fetched.
- [x] RSS/Atom parsing from bytes only; parser never owns network I/O.
- [x] Normalize valid image-less entries instead of dropping them.
- [x] Normalize Media RSS, image enclosures and bounded HTML image candidates without downloading them.
- [x] Normalize HTTP/S and magnet action targets; retain non-image enclosures for later controlled actions.
- [x] Resolve relative home/article/media/enclosure URLs against the final feed endpoint.
- [x] Bounded plain-text sanitation for summary/author/title.
- [x] Stable item identity using explicit feed ID/GUID first, canonical action URL second, bounded fallback identity last.
- [x] Human-readable fallback title derivation, including magnet `dn=` when an item supplies no title.
- [x] Atomic versioned last-good cache with corruption quarantine and strict read-shape limits.
- [x] Unique temp-file cache writes so accidental same-process overlap cannot corrupt a shared target.
- [x] Cache-write failure is non-fatal to a valid in-memory generation.
- [x] Persist refresh health/backoff so repeated failures cannot become restart/churn loops.
- [x] Strict CUSTOM cache isolation by endpoint fingerprint.
- [x] Stable built-in-provider endpoint-migration seam with validators fenced to matching endpoints.
- [x] Canonical dormant defaults for all four CUSTOM slots; user URL/name survive global Reset while styling/view controls remain resettable.
- [x] Add Feeds to explicit cache-maintenance allowlist without including settings/credentials.
- [x] Keep package-root imports lightweight so mere schema/role discovery does not wake requests/feedparser.
- [x] Migrate ancient wallpaper RSS document retrieval onto the bounded shared transport, fixing its historical unbounded `feedparser.parse(url)` network path without merging its scheduler/cache into FEEDS.
- [x] Pure presentation projection supports List, Grid and Compact modes with no Qt dependency.
- [ ] Execute deterministic feed-core tests in the native dependency environment (`feedparser`, PySide test harness present) and promote every real failure into the contract rather than weakening fixtures.

## F2 | CUSTOM 1 complete vertical slice

**Goal:** prove one useful widget all the way from Settings to runtime before multiplying surfaces.

- [x] Register `feeds` family dormantly and expose only Custom 1 behind canonical family activation.
- [x] Settings: enabled, name, URL, List/Grid/Compact selector, **Max Items**, refresh interval and normal card/theme/monitor/position/authored-geometry controls. The F3 locally cached article-image preference is available only after the bounded warmer is wired to the current source owner.
- [x] Settings: asynchronous explicit **TEST FEED** action. Never network-fetch on every keystroke or merely opening Settings.
- [x] TEST FEED uses the exact production probe seam and reports parser type, valid items, actionable count, image coverage and newest-item evidence. Network failure does not forbid saving a syntactically valid URL.
- [x] TEST FEED callback is weak-owner and Qt-validity fenced so runtime/Settings replacement cannot touch a destroyed tab.
- [x] Cache-first runtime admission: valid cached snapshot paints first; refresh is asynchronous only when due. Cache-only startup constructs no HTTP session.
- [x] One generation-shared due owner and endpoint-deduplicated source state; no per-card timer/poller.
- [x] One retained Qt Quick model/host, no per-entry QObject tree, no QML network timer and no remote QML image source.
- [x] Text List/Grid/Compact presentations are usable before artwork warming. Max Items is a presentation ceiling; card geometry exposes only whole rows/cells that fit and reports overflow instead of clipping. Grid columns adapt to available width.
- [x] Clicking an HTTP/S entry uses the existing foreground helper/action seam, not QML `Qt.openUrlExternally`.
- [x] Disable/retire source contracts detach presentation callbacks, recompute active cadence and release idle transport state.
- [~] Runtime/Settings/runtime preservation and last-good cache independence implemented; native physical round-trip remains open.
- [~] Dormancy implemented by registration/source contracts; physical no-work validation remains open.
- [~] Failure/malformed/timeout retention has deterministic coverage; physical last-good/backoff validation remains open.


## F3 | Presentation expansion + all CUSTOM slots

- [~] Per-endpoint cancellation/pruning is implemented in the shared owner: the final active lease cancels queued/streaming work, its completion cannot publish or convert cancellation into provider backoff, and other active endpoints remain unaffected. A same-endpoint surviving lease keeps its source alive. The operator reported **45 passed in 2.06s** for the earlier changed-tree native gate. Before Custom 2–4 activate, physically/native-test simultaneous A/B endpoints, dormancy, reactivation and lifecycle/eviction fencing rather than adding another cancellation system.
- [x] Retain the pure all-or-none image-generation helper only for consumers whose product contract genuinely requires it. FEEDS Grid no longer uses it: one missing optional article image must not globally suppress unrelated valid local artwork.
- [x] Keep Steam Games You Follow separate: its image-optional mixed news requires per-game validated artwork and one stable image rail/placeholder, not an all-or-none gate that suppresses every good image when one article has no artwork. Share only content-neutral primitives with equivalent semantics.
- [~] `project_feed` keeps local artwork attached to each stable story identity while retained QML alone decides geometry visibility. Missing-art Grid cards use their authored text-only cell; available local images remain visible. A fixed image-capable Grid cell height prevents capacity/readiness oscillation, and resize no longer calls back into Python or resets rows. Native mixed-image/large/small-card acceptance remains open.
- [x] Compact Headlines is a deliberately text-only dense view with no animation or ticker.
- [~] The worker-only `FeedArtworkCache` and vetted, DNS-pinned redirect-validated `artwork_transport` are wired into the existing Custom 1 source-owner IO lane. One event-admitted image batch may accept at most four newly network-owned story images, try at most eight candidates and shares one eight-second deadline; List and Grid admit local artwork per story while image-less cards collapse to their authored text-only presentation; Compact remains text-only. Duplicate identity strips query/fragment for comparison, and normalized-content hashing rejects distinct URLs that resolve to the same generic hero. Every candidate is checked locally before network work, so a cached fallback survives a failed preferred source. Feed-contained metadata discovery includes Media RSS/enclosures, `img`/`source`, lazy attributes and `srcset`; article-page scraping remains absent. On-write rotation protects current source image URIs. Current-tree physical identity/offline/reflow acceptance and concurrent multi-source eviction fencing remain required before Custom 2–4. No new image scheduler, QML network load or render-time media validation.
- [ ] A complete current image generation may remain displayed while a replacement generation warms. Do not progressively tear holes into the retained presentation.
- [ ] Enable Custom 2/3/4 using the same codepath/registry/component; do not clone four providers or four QML implementations.
- [~] Custom 1 runtime monogram now uses the retained QPainter vector-icon approach: first alphanumeric grapheme is drawn from explicit wireframe segments once per semantic config and supplied as an immutable local image, with no emoji/font-glyph/QML-Canvas dependency. Deterministic small collision ordinals (e.g. `N`, `N²`) remain a required part of the later Custom 2–4 activation because only one slot is currently admitted.
- [~] Custom 1 uses the shared ordinary Edit contract with independent horizontal/vertical `content_extent` reflow (320×180 logical floor), the ordinary outer scale intent, and stable shared child roles (`header`, `refresh`, `articles`, `artwork`, `overflow`). Volatile article rows never become persisted child IDs. One repeated `artwork` role supplies freeform X/Y/width/height to all admitted images; Grid text reflows into the best usable side/above/below region and fits to the remaining space. The representative Edit proxy targets real admitted artwork even when the first feed row has no image. Layout derives from the actual padded authored card surface so uniform parent scale cannot create an unreachable lower band; a Grid that fills its row capacity consumes the remaining body height. The common editor owns detach/reset/undo/lock/snapping/persistence/containment; no feed-local collision, undo, persistence or resize-I/O machinery exists. Current-tree physical parent/child resize + save/reopen acceptance remains open; Custom 2–4 must reuse the same descriptor/component contract.
- [~] Custom 1 header uses shared `BrandedHeader` rather than a FEEDS-local header. It projects the established semantic header colours, with bounded publisher metadata as a small separate optional subtitle below the pill (default on per custom slot). Header left/right alignment is the widget-wide semantic orientation intent, mirroring Grid order, List artwork/text/age rails, refresh and overflow together without mirroring image pixels. Shared semantic-corner anchoring remains under the common child geometry contract. Native/physical flip, Reset, undo/lock and save/reopen acceptance remains open.

## F4 | Torrent/magnet actions

- [ ] Keep authored feed title first. If missing, prefer magnet `dn=`, then enclosure filename, then URL slug. Only derived machine-ish names receive separator cleanup; do not mutilate an authored scene-release title.
- [ ] Add an explicit helper `open_magnet` capability. Validate scheme and bounded magnet syntax; never broaden the existing HTTP/S action into arbitrary URI execution.
- [ ] `.torrent` enclosures are fetched only on explicit click, with strict response-size/content validation into an SRPSS-owned managed action-cache directory.
- [ ] Add helper `open_torrent_file` that accepts only `.torrent` files inside that exact managed directory. Never add a generic arbitrary-file opener.
- [ ] All actions are disabled during CUSTOM input capture and retire with the owning generation.
- [ ] Physical Windows gate with the default torrent handler before calling torrent actions accepted.

## N0 | NEWS provider promotion

- [ ] Promote only provider IDs with repeated native probation evidence; raw endpoint strings live in replaceable provider descriptors.
- [ ] Category ships only when two independent providers meet the current technical floor.
- [ ] Provider descriptor records stable ID, display name, category, endpoint, homepage/attribution and terms-reference metadata.
- [ ] Settings exposes source selection and cached health (`HEALTHY`, `STALE`, `BACKOFF`, `FAILED`) without implying editorial quality.
- [ ] Explicit **CHECK SOURCES** performs asynchronous validation. Merely opening Settings does not cause a network storm.
- [ ] Provider endpoint replacement retains last-good state under stable provider ID until the replacement validates; never send old ETag/Last-Modified to a new endpoint.

## N1 | NEWS projection

- [ ] Add five stable NEWS widget identities only after N0 category floors pass.
- [ ] Multiple selected providers merge chronologically using publication time while retaining provider attribution.
- [ ] Exact feed identity/canonical-URL dedup is allowed. Do not use semantic/fuzzy political-story suppression or pretend different outlets' coverage is interchangeable.
- [ ] Failure of one provider retains that provider's last-good state and must not blank healthy providers.
- [ ] Same shared coordinator, parser, cache and presentation modes as CUSTOM; no five bespoke NEWS engines.
- [ ] Image coherence and local-cache-only rules remain identical to CUSTOM.

## L0 | Legacy wallpaper RSS consolidation

- [x] Replace direct `feedparser.parse(url)` retrieval with the bounded shared HTTP transport.
- [ ] Audit the apparently dormant process `RSSWorker` separately before removal or reuse. Registration/tests alone do not prove runtime ownership.
- [ ] Reuse shared normalization/image-candidate helpers where this makes the wallpaper engine simpler, but keep wallpaper-specific image-primary cache/scheduling separate from FEEDS last-good item snapshots.
- [ ] Do not change current wallpaper feed behavior merely to force code sharing; prove parity first.

## Performance / lifecycle acceptance

- [ ] One shared FeedRefreshCoordinator only after a runtime consumer exists. It sleeps until next due work; it is not a periodic GUI timer.
- [ ] Deduplicate identical active source endpoints/jobs within a generation where privacy/cache identity allows it.
- [ ] I/O and parsing remain off GUI. GUI admission is immutable/bounded and only occurs on changed normalized revision or explicit status transition that must be visible.
- [ ] No Settings writes during refresh, resize, image warming, hover or render.
- [~] Final consumer retirement cancels due work, fences queued/in-flight completion and releases endpoint transport safely after its worker exits; verify native streaming cancellation, reactivation, unrelated endpoints and last-good preservation before multi-CUSTOM admission.
- [ ] Heavy transition + active Visualizer + feed refresh acceptance must show no meaningful regression to presentation freshness, Settings entry or teardown.
- [ ] Cache/artwork maintenance is bounded by count/bytes; no unbounded history accumulation.
