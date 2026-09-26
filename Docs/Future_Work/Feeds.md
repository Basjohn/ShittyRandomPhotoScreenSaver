# FEEDS | Expansion and acceptance plan

**Status:** active. `Current_Plan.md` owns immediate sequencing. `Docs/Reference/Feeds.md` owns what is already implemented. This file contains only remaining family expansion, acceptance and deferred product work.

## Product boundary

FEEDS is one bounded ordinary-widget family, not a runtime widget factory. Four CUSTOM identities are reserved:

- `feeds_custom_1`
- `feeds_custom_2`
- `feeds_custom_3`
- `feeds_custom_4`

All four CUSTOM slots are admitted to runtime through one path. A user-visible custom name is presentation state, never persistence, registry or cache identity. Four CUSTOM slots remain the product ceiling unless a later measured design explicitly changes it. Disabled/unconfigured slots are dormant.

Five NEWS identities are reserved for later provider-backed categories:

- `feeds_news_world`
- `feeds_news_us`
- `feeds_news_politics`
- `feeds_news_gaming`
- `feeds_news_tech`

Their presence in research/catalog code is not a shipping promise. No NEWS identity enters Settings/runtime until its provider gate below is satisfied.

## Expansion guardrails

These rules apply to every remaining FEEDS slice:

- Preserve endpoint-isolated, non-expiring last-good state. Transport/parser/empty-result/provider failure must not erase an accepted snapshot.
- Preserve strict CUSTOM endpoint identity. Reconfiguring a slot from endpoint A to endpoint B may never display A while B warms or fails.
- Feed validity remains image-independent. Artwork is optional and locally admitted; no remote QML image URLs and no article-page scraping merely to decorate cards.
- No per-widget poller, QML timer, second downloader, second Edit owner or Settings I/O on refresh/resize/hover/render cadence.
- Same-endpoint active consumers share source/cache/due work where privacy/cache identity permits it. Retiring one lease must recompute cadence rather than leave a permanently faster source.
- Identical normalized/presentation revisions do not republish retained models.
- External actions stay capability-specific. HTTP/S is the only currently admitted FEEDS foreground action; magnet and managed `.torrent` actions remain separate future capabilities.
- Feed URLs may contain private query tokens. Diagnostics/logs redact query and fragment data.
- Cache maintenance deletes cache/artwork only, never CUSTOM names/URLs or credential/configuration state.

Before multiplying sources or identities, re-check **durability, content adaptability and performance neutrality**. A red pillar blocks expansion.

## Custom 1 closure gate

Closed 2026-09-24: the Edit transaction, Show Feed Subtitle, offline last-good restart and in-flight disable/replace were physically accepted (see `Current_Plan.md`). Do not reopen accepted artwork reflow, source-link routing, click-highlight or subtitle behaviour without a reproduced defect.

## Custom 2–4 activation

Admitted 2026-09-26 through the **same** descriptor/runtime/source/QML/Edit path as Custom 1: a generated runtime descriptor per slot, one `FeedFamilyAdapter`, one retained presentation and a slot-parameterized Settings builder. Multi-source behaviour is covered by `tests/test_feed_runtime.py` (independent endpoints, retire-A-keeps-B, shared-endpoint dedup, cancelled work never publishes), `tests/test_feed_artwork_multisource.py` (eviction protection across sources) and `tests/test_feed_custom_slots.py` (admission, ordinals, Settings round-trip). Same-initial names carry a deterministic monogram ordinal through the existing cached vector path.

- [~] Physical: two or more slots live on the saver at once (different endpoints, then the same endpoint in two slots); Settings round-trip of every slot.

## NEWS provider probation

NEWS is a technical-provider qualification problem, not an editorial-ranking feature.

- [ ] Run repeated native `tools/feed_probe.py` probation on Windows for each candidate over multiple sessions/days. A single successful HTTP response is insufficient evidence.
- [ ] Require at least **two independent viable no-signup providers per category** before that category is admitted.
- [ ] Reject providers that require API keys, account sign-in, third-party RSS reconstruction, article scraping, browser automation or credentials.
- [ ] Record stable provider ID, display name, category, endpoint, homepage/attribution and terms-reference metadata before promotion.
- [ ] Convert malformed/edge documents found during probation into frozen deterministic parser fixtures.
- [ ] Keep Settings source checks explicit/asynchronous. Opening Settings must not cause a provider-validation storm.
- [ ] Under a stable provider ID, endpoint replacement may retain the previous last-good snapshot while the replacement is unhealthy, but old ETag/Last-Modified values must never be sent to the new endpoint.

