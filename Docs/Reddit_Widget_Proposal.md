# Reddit Widget Proposal

## 1. Goal

Provide an optional overlay widget that displays the top N posts from a configured subreddit (e.g. `r/wallpapers`), styled consistently with existing widgets, and opens the users default browser to the selected post on click.

The widget should be **read-only**, performant, and respect the projects theming and interaction model.

---

## 2. Feasibility & Data Source

### 2.1 Data Source Options

- **Unauthenticated JSON endpoints (preferred)**
  - Reddit historically exposes JSON views for listing pages (e.g. `https://www.reddit.com/r/<subreddit>/hot.json?limit=N`).
  - Pros:
    - No API key or OAuth flow required.
    - Simple JSON payload (titles, URLs, scores, etc.).
  - Cons:
    - Subject to rate limiting and potential format changes.
    - Some endpoints may enforce stricter requirements or CORS when used from embedded/HTML contexts; however, this app is a native desktop client using Python HTTP, not a browser.

- **Official Reddit API (with OAuth / keys)**
  - Requires registering an app and handling tokens.
  - Not aligned with the current "no API keys" preference (e.g. Open-Meteo for weather).

**Proposal:**
- Start with **unauthenticated JSON listing endpoints** for order-by-hot access.
- Design the widget so it can be disabled or degraded gracefully if/when Reddit tightens unauthenticated access.

### 2.2 Request Strategy

- Fetch using the existing IO/ThreadManager infrastructure.
- Respect conservative rate limits:
  - Refresh no more than **once every 1030 minutes** while the widget is visible.
  - Back off and log on repeated failures.
- Basic settings:
  - `widgets.reddit.subreddit`: string (default `wallpapers` or user choice).
  - `widgets.reddit.sort`: enum (`hot`, `new`, `top`)  initially `hot` only.
  - `widgets.reddit.limit`: int (e.g. 510 items, default ~10).

---

## 3. Architecture

### 3.1 Core Components

- **`widgets/reddit_widget.py`**
  - `RedditWidget(QLabel or QWidget)`
    - Handles painting of the Reddit header and list of entries.
    - Integrates with `widgets/shadow_utils.apply_widget_shadow`.
    - Hit-tests mouse clicks to open links in the browser.

- **`reddit/reddit_client.py` (optional new module)**
  - Thin client responsible for:
    - Building subreddit URLs (`/r/<subreddit>/<sort>.json?limit=N`).
    - Parsing JSON into a simple `RedditPost` dataclass:
      - `title: str`
      - `url: str` (prefer `url_overridden_by_dest` / `permalink`)
      - `score: int`
      - `num_comments: int`
    - Handling HTTP errors, rate limits, and backoff.
  - Uses the existing **ThreadManager IO pool**.

- **Settings integration**
  - Add a **Reddit section** under `widgets` in Settings:
    - Enable/disable widget.
    - Subreddit name.
    - Item count.
    - Position + display monitor (matching Spotify/weather widgets).

### 3.2 Threading & Caching

- All HTTP fetches run off the UI thread via ThreadManager.
- Cache the latest successful listing for a short window (e.g. 1030 minutes) to avoid hitting Reddit repeatedly.
- On failure:
  - Keep displaying the last known list, with a small inline Last updated at HH:MM (stale) note if desired.

---

## 4. UI & Interaction

### 4.1 Visual Design

- **Card-style overlay**, similar to Spotify:
  - Header: Reddit logo (or a generic icon) + `r/<subreddit>` text.
  - Body: list of post titles, each on one or two lines, ellipsized at the end.
  - Optional small score/comment count in a lighter color.
- Uses existing dark theme colours and optional background frame + drop shadow (via `widgets.shadows`).

### 4.2 Behaviour

- **Mouse click** on a post:
  - Opens the post (or direct link) using `QDesktopServices.openUrl()` in the system default browser.
  - Does **not** support upvotes, comments or any authenticated action.
- **Interaction gating**
  - Reuse the same gating as Spotify controls:
    - Only respond to clicks when the user is in Ctrl-held or hard-exit interaction mode.
    - Otherwise, the widget is display-only.

### 4.3 Layout & Performance

- Limit rendering cost:
  - Max N items (default ~10).
  - Pre-measure and elide text with `QFontMetrics`.
  - Avoid per-frame layout churn; recompute layout only when data or size changes.

---

## 5. Error Handling & Fallbacks

- If Reddit JSON fetch fails:
  - Log a clear warning with the HTTP status / exception.
  - DO NOT SHOW/DRAW WIDGET AT ALL
  - Do **not** spam retry; use a backoff timer.
- If the endpoint behaviour changes dramatically (breaking parse):
  - Catch parse errors and log them.
  - Fall back to a disabled state rather than crashing the screensaver.

---

## 6. Settings Schema Sketch

Proposed keys (to be folded into `Spec.md` once implemented):

- `widgets.reddit.enabled`: bool
- `widgets.reddit.subreddit`: str (e.g. `wallpapers`)
- `widgets.reddit.sort`: str (`hot`|`new`|`top`)  initially `hot` only
- `widgets.reddit.limit`: int (510, default 10)
- `widgets.reddit.position`: str (Top Left/Top Right/Bottom Left/Bottom Right)
- `widgets.reddit.monitor`: str (`ALL`|`1`|`2`|`3`)
- `widgets.reddit.show_scores`: bool

---

## 7. Risks & Constraints

- **Upstream changes**: Reddit may alter or lock down unauthenticated JSON endpoints, which could:
  - Break the widget until updated.
  - Require falling back to an officially authenticated API (with keys) or fully disabling the widget.
- **Legal / ToS considerations**:
  - The widget must honour Reddits terms of use for public content and not attempt to bypass rate limits.
- **Network dependency**:
  - The widget is non-essential; on offline systems it should fail gracefully without affecting core screensaver behaviour.

---

## 8. Implementation Plan (High Level)

1. Add `reddit/reddit_client.py` (or similar) using ThreadManager IO pool.
2. Implement `RedditWidget` with basic card UI and clickable entries.
3. Wire up settings under the Widgets tab (enable, subreddit, limit, position, monitor).
4. Integrate into `DisplayWidget` overlay management similar to Spotify/weather widgets.
5. Add logging and a few targeted tests covering:
   - Successful fetch/parse of a canned JSON sample.
   - Error handling and backoff.
   - Click-to-open behaviour (mocked `QDesktopServices.openUrl`).
6. Update `Spec.md`, `Docs/Spec.md`, and `Docs/Index.md` to include the Reddit widget as an optional overlay.
