# RSS System Audit - Compliance Issues

## Resolution Status: ✅ RESOLVED (Modular Overhaul)

All issues below were addressed by splitting `rss_source.py` (1362 lines) into
`sources/rss/` (cache, parser, downloader, coordinator, health, constants):

| Issue | Resolution |
|-------|-----------|
| 1.1 `time.sleep()` blocking IO | Moved to `downloader.py` interruptible waits only; coordinator/parser have zero sleeps |
| 1.2 Sync network in IO thread | All network I/O isolated in `RSSDownloader`; called via `RSSCoordinator.load_async()` on ThreadManager IO pool |
| 2.1 No ResourceManager | `RSSCache` registers with ResourceManager in `__init__` |
| 2.2 File I/O untracked | `RSSCache` owns all disk operations with atomic write pattern |
| 3.x Shutdown handling | Every network call preceded by `_should_continue()` check; interruptible waits abort on shutdown |
| 4.x Rate limiting | Domain rate limiting centralised in `RSSDownloader`; Reddit quota coordination preserved |
| 5.x Cache management | `RSSCache` handles LRU eviction, startup validation, and cleanup |
| 6.x Download logic | Dynamic budget in `RSSCoordinator`: `target=50 - cached`, per-feed cap=3 |

Backup of original monolith: `bak/rss_source_pre_overhaul.py`

---

## Original Issues Found (Pre-Overhaul)

### 1. **THREADING VIOLATIONS**

#### Issue 1.1: Direct `time.sleep()` in IO Thread
**Location**: `screensaver_engine.py:857-861`, `rss_source.py:532-536`
```python
for _ in range(8):
    if engine._shutting_down:
        logger.info("[ASYNC RSS] Engine shutting down during delay, aborting")
        return
    time.sleep(1.0)  # ❌ BLOCKING IO THREAD
```
**Problem**: Blocks ThreadManager's IO pool thread for 8+ seconds per feed
**Impact**: Prevents other IO tasks from running, can delay shutdown
**Policy Violation**: Should use ThreadManager's scheduling, not raw sleep

#### Issue 1.2: Synchronous Network Requests in IO Thread
**Location**: `rss_source.py:_parse_feed`, `_parse_json_feed`
```python
response = requests.get(request_url, timeout=self.timeout, headers={...})  # ❌ BLOCKING
```
**Problem**: `requests.get()` blocks for up to 10 seconds per feed
**Impact**: 11 feeds × 10s = 110 seconds of blocking IO thread
**Policy Violation**: Heavy network I/O should be async or use proper worker processes

---

### 2. **RESOURCE MANAGEMENT VIOLATIONS**

#### Issue 2.1: No ResourceManager Registration
**Location**: `rss_source.py:__init__`
**Problem**: RSSSource creates file handles, network connections, but never registers with ResourceManager
**Impact**: Resources not tracked, potential leaks on shutdown
**Policy Violation**: "ALL resources MUST utilize ResourceManager for lifecycle management"

#### Issue 2.2: File I/O Without Tracking
**Location**: `rss_source.py:_download_image`, `_load_cached_images`, `_cleanup_cache`
**Problem**: Direct file operations without ResourceManager tracking
**Impact**: File handles may not be properly closed on shutdown
**Policy Violation**: Resource cleanup not deterministic

---

### 3. **SHUTDOWN HANDLING ISSUES**

#### Issue 3.1: Inconsistent Shutdown Checks
**Location**: Multiple locations
```python
# Some places check:
if engine._shutting_down:  # ❌ Direct attribute access

# Others check:
if not self._should_continue():  # ✅ Proper callback

# Some don't check at all:
for feed_url in feeds_to_process:  # ❌ No check inside download loop
    response = requests.get(...)  # Can block for 10s during shutdown
```
**Problem**: Shutdown can be delayed by up to 110 seconds (11 feeds × 10s timeout)
**Impact**: Poor UX, app appears frozen during exit

#### Issue 3.2: No Cancellation of In-Flight Requests
**Location**: `rss_source.py:_parse_feed`
**Problem**: Once `requests.get()` starts, it cannot be interrupted
**Impact**: Must wait for timeout even during shutdown
**Solution Needed**: Use `requests.Session()` with proper timeout handling or worker processes

