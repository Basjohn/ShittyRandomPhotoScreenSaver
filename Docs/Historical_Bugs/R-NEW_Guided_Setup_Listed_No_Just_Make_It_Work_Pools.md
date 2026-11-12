# R-NEW | Guided Setup's online sources list showed no Just Make It Work pools (Settings' Sources tab did)

**Status:** fixed 12 Nov 2026 (plan 1D.1). Reported by the operator. Owner: `ui/tabs/online_source_rows.py`
(`build_online_source_list`, `refresh_online_source_list`), used by `ui/tabs/sources_tab.py` and
`ui/onboarding/basic_pages.py` (`SourcesPage`). Regression bar: `tests/test_guided_setup_online_sources_parity.py`
(all three tests failed on the page before the fix: no pool rows). Silent: no error anywhere; pools were configured and
fetched, and the bucket's count ("· N ON") included them, but the list under it never showed them. Since the pools
shipped (a202ba75, 26 Oct); the gap widened when Sources gained its pool rows (bd3440f1, 1C.9, 11 Nov).

## Symptom

Guided Setup, Sources, Online Wallpaper Feeds: with pools enabled (in Settings or through the page's own Just Make It
Work), the list held only custom feed URLs, or nothing. The bucket title said e.g. "· 3 ON" over an empty list.
Settings' Sources tab listed the same pools as `JMIT POOL -> <Pool Name>` rows with their valid/failing/untried mark.

## Cause

Two list builders for one thing. The wallpaper pools (a202ba75) replaced the retired curated RSS URLs with a separate
selection (`sources.wallpaper_pools`), and the wizard page kept its own checkable list built from `sources.rss_feeds`
only, with a pools on/off checkbox above it. 1C.9 (bd3440f1) then gave the Sources tab pool rows through
`populate_online_source_rows`, called from the tab's own refresh with the tab's own pool lookup; the wizard page was not
a caller. The count used the shared `online_source_count`, which includes pools, so count and list disagreed.

## Fix

One owner for the list: `build_online_source_list` (the outlined list, the shared Settings list style, the row
delegate) and `refresh_online_source_list(list, settings)` (active pools in canonical order, then custom feeds, each with
its stored status). The Sources tab and the wizard page both call them; the wizard passes its `SettingsDraft`, so a pool
turned on in Guided Setup shows at once and reaches the store only at Finish. The wizard's tick-to-remove custom feed
list became Settings' Remove Selected (which never removes a pool row; pools stay with the Just Make It Work chooser
and the page's pools switch).

## Why it hid

- Nothing failed: the pools were saved and fetched, and the count was right.
- Tests covered each surface alone (the wizard's custom feed add/untick, the Sources tab's pool rows); none compared
  what the two surfaces list for the same settings.

## Lessons

1. A list shown in two places has one builder, called by both, never two that read the same settings separately.
2. When a stored shape moves (feed URLs to a pool selection), every reader of the old shape is a caller to update;
   search for the key, not only the class.
3. A parity test drives both real surfaces with the same settings and compares the rows, with a control on the old one.
