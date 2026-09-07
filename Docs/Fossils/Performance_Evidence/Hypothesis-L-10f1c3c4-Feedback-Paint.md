# Hypothesis Record — Slice L / 10f1c3c4 — Feedback-Only Parent Paint Fast Path

## Hypothesis

Skipping artwork/header/metadata/logo/progress subpainters on controls-row-only damage will make
animated feedback genuinely lightweight in production.

## Source correction

Commit:

```text
10f1c3c45a9c898499acd8088b7cab3ad0929251
```

The test uses a real `MediaWidget` and real Qt repaint events. In its clean row-only case, the five
selected expensive subpainters run zero times across repeated feedback frames.

## Narrow mechanism status

**CONFIRMED**

The selective branch can skip those named subpainters when the damage event remains inside the
feedback row.

## Installed performance status

**RED / NOT ACCEPTED**

Third installed run still reports repeated parent `media.paint` windows around:

```text
~5–6+ ms average
```

with frame-count-scale calls.

The unit gate does not establish:
- that real Qt damage remains row-only under ordinary application invalidation/coalescing;
- that `BaseOverlayWidget.paintEvent()` is cheap;
- that no overlapping parent damage forces the full path;
- that the overall parent-card paint cost is low.

## Durable conclusion

Do not call Slice L a production performance success from its focused unit test.

A later fix may retain the selective branch, replace it with a lightweight child/overlay, or remove it
if the production ownership changes. Installed cost decides.
