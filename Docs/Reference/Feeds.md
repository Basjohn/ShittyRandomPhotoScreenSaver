# Feeds | Durable architecture contract

This is the current architectural contract for the shared Feed foundation. Product/runtime surfaces not yet implemented remain in `Docs/Future_Work/Feeds.md` and must not be inferred as already shipped.

## Identity and authority

FEEDS is one bounded widget family. Four CUSTOM slots have stable IDs (`feeds_custom_1` through `feeds_custom_4`) and canonical dormant defaults. A configured name such as `Nyaa` is presentation only and never becomes a settings key, cache identity or runtime registry identity. Future NEWS widgets/providers follow the same rule: stable category/provider IDs are independent of the current endpoint URL.

`core.settings.default_settings.DEFAULT_SETTINGS` remains the product-default authority. `CustomFeedConfig` repairs missing/malformed headless values from that canonical root rather than embedding a parallel authored-default table. User-authored CUSTOM `feed_url` and `name` are preserved by global Reset; ordinary display/theme tuning remains resettable.

## Layer boundaries

`core/feeds/transport.py` owns one bounded HTTP transaction. `core/feeds/parser.py` owns RSS/Atom bytes-to-model normalization. `core/feeds/cache.py` owns the durable versioned last-good record. `core/feeds/source.py` owns one cache-first refresh transaction and persisted backoff decision. `core/feeds/projection.py` owns pure snapshot-to-presentation policy. `core/feeds/probe.py` is the one explicit viability seam used by Settings TEST FEED and the operator probation tool. None of those core layers owns Qt objects, QML, periodic timers or Settings UI.

`widgets/feed_runtime.py` owns generation-scoped scheduling/source leases. `rendering/quick/widgets/feeds.py` owns retained presentation projection/action admission; `FeedPresentation.qml` is presentation only. Its `ShadowedText` instances use the component's supported `wrap` boolean instead of the native `Text.wrapMode` property; a native `QQmlComponent` compile gate is mandatory for any QML property changes because an invalid custom property can prevent the *entire screensaver engine* from initializing. The package root intentionally has no eager parser/network imports. Importing Feed configuration/source in a clean interpreter does not import `requests` or `feedparser`. Cache-only `FeedSource` admission also keeps parser and HTTP transport construction lazy, so a fresh last-good snapshot can paint without creating a network session.

## Transport

- HTTP/S only for feed documents; malformed/non-network endpoints are rejected before I/O.
- Explicit connect/read timeouts, redirect ceiling and decompressed response byte ceiling.
- Streaming cancellation checks allow later runtime retirement to stop bounded work.
- Conditional `If-None-Match` / `If-Modified-Since` is sent only when the cached endpoint fingerprint still matches the current endpoint.
- Final redirect URL is retained and becomes the base for relative item/home/media/enclosure URLs.
- Feed query strings/fragments may contain private tokens. Runtime/tool logging uses redacted scheme/host/path form.
- `feedparser` receives bytes; it is never allowed to perform production network I/O itself.

The legacy wallpaper RSS downloader now uses this bounded transport for its document fetch. Its existing image-primary parser/cache/scheduler remain separate until an explicit parity-preserving consolidation slice.

## Normalized document

A normalized item contains stable identity, title, optional action URL, bounded plain-text summary/author, optional publication time, zero or more feed-advertised image candidates and zero or more non-image enclosures. No image is required for validity.

Identity precedence is explicit feed ID/GUID, then action URL, then a bounded title/time fallback. Action targets may currently normalize HTTP, HTTPS or magnet schemes, but later runtime launch capability remains separately allowlisted. Feed-advertised image candidates accept only HTTP/S. Relative links are resolved against the final feed endpoint.

Title sanitation preserves authored titles. Only a missing title invokes derivation from magnet `dn=`, enclosure/URL-like path information or hostname; machine-like separators are cleaned only on this derived fallback path.

## Last-good and health state

Every cache record contains logical source ID, endpoint fingerprint, optional immutable snapshot, persisted health, ETag/Last-Modified and schema version. Writes are atomic and use unique temporary files; malformed/oversized cache input is rejected and quarantined instead of admitted into runtime state.

