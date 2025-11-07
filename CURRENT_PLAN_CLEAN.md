# CURRENT PLAN - Actionable Tasks

**Updated**: Nov 6, 2025 19:30

---

## ⚠️ JUST FIXED (Need User Testing)

- [ ] **Wipe transition** - Enabled setScaledContents (fix DPI distortion)
- [ ] **Block Puzzle transition** - Enabled setScaledContents
- [ ] **Diffuse transition** - Enabled setScaledContents + fillRect/QRectF
- [ ] **Pan & scan jump** - Transitions use pan-scaled images
- [ ] **Lanczos scaling** - Removed blocking optimization
- [ ] **Transitions tab** - Added scroll area

**PLEASE TEST THESE - especially wipe/block/diffuse**

---

## 🔴 KNOWN BROKEN (From Tests)

### 1. Pan & Scan Label Stays Hidden
**Test**: `test_pan_scan_cleanup_between_images` fails  
**Fix**: Show label in `_on_transition_finished()`

### 2. Default Duration Wrong
**Test**: expects 1300ms, gets 500ms  
**Fix**: Check settings defaults

### 3. Transitions Timeout
**Test**: Wait 600ms but transitions take 2000ms  
**Fix**: Increase test wait times

---

## 📋 TODO (After Testing)

1. Run full manual test of all transitions
2. Fix any remaining bugs
3. Update Docs/INDEX.md with current structure
4. Update Docs/SPEC.md with changes

---

## 📊 Test Results (Nov 6, 19:25)

```
2 PASSED:
- test_pan_scan_stopped_before_transition
- test_block_puzzle_with_pan_scan

5 FAILED:
- test_diffuse_with_pan_scan (timeout)
- test_wipe_with_pan_scan (timeout)
- test_crossfade_duration (wrong default)
- test_pan_scan_cleanup_between_images (label hidden)
- test_all_transitions_with_pan_scan (timeout)
```
