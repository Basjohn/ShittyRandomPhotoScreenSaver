# Just Make It Work Pools | wallpaper provider discovery and design contract

## Intent and status

**Research/implementation target, not landed behavior.** A single themed `Just Make It Work Pools` popup replaces
both existing one-click curated-feed actions. It selects named, SFW online image-discovery pools while the existing
wallpaper engine alone owns final random/shuffled presentation. Operator-created feed URLs remain separate editable
inputs to the same RSS/Atom/JSON wallpaper acquisition product. The source-discovery UI is not another image
queue, cache, shuffle or periodic refresh owner. §3 SC4 in `Current_Plan.md` owns execution gates; this document
owns durable provider/UX/data/validation contracts and must not become a running changelog.

## Existing physical architecture and corrective observations

- `sources/rss/constants.py`: current four curated defaults are NASA Image of the Day, legacy NASA JPL Photojournal,
  public Wallhaven JSON search `https://wallhaven.cc/api/v1/search?categories=110&purity=100`, and Bing Image of
  the Day. Wallhaven **already uses its public JSON API without a key**; general+anime are selected and purity=SFW.
- `sources/rss/curated.py` writes replacement URLs into `sources.rss_feeds`. Both `ui/tabs/sources_tab.py` and
  `ui/onboarding/basic_pages.py` call it with different surrounding UI/commit behavior; replace that split with
  one reusable, correctly staged popup/admission flow. Guided Setup currently also treats enabling Feeds as applying
  the fixed curated defaults; audit that toggle so custom feeds cannot be overwritten by pool operations.
- `sources/rss/coordinator.py::_acquire` fetches a **document for every configured feed first**, then takes candidate
  images round-robin. `_run_pass` has a single pass lock; feed/image budgets and per-host politeness remain in force.
  Merely expanding `sources.rss_feeds` to dozens of URLs would amplify upstream listing requests. A pool selector
  must bound document acquisition *before* invoking `_acquire`, with fair turn-taking and deduped endpoints. It
  must not give every chosen theme a polling task or another admission scheduler. An all-source first-load pass is
  currently possible; a `refresh_single_feed` path already exists, so distinguish first fill and later top-ups.
- `sources/rss/json_listing.py` is site-neutral: entries with image URLs and optionally declared dimensions feed
  the common model. Retain its shape-based admission, with a very small source adapter only where required for
  genuinely different payloads. `sources/rss/image_fetch.py` checks original pixel size from early streamed bytes,
  without downloading an undersized full image. Declared API dimensions may reject early, not supersede this check.
- `Docs/Reference/Feeds.md` is the parent reference for wallpaper pool/transport/cache. Online wallpaper sources
  are *not* the FEEDS news-widget refresh subsystem.

## Proposed grouped pools and actual remote capabilities

### NASA Space (one user choice)

**Selecting Space selects all four subject families together**, not a user-facing NASA subject-picker. Retire the
NASA-wide Image of the Day (`www.nasa.gov/feeds/iotd-feed`) and legacy JPL Latest (`photojournal.jpl.nasa.gov/rss/new`)
from the *curated NASA Space* source set: these include staff, events and terrestrial editorial photography.
NASA Photojournal's official RSS catalog supports:

- **Universe:** `https://science.nasa.gov/feed/photojournal/gallery/universe/`
- **Mars:** `https://science.nasa.gov/feed/photojournal/gallery/mars/`
- **Sun:** `https://science.nasa.gov/feed/photojournal/gallery/sun/`
- **Solar System:** a rotation *among the actual official per-body feeds* (`mercury/`, `venus/`, `jupiter/`,
  `saturn/`, `uranus/`, `neptune/`, `dwarf-planets/`, `small-bodies/` under
  `https://science.nasa.gov/feed/photojournal/gallery/`). There is no verified single aggregate `solar-system/`
  RSS endpoint. Mars and Sun need not be re-requested by this group.

The named families are acquisition-selection intents, not a promise each NASA entry is a photogenic astronomical
photo. Official galleries also publish diagrams, illustrations, animations and spacecraft images; image-size/format
checks do not classify visual content. Exclude video/animation candidates, test representative feeds and decide
bounded content filtering on returned metadata before marking the default 'space-only' goal accepted. One feed
request at a time through the existing politeness/cache gate; don't fetch all Solar System feeds in one pass.

NASA reference: https://science.nasa.gov/photojournal/rss-feeds/

### Wallhaven themed searches (public API, current provider)

