# Just Make It Work Pools

`Current_Plan.md` SC4 owns live work and physical acceptance. This file owns the source, persistence and provider
contract. Wallpaper acquisition is separate from the FEEDS news-widget runtime in `Feeds.md`.

## Owners and entry points

- `sources/rss/pools.py` owns the neutral catalogue, provider query projection, finite pass cursor, exact legacy
  migration and strict response examination. It owns no network, worker, timer, image cache or playback order.
  `core/settings/default_settings.py` alone owns default selected IDs, order and enablement.
- `ui/wallpaper_pool_popup.py` is the one staged, themed selector. Sources, Guided Setup and no-source recovery
  call `choose_wallpaper_pools`. Cancel writes nothing. Apply preserves custom URLs, folders, ratio and accepted
  cached images. Guided Setup writes only its existing SettingsDraft; Finish/discard remains its commit boundary.
  It uses shared circle-checkbox/combo/pill styles, provider-page selection counts and tooltips. Wallhaven uses a
  two-column list; Space & Daily and optional Image Boards keep their choices across navigation. The shared transparent
  scroll surface exposes the semantic popup background rather than an opaque native palette. Provider/ranking details
  belong in tooltips, not an explanatory paragraph. Sources summarizes enabled counts with full names in its tooltip.
- `sources/rss/coordinator.py` remains the wallpaper pass/acquisition owner. Existing startup IO and background
  cadence drive its pass lock, image-attempt budget, rejection memory, cache, cancellation and session rotation.
- `core/feeds/source.py` / `transport.py` retain bounded HTTP/DNS/redirects, validators, last-good and persisted
  backoff. Retry-After delta/date extends backoff. The coordinator shares HTTP 429 host backoff and uses its existing
  per-host gate for listings (Wallhaven at least 1.5s). No pool gets a schedule.
- `json_listing.py` retains the generic image reader; pool-only rating filters run before row admission.
  `nasa_listing.py` only normalizes NASA search/manifest JSON and performs no network work.

## Settings, migration and readiness

The existing flat Sources persistence projection owns these leaves:

| Canonical key | Meaning |
| --- | --- |
| `sources.wallpaper_pools.enabled` | Admit the retained selection; disabling retains choices |
| `sources.wallpaper_pools.selected` | Stable catalogue IDs, never expanded URLs |
| `sources.wallpaper_pools.discovery_order` | One upstream discovery preference |
| `sources.rss_feeds` | Separately authored custom RSS/Atom/JSON/image-listing URLs |

Fresh profiles keep pools disabled until an explicit action; the popup shows canonical suggestions. Selecting none
disables pools. Guided Setup's pool-enable switch never replaces/removes custom URLs. Pool-only configurations count
for startup/readiness, ratios, bucket counts and Guided Setup summary. Readiness makes no network request. An empty
selection cannot close no-source recovery or pretend to finish Guided Setup with a usable source.

Reset preserves pool choices like custom URLs/folders. SST supports the existing flat projection and natural nested
`sources.wallpaper_pools` through one import/preview projection; conflicting flat/nested values are rejected.

One compatibility bridge recognizes **exact** retired URLs in `LEGACY_CURATED_RSS_FEEDS`, including partial/custom
mixtures. Retired NASA IOTD/JPL becomes grouped NASA Space; broad SFW Wallhaven becomes its named theme pools;
Bing becomes Bing Daily. Every other URL remains byte-for-byte in relative order. Query variants/lookalike hosts
remain custom. Presence of the new selection prevents reconversion. Startup runs before defaults; SST import and
preview use the same pure bridge. The old fixed-list replacement action is removed.

## Bounded acquisition and cache identity

Each real pass admits at most **two document opportunities** before image acquisition. Custom URLs/ordinary pools
cost one; NASA costs two (search plus at most ONE selected manifest). Sources share a finite fair cursor, so many
checked themes do not become an all-source request burst. Identical endpoint URLs are deduplicated per pass. A full
cache with no pending session replacements does not advance the cursor or fetch listings. The existing session policy
may replace stale entries in a full cache, retiring each old image only after its replacement is accepted on disk.

