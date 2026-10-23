"""Plot per-identity displayed-radius curves for 2D Bubble and EB on one time axis.

Reads a ``bubble_response_comparison`` output directory and draws, for each mode and
class, the longest-lived mature identities inside ``--window`` as ratio-to-nominal
curves, with the mode's actual body input underneath. Logical ratios only.
Drawn with PIL (already a tool dependency); no plotting library is required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

_PANEL = (760, 250)
_MARGIN = 40
_COLOURS = ((230, 90, 70), (70, 160, 230), (90, 200, 110), (230, 190, 60), (190, 110, 220), (240, 240, 240))


def load(path: Path, start: float, stop: float):
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if start <= row["time_s"] <= stop:
                rows.append(row)
    return rows


def curves(rows, large: bool, count: int):
    series: dict[int, list[tuple[float, float]]] = {}
    for row in rows:
        for obj in row["objects"]:
            if obj["large"] is large and obj["mature"]:
                series.setdefault(obj["id"], []).append((row["time_s"], obj["ratio"]))
    return sorted(series.values(), key=len, reverse=True)[:count]


def body_input(rows, mode: str):
    if mode == "bubble":
        bass = [(r["time_s"], r["actual_energy"].get("pulse_bass", 0.0)) for r in rows]
        mid = [(r["time_s"], r["actual_energy"].get("pulse_mid", 0.0)) for r in rows]
    else:
        bass = [(r["time_s"], r["actual_bands"][0]) for r in rows]
        mid = [(r["time_s"], r["actual_bands"][1]) for r in rows]
    return [bass, mid]


def draw_panel(image, origin, title, lines, start, stop, low=None, high=None):
    draw = ImageDraw.Draw(image)
    x0, y0 = origin
    w, h = _PANEL
    draw.rectangle((x0, y0, x0 + w, y0 + h), outline=(90, 90, 90))
    draw.text((x0 + 6, y0 + 4), title, fill=(220, 220, 220))
    values = [v for line in lines for _, v in line]
    if not values:
        return
    low = min(values) if low is None else low
    high = max(values) if high is None else high
    span = max(1e-9, high - low)
    draw.text((x0 + 6, y0 + h - 14), f"{low:.2f}", fill=(150, 150, 150))
    draw.text((x0 + 6, y0 + 18), f"{high:.2f}", fill=(150, 150, 150))
    for index, line in enumerate(lines):
        points = [(x0 + (t - start) / (stop - start) * w, y0 + h - (v - low) / span * (h - 30) - 6)
                  for t, v in line]
        if len(points) > 1:
            draw.line(points, fill=_COLOURS[index % len(_COLOURS)], width=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--window", required=True, help="start,stop seconds")
    parser.add_argument("--ids", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start, stop = map(float, args.window.split(","))
    image = Image.new("RGB", (2 * _PANEL[0] + 3 * _MARGIN, 3 * _PANEL[1] + 4 * _MARGIN), (18, 18, 22))
    data = {mode: load(args.directory / f"{mode}.jsonl", start, stop) for mode in ("bubble", "extruded_bubble")}
    for row_index, large in enumerate((True, False)):
        lines = {mode: curves(rows, large, args.ids) for mode, rows in data.items()}
        values = [v for mode_lines in lines.values() for line in mode_lines for _, v in line]
        shared = (min(values), max(values)) if values else (None, None)
        for column, (mode, label) in enumerate((("bubble", "2D Bubble (floor ON)"), ("extruded_bubble", "EB (floor OFF)"))):
            origin = (_MARGIN + column * (_PANEL[0] + _MARGIN), _MARGIN + row_index * (_PANEL[1] + _MARGIN))
            draw_panel(image, origin, f"{label} {'large' if large else 'small'}: radius / nominal ({start:g}-{stop:g}s)",
                       lines[mode], start, stop, *shared)
    for column, (mode, label) in enumerate((("bubble", "2D"), ("extruded_bubble", "EB"))):
        origin = (_MARGIN + column * (_PANEL[0] + _MARGIN), _MARGIN + 2 * (_PANEL[1] + _MARGIN))
        draw_panel(image, origin, f"{label} body input: bass (red), mid (blue)", body_input(data[mode], mode),
                   start, stop, 0.0, None)
    image.save(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