**User-facing choice is a checked *named search*, never the site's three broad category bits.** The old
`categories=110&purity=100` describes today's anonymous JSON provider implementation, not the future UI. Wallhaven
has powerful `q` keyword, tag, minus/exclusion and `id:<tag>` exact matching, plus `sorting`, `topRange`,
seeded `random`, and paged results (24/page). Define **independent checked search pools** with stable identifiers,
operator-editable selections and tested query-template mapping. Starter vocabulary (validate effectiveness in live
query samples; these are proposed *themes*, not guaranteed literal tags):

| Named checkbox/search pool | Discovery intent and initial Wallhaven query candidates |
| --- | --- |
| Nature & Landscapes | `nature`, `landscape`, `forest`, `mountains` |
| Space | `space`, `galaxy`, `nebula`, `planet` |
| Cities & Architecture | `city`, `architecture`, `cityscape` |
| Fantasy | `fantasy`, `fantasy landscape` |
| Science Fiction | `science fiction`, `sci-fi`, `spaceship` |
| Cyberpunk | `cyberpunk`, `neon city` |
| Abstract | `abstract`, `geometric` |
| Minimalism | `minimalism`, `minimal` |
| Anime Scenery | `anime scenery`, `anime landscape` |
| Dark Wallpapers | `dark`, `dark wallpaper` |

This is a **disjunction of individual pool queries over time**: do not concatenate checked themes into an
AND-search, do not fetch all synonyms or all checked themes together, and do not introduce another network timer.
A pool can own a *bounded rotation* of validated alternative expressions. Verify relevance, nonempty results,
source dimensions and host behavior with real sample listings before shipping a template; keywords alone do not
promise categorical accuracy. Persist stable pool IDs and exact query templates through source-owned configuration.

Keep `purity=100` nonnegotiable. Wallhaven `categories` bitmask remains an *internal* SFW/query-coverage filter;
there is **no General/Anime/People checkbox section** in Just Make It Work Pools. The user selects content themes,
not the site's taxonomy. The Wallhaven metadata `dimension_x/y` can reject candidates early; retain the original
header-stream size detector as the final dimension authority. With no API key, current SRPSS can use its public JSON
API; changing to HTML scraping is unnecessary. Honor Wallhaven's documented 45/minute API ceiling, throttling,
cache, conditional fetch and provider-owned pagination. Source: https://www.whvn.cc/help/api

### One global discovery-order preference (all Just Make It Work Pools)

Put **one** control near the top of the themed popup, outside *every* provider group. Example choices:
`Random`, `Latest`, `Popular`, `Top Today`, `Top This Week`, `Top This Month`, `Top This Year`.
It is a preference for **remote listing/candidate discovery only**, not SRPSS's local display shuffle and not
an additional ranking job. Every selected pool attempts the applicable remote translation; if the provider lacks
that operation, it retains its normal source listing order **without pretending to honor it**, re-sorting fetched
items, or performing extra ranking requests. The UI can show passive compatibility help such as "Not supported by
NASA/Bing" without creating per-provider order selectors. Persist one value in the canonical pool-settings owner.

| Provider | Random | Latest | Popular | Top Today / Week / Month / Year |
| --- | --- | --- | --- | --- |
| Wallhaven | `sorting=random`, seed/pagination | `sorting=date_added` | `sorting=favorites` (label as favourite-ranked) | `sorting=toplist&topRange=1d/1w/1M/1y` |
| NASA subject feeds | No sort control: use feed order | Native feed chronology | Unavailable | Unavailable |
| Bing Daily | Unavailable | Native daily entry | Unavailable | Unavailable |
| Konachan.net candidate | Do not assume query-random support | `order:id_desc` tag | `order:score` tag | No verified time-window leaderboard |
| Safebooru.org candidate | Unverified; do not synthesize | Native listing order | Unverified | Unavailable unless specifically proven |
| Danbooru Safebooru candidate | `random` list option documented | Native ID-desc order | Score/favourite tag orders subject to exact query verification | No presumed leaderboard |
| Zerochan candidate | Unverified | Native chronology if confirmed | Unverified | Unverified |

Provider ranking is *upstream selection* and does not change the existing coordinator's candidate admission,
deduplication, pacing, caching, or wallpaper-engine shuffle. A multi-pool selection produces **bounded, fair
provider/listing opportunities** over successive existing acquisition admissions; one pass must not turn into a
burst against every source. On a blank/unsupported result, fall back to the provider's ordinary query semantics,
not a secretly introduced global sorter. User-added custom RSS/Atom/JSON URLs remain independent and editable.

### Image-board eligibility research: ordered candidates and hard gates

