# DT MAX Investigation Checklist

## Problem Statement
DT MAX values remain high (80-100ms) even after recent fixes to:
- Fade coordinator issues
- Lifecycle double-initialization

## Investigation Areas

### 1. FadeCoordinator Analysis
- [ ] Check if fade coordinator continues running after all fades complete
- [ ] Investigate thread contention from fade coordination polling
- [ ] Review lifecycle check frequency and aggressiveness
- [ ] Examine timer intervals and callback frequency

### 2. Reddit Widget Analysis  
- [ ] Check if Reddit widgets are painting constantly (not just every 5-10 min)
- [ ] Investigate repaint triggers (hover effects, animations, shadows)
- [ ] Review update timers and their intervals
- [ ] Examine paint event frequency in perf logs
- [ ] Check for unnecessary update() calls
- [ ] Review shadow/fade effect invalidation

## Current Findings

### Reddit Widget Paint Metrics (from recent run)
```
widget=reddit kind=paint metric=reddit.paint calls=50 avg_ms=8.27 max_ms=11.76 slow_calls=50 area_px=479400
widget=reddit2 kind=paint metric=reddit.paint calls=50 avg_ms=8.57 max_ms=9.54 slow_calls=14 area_px=477000
```

**Observation**: Both Reddit widgets show `slow_calls=50` and `slow_calls=14` respectively - this means ALL paint calls are considered "slow" (>5ms threshold). This is the smoking gun.

## Hypotheses

1. **Reddit widgets repainting every frame** - Even though content only updates every 5-10 min, something is triggering constant repaints
2. **FadeCoordinator polling** - May be running timers/checks continuously even when idle
3. **Effect invalidation cascade** - Shadow/fade effects causing repaint chains

## Next Steps
- Profile paint call stacks for Reddit widgets
- Check what triggers update() calls
- Examine fade coordinator idle state