An empty-cache startup uses one existing IO job, with up to six document opportunities, one shared forty-image
attempt budget and a twenty-second cooperative acquisition deadline. A zero-result opportunity advances the same
cursor within those bounds; it does not fetch every selected source. In-flight reads retain the existing transport
timeouts (ordinary silent listing waits up to three seconds, image reads five), so the cooperative deadline is not a hard process
deadline. Ordinary passes retain the two-document bound. Queue construction keeps its existing synchronous disk-cache
warm preload but performs no synchronous network acquisition.

The single IO completion merges through the existing queue-cap/dedup owner and posts one coordinator/queue/runtime-
fenced GUI continuation to foreground image admission. Startup hydration does not add playback randomization or retire
accepted offline images by the background TTL policy. While an empty queue genuinely awaits source IO, the existing
reveal watchdog pauses only after display construction; the same watchdog rearms before first image admission.
There is no GUI polling or second startup state machine. Shutdown rejects both acquisition and queued publication.

Runtime teardown stops the coordinator and its existing refresh timer. Startup/background IO jobs carry the submitting
runtime generation, including their result publication, so the existing destruction barrier drains them before Settings
or a replacement can acquire the same disk-cache writer. Late results require the same live coordinator, queue and
generation. The barrier timeout is unchanged; slow status/header trickle remains the shared HTTP limitation documented
in `Future_Work.md`, rather than a claimed hard cancellation guarantee.

After Settings, positive-display admission constructs a fresh coordinator; it never revives a stopped one. Unchanged
sources retain queue identity/history, folder objects, decoded cache and prefetcher. Changed sources use the existing
rebuild path, invalidating prefetch before clearing decoded cache and replacing queue membership. Source-change and
pending-admission flags are consumed only after successful admission, so zero-display suspension and another Settings
visit cannot lose pending changes. The existing background cadence is restored once, with no new scheduler.

Wallhaven/board pages rotate through a bounded range; Wallhaven Random has one coordinator-generation seed.
Stable logical FeedSource/cache identity survives page/seed changes: health stays retained, validators apply only
to matching endpoint fingerprints. There is no source object per random seed/page. NASA retains one search and one
asset source per subject.

Pools inject a strict response_examiner and max_discovery_fetches=1 into existing FeedSource. HTML or a generic
RSS/Atom/JSON Feed cannot replace rating-bearing JSON or advertise extra feed requests. Bing explicitly admits its
native RSS archive. Custom URLs retain normal bounded discovery. Each document still has transport redirect caps.

Actual streamed image headers remain the final dimension authority; declared sizes only reject early. Thumbnails,
incorrect metadata and undersized originals cannot bypass it. Offline/429/empty sources keep accepted disk images;
session rotation retires an old image only after replacement is on disk. No playback shuffle/ranker is added.

## Provider semantics

Wallhaven exposes named themes rather than category switches. Checked themes stay separate queries over time,
never an AND-search. The catalogue owns vocabulary; requests fix purity=100 and returned rows must declare sfw.

NASA Space is one choice for Sun, Mars, Universe and Solar System, with equal subject opportunities; Solar System
rotates one body per turn. Its explicit provider is the official **NASA Images API**, using bounded JPL image/title
queries and a recent-archive floor to improve yield. Returned nasa_id identifies the documented asset manifest;
only an original URL returned by that manifest is considered. No guessed original/preview URLs. Non-image media and
video/movie/animation titles are excluded. Actual format/size admission still applies; metadata does not guarantee
every returned diagram, spacecraft image or illustration is a photogenic astronomical photograph.

The official Photojournal RSS subject endpoints tested on 2026-10-26 returned malformed XML: adjacent
`xmlns:apod="..."xmlns:media="..."` attributes without whitespace (line8,column45), yielding zero parsed entries
despite HTTP200. The independently documented Images API is the chosen provider, not silent XML sanitization or
fallback to NASA-wide editorial feeds.

| Provider | Global discovery-order translation |
| --- | --- |
| Wallhaven | Random=sorting=random + seed; Latest=date_added; Popular=favorites; Top Today/Week/Month/Year=toplist + topRange=1d/1w/1M/1y |
| Konachan.net | Latest=order:id_desc; Popular=order:score; unsupported orders keep native order |
| NASA/Bing/Safebooru.org/Yande.re | Native provider order; no invented random/ranking/time-window request |

## Anonymous eligibility evidence