Official/public documentation confirms the following *potential* integrations; **none has a successfully verified
live original-file retrieval in this investigation**. Direct read-only JSON listing probes were inaccessible from
this browsing environment. A published API contract cannot certify original CDN links, hotlink policy, rights or
SFW correctness. Prefer low-volume, operator-authorized samples before promotion to a bundled optional source.

| Site | What its published documentation supports | Wallpaper/SFW strengths | Remaining gating issues | Disposition |
| --- | --- | --- | --- | --- |
| **Konachan.net** | Moebooru `/post.json` (`limit` ≤100, `page`, `tags`) and `rating:safe`, `width`, `height`, `mpixels`, `ratio`, `score`, `order:id_desc`, `order:score` query metatags | The site requires landscape wallpaper-shaped submissions; `.net` is its rated-safe site, unlike `.com` | Live file URL, >1080p acceptance fraction, `Referer`/CDN policy, SFW rating errors, 403/429 and licence | **First optional anime wallpaper candidate** |
| **Safebooru.org** | Gelbooru `index.php?page=dapi&s=post&q=index&json=1`, `tags`, `pid`, `limit` ≤1000 | Lots of anime images and tag discovery | Site warns safe filtering has rating mistakes; many portraits/small images; needs stringent landscape, dimension and site-use validation | Secondary candidate, not auto-enabled |
| **Danbooru Safebooru** `safebooru.donmai.us` | `/posts.json?tags=...`, `random` and metadata for `image_width/height`, `rating`, `file_url`; global API read ceiling 10/s, sustained ≈1/s advised | Rich tags and precise `rating:g` (general) query; source dimensions | Non-wallpaper bulk content, occasional missing originals or other URL restrictions; strict no-sensitive filter; IP-shared rate quota | Strong metadata but lower wallpaper yield |
| **Zerochan.net** | Official read-only JSON/XML API, project + **username** User-Agent, 60 requests/min | Large anime illustration catalogue | Anonymous client may be banned; accounts, actual original access, landscape yield and download policy unproven | Evaluate after other boards |
| **Yande.re** | Moebooru-style API family documented by compatible clients, rating/size/tags conceptually possible | High-quality anime scans/wallpapers | No verified live safe-only endpoint, original accessibility, or safe-default guarantee; unrestricted board content | Research-only, opt-in only after robust SFW proof |
| **E-Shuushuu** | SFW image board, detailed tagging, public RSS link; no confirmed structured wallpaper/original API | Site explicitly forbids hentai, screenshots, and most nudity | Character-focused rather than wallpaper-focused, image minimum only 350×350, and no verified sanctioned full-original feed | Low priority; not a shipped provider |
| **MiniTokyo** | See dedicated section below | Old, sometimes high-resolution anime wallpaper archive | Rot, HTTP/HTTPS problems, login-gated originals, no stable public feed proved | Research-only |

**Probe before coding:** for each priority candidate, fetch one well-formed low-volume SFW listing with an
identifying User-Agent and permitted API, then inspect the returned original URL/width/height/rating without
assuming CDN conventions. Follow 1–2 *authorized* original links only far enough to verify content type and
streamed size headers (do not download rejected full images). Record HTTP status, redirect chain, referrer
requirement, rate headers, explicit terms/robots, typical landscape yield, and failures over separate runs.
Never evade authentication, 403/429, bot controls, or reuse hidden credentials. Distinguish a safe-rated site from
an absolute guarantee of SFW imagery; do not default any image board on solely because `rating:s` exists.

References:
- Wallhaven: https://www.whvn.cc/help/api
- Konachan API and site-specific rating/landscape rules: https://konachan.net/help/api ,
  https://konachan.net/help/cheatsheet , https://konachan.net/wiki/show?title=faq:_general ,
  https://konachan.net/forum/show/82083
- Safebooru.org API and safety caveat: https://safebooru.org/index.php?page=help&topic=dapi ,
  https://safebooru.org/index.php?page=help&topic=post
- Danbooru Safebooru API and rates: https://safebooru.donmai.us/wiki_pages/api:posts ,
  https://safebooru.donmai.us/wiki_pages/help:api
- Zerochan API: https://www.zerochan.net/api
- E-Shuushuu rules: https://e-shuushuu.net/rules

### MiniTokyo: research-only, do not silently ship as a default

`http://gallery.minitokyo.net/wallpapers?time=0` is an old anime-wallpaper archive, not a verified stable
machine-readable image feed. Public reports in 2026 describe intermittent 404/HTTPS mismatches, HTTP-only access,
registration trouble and account-gated original downloads. Indexed pages expose gallery item IDs, and old third-party
links sometimes refer to static `.jpg` originals, but an indexed URL pattern **does not prove** permitted, anonymous,
reliable original retrieval today. Direct web fetch in this investigation could not read site robots/pages. Do not
work around authentication, site controls, licensing or a broken robots policy.

