# R-104 — FEEDS Main-GIL Parsing Stalled Qt, Warm Artwork Lost Its Binding, And Hydration Drove Fades

**STRONG RETENTION VALUE DOCUMENT**

**Status:** SOLVED / ACCEPTED (2026-10-02). FEEDS retains robust cache-first/last-good semantics while expensive document examination is isolated from the Qt process GIL and warm artwork identity is durable.

## Symptoms

Three failures became entangled while FEEDS was being hardened:

1. Periodic News/Custom refreshes produced visible event-loop hitches. At 15 minutes, then deliberately shortened to 5 minutes for testing, stalls repeatedly reached roughly **180-356 ms**.
2. Warm startup had cached articles and cached image files but often started without those images, then rebound them later.
3. Intermediate presentation fixes first produced **5-20 slow startup fade cycles**, then overcorrected into full-opacity artwork/body snaps.

## Root causes

### A. IO threads were not GIL isolation

Initial stagger work correctly stopped all providers from refreshing together, but one very large feed was enough to reproduce the hitch by itself: a roughly **2.45 MB** document spent about **278-298 ms** inside pure-Python `feedparser`. Running that work in the ordinary IO thread pool still monopolized the **same main interpreter GIL** that Qt/GUI Python needs. Serialization fixed collision, not single-parser starvation.

### B. The durable cache forgot accepted artwork identity

The feed cache knew the normalized article and the artwork cache owned the PNG, but durable state did not retain the accepted **item -> cache-owned artwork filename** association. Restart therefore threw away an answer the previous session had already paid to discover.

### C. Presentation transitions were coupled to hydration events

Progressive cache/network/artwork publications were allowed to behave like independent article transitions. Staggering made that visually worse because each source could trigger a legitimate-looking slow fade in sequence. Suppressing all startup fades then made the final hydrated state replace visible content at full opacity.

## Fix

- One **lazy spawned parser process per active FEEDS family** owns pure remote-document examination/normalization (RSS/Atom/JSON plus supported HTML/h-feed examination). Network transport, cadence, validators, last-good state, artwork cache ownership and presentation authority remain in the main FEEDS owners.
- There is **no in-process parser fallback**. A parser failure fails that refresh and preserves last-good presentation; a later legitimate demand may lazily recreate the child. The final active lease retiring closes the parser process.
- Source refreshes remain staggered; providers are not deliberately phase-aligned or pulled early.
- The durable last-good feed record persists only validated cache-owned `<sha256>.png` artwork bindings. Warm restore validates the file and publishes cached rows with local artwork immediately, before network construction. Missing/corrupt/evicted artwork drops only that image, not the article.
- Presentation consumes coherent latest-wins bundles. Startup coalesces into one gentle body transition rather than per-source/per-hydration fades; later genuine article-set replacements use the body fade. Artwork uses the retained two-buffer fade primitive instead of popping in.
- Needless normalization is bounded to visible/usable capacity instead of historical 40-item work per publisher.

## Acceptance

- **13 focused product tests pass**, including real spawned-child isolation with the parent parser deliberately poisoned, parser failure preserving last-good rows/artwork, fresh-source warm restore with network construction forbidden, durable artwork across a fresh `FeedSource`, missing-art degradation, source staggering, family-wide startup settlement and parser-process dormancy.
- A later two-display source run with active Bubble crossed a real FEEDS refresh: the old recurring **180-350 ms** cadence-bound stalls were absent. The one notable refresh-window outlier was **63 ms** exactly as the lazy parser child first appeared; subsequent windows returned to ordinary low tails.
- Warm startup restored cached local images with `attempts=0` / `newly_cached=0`, demonstrating that the saved artwork binding, not network rediscovery, supplied them.
- SHM/lifecycle/QML remained clean and the parser child produced one bounded active-feature process/handle baseline rather than a continuing ratchet.

## Durable lesson

A Python IO thread is not isolation from the main interpreter GIL. Cache durability must preserve **accepted relationships**, not merely individual blobs. And animation/presentation must consume coherent product states; backend hydration callbacks must not become visual transition authority.
