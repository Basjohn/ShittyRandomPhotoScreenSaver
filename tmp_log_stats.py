import re
from pathlib import Path
import numpy as np

log_path = Path(r"f:/Programming/Apps/ShittyRandomPhotoScreenSaver/logs/screensaver_spotify_vis.log")
pattern = re.compile(r"raw_bass=(?P<bass>-?\d+(?:\.\d+)?)\s+Bars:\s+\[(?P<bars>[^\]]+)\]")
frames = []
with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        m = pattern.search(line)
        if not m:
            continue
        bass = float(m.group("bass"))
        bars = [float(tok) for tok in m.group("bars").split()]
        frames.append((bass, bars))

if not frames:
    raise SystemExit("No frames parsed from log")

frames = frames[-720:]
bar_arr = np.array([bars for _, bars in frames], dtype=np.float32)
bar_avgs = bar_arr.mean(axis=0)
bar_max = bar_arr.max(axis=0)
bar_min = bar_arr.min(axis=0)
print("avg:", " ".join(f"{v:.3f}" for v in bar_avgs))
print("max:", " ".join(f"{v:.3f}" for v in bar_max))
print("min:", " ".join(f"{v:.3f}" for v in bar_min))
center_idx = bar_arr.shape[1] // 2
center_avg = float(bar_avgs[center_idx])
bar4_avg = float(bar_avgs[4])
print("center_idx", center_idx, "center_avg", f"{center_avg:.3f}")
print("bar4_avg", f"{bar4_avg:.3f}", "ratio", f"{center_avg/(bar4_avg + 1e-6):.3f}")
print("avg_neighbors_bar3_bar5", f"{bar_avgs[3]:.3f}", f"{bar_avgs[5]:.3f}")
print("edge_avg", f"{bar_avgs[0]:.3f}" )
center_vals = bar_arr[:, center_idx]
drops = []
for prev, curr in zip(center_vals[:-1], center_vals[1:]):
    delta = prev - curr
    if delta > 1e-3:
        drops.append(delta)
if drops:
    print("avg_drop", f"{np.mean(drops):.3f}", "max_drop", f"{np.max(drops):.3f}", "samples", len(drops))
else:
    print("avg_drop 0.000 max_drop 0.000 samples 0")