A transport/parse/empty-feed failure updates health/backoff but retains the previous valid snapshot. A 304 refresh retains the exact document and marks the check successful. A storage-write failure never converts a valid in-memory generation into a source failure. Persisted failure backoff prevents restart/retry churn.

CUSTOM cache keys include endpoint fingerprint. URL replacement therefore has no path that can render the previous endpoint's snapshot. Future built-in providers may opt into endpoint migration under a stable provider cache key: an old snapshot may remain visible while a replacement official endpoint is failing, but old validators are fenced off and success advances the stored endpoint fingerprint.

## Presentation and images

`project_feed()` is pure and receives only a snapshot, display mode, limits and optionally already-validated local artwork sources. It never downloads or exposes remote URLs as render sources. Feed image URLs are carried only as candidates for a later artwork warmer.

List permits sparse optional thumbnails because each row can collapse its image lane independently. Compact is text-only. Grid is generation-coherent: if every visible row does not have a validated local artwork source, every visible grid row receives an empty image source and the generation uses a coherent text-grid presentation. When the visible set is complete, all images may appear together.

The all-or-none image helper remains available for FEEDS Grid, whose visual policy requires complete image generations. Games You Follow is a separate Steam consumer with image-optional stories: its source admits a bounded, validated set of per-game local assets in one retained snapshot, and its card uses a consistent image rail/placeholder when only some stories have artwork. Do not merge feed and Steam scheduling, cache authority or image admission merely because they share a media-readiness concern.

F2 presentation treats configured item count as a **maximum**. The retained card budgets a stable footer, paints only complete List/Compact rows or Grid cells that fit the current geometry, reports hidden rows as `+N MORE`, and adapts text-grid column count to available width. It deliberately does not own a `ListView`, `GridView`, `WheelHandler` or internal scroll position, preserving Edit-mode wheel/resize authority.

## Cache maintenance

The Feeds cache is explicit under the canonical application cache root (`cache/feeds`). User-facing cache maintenance may clear this last-good data; it does not clear CUSTOM URLs/names or any settings/credential material. Feed cache records are bounded by schema and file size. A future image cache requires its own count/byte budget and local-file presentation contract.

## NEWS durability rule

`core/feeds/news_candidates.py` is a research/probation catalog only. It is not product authority and importing it does not enable a NEWS widget. A category cannot be promoted until at least two independent no-signup providers have repeatedly passed the native `tools/feed_probe.py` path. Provider health describes technical reachability/parser viability only; it is not an editorial score.

The shipped architecture must tolerate endpoint death by changing the provider descriptor, not by changing the user's widget identity. Third-party RSS recreation services, API-key sources and page scrapers are outside the intended durable baseline.

## Runtime ownership

F2 uses one `_FeedFamilyOwner` per active runtime generation (or helper-manager fallback in isolated tests). Retained cards hold lightweight leases. The owner keeps one earliest-due deadline across active sources and deduplicates CUSTOM acquisition by endpoint fingerprint, so the same feed used on multiple displays or future CUSTOM slots shares last-good state and network cadence while each card keeps independent presentation settings.

Cadence is projected from **currently active** leases; retiring a short fast lease cannot permanently ratchet the shared source. An idle source releases its HTTP transport state while retaining the immutable accepted result. Reactivation before the next due time reuses that result without rereading disk merely to recreate source state. Cache-only admission is first; a fresh cache schedules the future due deadline without importing/constructing the HTTP stack, while an empty cache proceeds to one bounded refresh. Persisted backoff owns subsequent failure timing.

F2 browser actions remain HTTP/S-only at both presentation admission and the presentation-neutral product-action boundary; later magnet/torrent capabilities require separate allowlisted actions.

Worker callbacks are tagged/fenced to the runtime generation and presentation consumers are weakly attached. Presentation retirement stops its lease and detaches the callback; the runtime-service manager remains final lifetime authority. QML owns no timer, network operation or remote image source.

F2 admits only `feeds_custom_1`. The remaining fixed CUSTOM IDs and all NEWS IDs are non-runtime until their own gates. Before Custom 2–4 are enabled, add source-specific in-flight cancellation/pruning so an unused source inside a still-live multi-source family generation cannot finish needless work.