---

### 4. **RATE LIMITING COORDINATION ISSUES**

#### Issue 4.1: Multiple Rate Limiters Not Coordinated
**Location**: `rss_source.py`, `screensaver_engine.py`
```python
# Domain-based rate limiting (rss_source.py)
self._domain_requests = {}  # Per-instance, not shared

# Reddit rate limiting (reddit_rate_limiter.py)
RedditRateLimiter (singleton, but per-process)

# Async loader delays (screensaver_engine.py)
time.sleep(8)  # Fixed delays between feeds
```
**Problem**: Three separate rate limiting mechanisms that don't coordinate
**Impact**: Confusing behavior, delays stack unnecessarily

#### Issue 4.2: Domain Rate Limiting Broken
**Location**: `rss_source.py:_check_domain_rate_limit`
**Problem**: Checks domain limit but then sleeps in main thread blocking everything
**Impact**: If Flickr is rate limited, ALL feeds wait, not just Flickr

---

### 5. **CACHE MANAGEMENT ISSUES**

#### Issue 5.1: Cache Loading Happens Twice
**Location**: `rss_source.py:__init__` and `screensaver_engine.py:_build_image_queue`
```python
# In __init__:
self._load_cached_images()  # Loads up to 35 images

# In engine:
cached_rss_images = []
for rss_source in self.rss_sources:
    cached_rss_images.extend(rss_source.get_images())  # Gets same images again
```
**Problem**: Duplicate work, confusing ownership
**Impact**: Wastes CPU, unclear which cache is authoritative

#### Issue 5.2: No Cache Invalidation Strategy
**Location**: `rss_source.py:_cleanup_cache`
**Problem**: Only cleans up based on size/count, not based on actual queue usage
**Impact**: Can delete images that are still in queue or recently shown

---

### 6. **DOWNLOAD LOGIC ISSUES**

#### Issue 6.1: Downloads Happen Even When Skipped
**Location**: `screensaver_engine.py:826-827`
```python
rss_source.refresh(max_images_per_source=feed_limit)
images = rss_source.get_images()  # ❌ Returns ALL cached images, not just new ones
```
**Problem**: `get_images()` returns entire `_images` list (cached + new)
**Impact**: Confusing logs, hard to track what was actually downloaded

#### Issue 6.2: Per-Feed Limit Not Enforced Correctly
**Location**: `rss_source.py:_parse_feed`
**Problem**: `max_images` parameter passed but then ignored in some code paths
**Impact**: May download more than intended

---

## Architectural Problems

### Problem A: Mixed Responsibilities
- `RSSSource` does: caching, downloading, parsing, rate limiting, health tracking
- Should be split into: `RSSCache`, `RSSDownloader`, `RSSParser`, `RateLimiter`

### Problem B: No Clear State Machine
- RSS loading state is scattered across multiple flags
- No clear "IDLE → LOADING → LOADED → ERROR" state tracking

### Problem C: Synchronous Design in Async Context
- Built for synchronous operation but called from async context
- Should either be fully async or use proper worker processes

---

## Recommended Overhaul

### Phase 1: Immediate Fixes (Compliance)
1. Remove all `time.sleep()` calls - use ThreadManager scheduling
2. Register all resources with ResourceManager
3. Add proper shutdown checks before every network call
4. Fix `get_images()` to return only new images, not entire cache

### Phase 2: Architecture Refactor
1. Split `RSSSource` into focused modules
2. Move network I/O to RSSWorker process (already exists but underutilized)
3. Centralize rate limiting in one place
4. Implement proper state machine for RSS loading

### Phase 3: Performance
1. Parallel feed downloads (respect rate limits)
2. Better cache management with LRU eviction
3. Incremental loading instead of all-at-once

---

## Immediate Action Required

The most critical violations to fix NOW:
1. ❌ **Remove `time.sleep()` calls** - blocks IO thread
2. ❌ **Add ResourceManager registration** - resource leaks
3. ❌ **Fix shutdown handling** - can block exit for 110+ seconds
4. ❌ **Fix `get_images()` behavior** - returns wrong data

These are blocking issues that violate core policies and cause poor UX.