Technical health labels describe reachability/parser viability only. SRPSS does not score political slant, editorial quality or story importance.

## NEWS projection

- [ ] Admit the five stable NEWS widget identities only after their provider-category gates pass.
- [ ] Merge selected providers chronologically by publication time while retaining provider attribution.
- [ ] Allow exact feed identity/canonical-URL dedup only. Do not use semantic/fuzzy political-story suppression or infer equivalence between outlets' coverage.
- [ ] One failed provider retains that provider's last-good state and must not blank healthy providers.
- [ ] Reuse the shared FEEDS transport/parser/cache/runtime/presentation modes and local-artwork rules. Do not build five bespoke NEWS engines.

## Feed formats

Implemented (see `Docs/Reference/Feeds.md`): RSS, Atom, JSON Feed 1.x, JF2 and IndieWeb h-feed. Evaluated on 2026-09-24 and deliberately not built, each with the condition that would reopen it:

- ActivityStreams 2.0 / ActivityPub outboxes: Mastodon, Lemmy, PeerTube and Pixelfed all publish RSS that discovery already finds; outboxes need paging and often signed fetches. Reopen if a fediverse platform drops RSS.
- AT Protocol (Bluesky): profiles publish RSS. Reopen if that stops.
- Nostr: not HTTP; out of scope for a bounded HTTP feed source.
- OPML: a list of feeds, not a feed. A possible later "import subscriptions" convenience, not a format.
- WebSub: push notification, not a format; the pull cadence does not need it.
- Microformats1 hAtom: see the Reference note on why it is not read.

## Torrent and magnet actions

- [ ] Keep authored title first. A missing title falls back to magnet `dn=`, then the entry's own text, then enclosure filename or URL-derived text (implemented in `entry_title_and_summary`); machine-ish cleanup applies only to URL-derived fallback text.
- [ ] Add a separate allowlisted `open_magnet` capability with bounded syntax validation. Do not broaden HTTP/S open into generic URI execution.
- [ ] Fetch `.torrent` enclosures only after explicit user action, with strict response-size/content checks into an SRPSS-owned managed action-cache directory.
- [ ] Add a separate `open_torrent_file` capability restricted to validated `.torrent` files in that managed directory. Never add arbitrary-file opening.
- [ ] Retire these actions with their owning generation and disable them during CUSTOM input capture.
- [ ] Require a physical Windows gate with the default torrent handler before considering the feature accepted.

## Legacy wallpaper RSS consolidation

The wallpaper RSS path already uses the shared bounded document transport. Further consolidation is optional and must preserve wallpaper behavior rather than force code sharing.

- [x] Audited and removed the dormant `RSSWorker` process (2026-09-25): it was registered but never started, and wallpaper feeds acquire in-process on the shared core (`Docs/Reference/Feeds.md` § Wallpaper feeds).
- [ ] Reuse normalization/image-candidate primitives only where it makes the wallpaper engine simpler without merging its image-primary cache/scheduling authority into FEEDS last-good item state.
- [ ] Prove wallpaper parity before changing its remaining parser/cache/scheduler boundaries.

## Performance and lifecycle acceptance

- [ ] Heavy transition + active Visualizer + FEEDS refresh must show no meaningful regression to presentation freshness, Settings entry or teardown relative to the accepted runtime baseline.
- [ ] Multi-source cache/artwork maintenance remains bounded by count/bytes and source generation; no unbounded history or per-card maintenance loop.
- [ ] GUI admission remains bounded/immutable and occurs only for a changed accepted revision or a user-visible status transition. I/O and parsing remain off GUI.
- [ ] Final consumer retirement cancels due work, fences queued/in-flight completion and releases endpoint transport after its worker exits without disturbing unrelated active sources.