**Before eligibility:** operator-approved live-access probe with ordinary, identifiable requests: obtain robots/terms,
fetch listing, follow a real gallery entry, resolve an authorized full-resolution image, inspect actual content-type,
size and quality from streamed headers, test conditional/page requests, cancellation/429/404 and repeat the sequence
across separate sessions. If login is necessary, don't scrape around it or embed user cookies as a distributed key.
If site access remains unreliable, retain it only as a manually configured URL option, not as a shipped curated pool.

Public availability discussion (June 2026): https://www.reddit.com/r/MoeDesktop/comments/1u0ac66/did_minitokyo_just_vanish/

## UI and authority

- Existing Sources-tab **Just Make It Work** button remains in place and opens themed `Just Make It Work Pools`.
  Same selection UI available from Guided Setup's **Just Make It Work** button. Use the existing popup/theme tokens,
  scrollbar, checkbox patterns, keyboard focus, disable/enable logic and cancel semantics, not private styling.
- Group by source family and recognizable *user intent*, not provider implementation jargon. NASA `Space` is one
  checkbox admitting its four subject families. Wallhaven exposes **thematic search checkboxes**, never its
  General/Anime/People category flags. Show **one discovery-order selector above all sources**, applying where
  each provider supports it and silently retaining native listing semantics otherwise (optionally explain support).
  Experimental boards stay opt-in only after live source verification. Provide sensible default selected pools but
  never silently reset prior operator-authored source choices when merely opening the dialog.
- One canonical Settings persistence contract owns curated pool selections. Actual selected feed IDs can be derived
  from those settings for the coordinator; custom `sources.rss_feeds` entries remain individually editable with normal
  RSS/Atom/JSON support. Define one-time legacy conversion from old curated list; never relabel user custom entries
  on URL resemblance alone. Handle partial custom mixtures, import/export, reset, cancel, guided-setup draft and
  Settings Save consistently. The guided wizard currently writes settings directly in places and must be audited
  for staged Save/Cancel parity before implementing the shared popup.
- Provider-side 'random/top/popular' means *which candidate listing the wallpaper pool receives*, **not** a
  competing displayed-image shuffle. Fair pool/source acquisition happens on the existing engine IO lane. One
  selected pool does not imply a continuously active task; one network request at a time, with conditional cache,
  429 backoff, per-host pacing, one pass admission and candidate attempt budgets intact.
- Empty/unavailable pools do not deadlock startup or indiscriminately empty accepted disk images. Source-list counts,
  onboarding readiness, 'disabled online feed' state, the folder/feed ratio and cache controls remain consistent
  in both Settings and Guided Setup. Existing wallpaper-source shutdown/resume watchlist in §5 stays independent.

## Verification gates (checklist, synthetic first)

- [ ] Enumerate/snapshot old curated and user-authored source selections; prove new defaults and one-time conversion.
- [ ] Prove named Wallhaven query-template encoding, SFW purity, internal category-bit safety, topRange and
      seed/pagination generation; selected themes are alternated, never merged into an AND query.
- [ ] Exercise **every global discovery-order value** across supporting and unsupported providers: verify mapped
      API parameter values, provider-native no-op fallbacks and no added display-side shuffle/ranker or periodic owner.
- [ ] For Konachan.net, Safebooru.org, Danbooru Safebooru, Zerochan and lower-priority boards, record bounded
      live listing/original probe outcomes, wallpaper-resolution yield, rating accuracy, permission, referrer/CDN
      behavior and error handling before enabling any board (especially in the default pool set).
- [ ] Test multiple selected themes contact a **bounded subset** of endpoints per pass, with round-robin fairness
      over successive allowed passes, deduplication, 429/timeout/backoff and shared per-host pacing.
- [ ] Verify NASA Space doesn't request general NASA IOTD/legacy JPL and draws coverage from all four subject groups
      over time rather than fetching every subfeed at once.
- [ ] Exercise both buttons with the real themed dialog: fresh/default, partial custom inputs, cancel, accept,
      repeated open, Guided Setup Continue/Skip/Finish, Setttings reload, import, reset, and last selected choice.
- [ ] Retain original header-based dimension detection on actual candidate images, including declared-dimension
      mismatch; don't fetch full undersized images.
- [ ] Physically inspect image relevance/SFW/coverage from each admitted site before enabling it in a public default.

No provider code, popup or schema is implemented merely by this document's existence.