Bounded live checks on 2026-10-26 used identifiable anonymous requests, verified TLS, small listings and streamed
original prefixes. No cookies, referrer workaround, auth bypass or full rejected-image download. These prove access,
protocol and pixels, not perpetual availability or subjective relevance. Boards are optional and absent from fresh
suggestions; admission enforces the site's Safe/General rating, without claiming a visual-content classifier.

| Provider | Verified gate / disposition |
| --- | --- |
| Wallhaven | All named queries nonempty/SFW; actual original6000×4000, HTTP200, no referrer; API reports45/min. Fixed SFW request AND response admission. |
| NASA Images | Documented search→manifest→returned original; Mars2880×1800, Sun2000×2000, Galaxy2133×1200. Jupiter sample512×512 demonstrates required size rejection. Admitted explicit API. |
| Bing | RSS8 entries; actual original1920×1080, HTTP200. Naturally rejected on larger displays. |
| Konachan.net | Documented Moebooru, Safe rows, original3511×1884, HTTP200/no referrer. Optional; exact rating=s. |
| Safebooru.org | Documented DAPI, General rows, original4608×6144, HTTP200. Mixed portrait yield; optional, exact rating=general. Robots excludes admin/img/removal, not tested DAPI/original paths. |
| Yande.re | Anonymous Safe query/original1920×2879 worked, HTTP200; poor landscape yield. Optional, exact rating=s; no presumed ranking support. |
| Danbooru Safebooru | General API/original4096×3277 worked; robots explicitly disallows JSON crawling. Excluded pending access-policy clarification; no bypass. |
| Zerochan | API503; anonymous original and identifying username/client policy unverified. Excluded. |
| MiniTokyo | TLS rejected self-signed certificate; no insecure retry or verified permitted original. Excluded. |
| E-Shuushuu | Robots reachable; sanctioned structured original discovery/retrieval path unverified. Excluded. |

Receipts: `tmp/sc4_provider_probe.json`, `sc4_catalog_probe.json`, `sc4_nasa_api_probe.json`, `sc4_bing_probe.json`,
`sc4_robots_probe.json`, `sc4_production_seam_probe.json` (all under tmp). The final seam exercised real
RSSCoordinator/FeedSource/strict parsers including NASA manifest in isolated storage. Header evidence is not operator
image-relevance acceptance; native popup/image review remain separate live-plan gates.

Primary contracts: [Wallhaven](https://www.whvn.cc/help/api),
[NASA Images API](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf),
[Photojournal RSS](https://science.nasa.gov/photojournal/rss-feeds/),
[Konachan API](https://konachan.net/help/api)/[queries](https://konachan.net/help/cheatsheet),
[Safebooru DAPI](https://safebooru.org/index.php?page=help&topic=dapi),
[Danbooru posts](https://safebooru.donmai.us/wiki_pages/api:posts), [Zerochan API](https://www.zerochan.net/api).

## Focused verification

`tests/test_wallpaper_pools.py`: every global order, query/rating contracts, weighted fairness, NASA groups and
manifest bounds, HTML/RSS/JSON-feed negatives at the actual FeedSource seam, stable cache identity, Retry-After.
`tests/test_wallpaper_pool_popup.py`: staged Apply/Cancel/draft, persisted/SST/Reset roundtrips, custom preservation,
pool-only ratio/readiness, circle/tooltip styling contracts and cross-page choice retention. Native top/provider/tooltip
and Sources-page captures under `tmp/wallpaper_pool_native/{dark,light}` inspect Neon Mall Acrylic and Pearl Blush Glass
in real Settings. Provider descriptions and the custom-feed format/size explanation stay in tooltips.
`tests/test_wallpaper_pool_startup.py`: one IO admission, failed-first/usable-later, real foreground submission seam,
no-source failure, shutdown/queued callback rejection, finite document/deadline bounds and shared watchdog pause/rearm.
`tests/test_wallpaper_pools_zero_display.py`: selected NONE and empty Qt inventory keep source/queue/cache/network
admission dormant through actual engine initialization, display admission and start.
`tests/test_rss_settings_resume.py`: actual post-Settings continuation, preserved unchanged playback, changed sources,
zero-to-positive admission, stale background publication and held IO draining through the real ThreadManager/barrier.
Existing coordinator/image-fetch/feed tests cover real size rejection, full/offline cache,
replacement/cancellation and generic custom discovery. Use the no-env plugin and isolated basetemp in
`Docs/TestSuite.md`. Physical image relevance remains a separate operator gate.
