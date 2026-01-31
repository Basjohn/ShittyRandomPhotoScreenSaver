# Current Plan (Forward-Looking)

## Media Card & Overlay Reliability — **Status: In Progress (runtime validation pending)**

- **Why it matters:** MediaWidget, Spotify overlays, and Reddit cards must match the 2.6 experience: coordinated fades, tight control-row layout, responsive media keys, and deterministic polling. Recent regressions blocked live QA because the media glyph never flips on hardware keys and Reddit fades desynchronise across displays.
- **Latest progress (Jan 31 02:40):**
  - All MediaWidget unit/integration tests now pass (`python tests/pytest.py tests/test_media_widget.py`). Fixture cleanup issues were resolved via the `fade_ready_parent` harness, lifecycle resets, and deterministic fade/visibility checks.
  - Control-row shrink + artwork fade logic are covered by the refreshed tests, ensuring the card layout stays compact.

- **Outstanding work (prioritised):**
  1. **WidgetManager + Reddit fade tests**
     - [ ] Update Reddit widget fixtures to mirror the `fade_ready_parent` strategy so coordinated fades don’t stall under pytest-qt.
     - [ ] Rerun `python tests/pytest.py tests/test_widget_manager_refresh.py` and address any lingering lifecycle/reset issues surfaced there.
  2. **Runtime fade-sync verification**
     - [ ] Validate on a multi-display setup that `reddit`/`reddit2` overlays start fades simultaneously after the expected-overlay bookkeeping change.
     - [ ] Capture logs/screens to confirm the DisplayWidget bootstrap now registers all overlays with the coordinator.
  3. **Media key optimistic updates**
     - [ ] Route Qt media-key events through `_handle_media_key_feedback` and ensure `_apply_pending_state_override` fires even when `execute=False`.
     - [ ] Manually test hardware Play/Pause to verify the glyph flips immediately and telemetry logs the optimistic override.
  4. **Metadata polling resilience**
     - [ ] Harden ThreadManager injection for reused widgets (WidgetManager path) so `_ensure_timer()` always creates a poll handle once the manager exists.
     - [ ] Add regression coverage for timer creation logs and idle-wake polling so tests catch missing ThreadManager wiring early.
  5. **Documentation + audits**
     - [ ] Update `Spec.md`, `Index.md`, and `/audits/` with the new harness approach, fade-ready fixtures, and runtime validation notes once the above tasks close.

- **Exit criteria:**
  - `tests/test_media_widget.py` and `tests/test_widget_manager_refresh.py` stay green on repeated runs.
  - Live build demonstrates synced Reddit fades on every monitor and instantaneous play/pause glyph flips for media-key input.
  - Spec/Index reflect the finalized lifecycle + fade orchestration so future work reuses the harness instead of reintroducing visibility waits.

---
**Execution Notes:** Refresh this plan after each major milestone (e.g., widget_manager suite stabilized or runtime validation signed off) so it continues to list only the remaining work.