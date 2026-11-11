"""Capture card surface materials on the production display scene, never on screen.

The production ``DisplayScene.qml`` renders through ``QQuickRenderControl`` into a hidden
OpenGL texture (the Guided Setup foundry's ``_HiddenQuickScene``; Windows QPA, no window is
shown or mapped). It carries the real ``BackgroundRenderItem`` (wallpapers and production
transitions), the real ``SurfaceBackdropOwner`` and real family presentations (Weather,
Media, Reddit, System Stats, a digital Clock) with fixture data. Each material is drawn
beside Normal under a dark and a light Widget Theme, on still wallpapers and mid-transition.

    python tools/surface_material_capture.py --wallpapers DIR --output DIR [--sheets] [--cadence] [--cost]

``--cadence`` measures how far a backdrop refreshed every Nth frame drifts from one
refreshed every frame through whole transitions (the refresh-rate decision); ``--cost``
times the backdrop refresh and the whole frame per material with ``GL_TIME_ELAPSED``.
``--style`` writes full frames per theme/wallpaper/material plus one mid-transition frame and the
scene rectangles of named items (``regions.json``) for before/after crops; ``--card-set lists`` swaps
in Gmail, a news Feed, Friend Pulse and System Stats; ``--themes DARK LIGHT`` picks the themes.
Design and acceptance: ``Docs/Architecture/Card_Surface_Materials.md``.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

MATERIALS = ("normal", "acrylic", "glass", "frosted", "mica", "smoked")
SCENE = (1600, 900)
# Several transitions, including 3D ones (Block Spins, Glass Shatter, Cube Turn, Page Curl).
TRANSITIONS = ("wipe", "slide", "block_spins", "glass_shatter", "cube_turn", "page_curl")
LIGHT_THEME = "Polished Chrome [Single]"
DARK_THEME = "Default Dark"
# "main": Weather, Media, Reddit, System Stats, Clock; "lists": Gmail, Feed, Steam, System Stats.
CARD_SET = "main"


# --------------------------------------------------------------------------- scene


class MaterialScene:
    """The hidden production scene with a wallpaper background, backdrop owner and cards."""

    def __init__(self, width: int, height: int, *, dpr: float = 1.0) -> None:
        from tools.onboarding_preview_foundry import _HiddenQuickScene
        from rendering.quick.render.background_item import BackgroundRenderItem
        from rendering.quick.render.telemetry import RenderNodeTelemetry

        self.scene = _HiddenQuickScene(width, height, dpr=dpr)
        self.scene.window.setColor("black")
        root = self.scene.root
        self.background = BackgroundRenderItem(root, telemetry=RenderNodeTelemetry(), screen_index=0)
        self.background.setZ(0.0)
        self.background.setWidth(root.width())
        self.background.setHeight(root.height())
        root.setProperty("transitionRenderItem", self.background)
        self.owner = None
        self.presentations: list = []
        self.run_id = 0
        self.art: Path | None = None

    @property
    def host(self):
        return self.scene.host

    def render(self, frames: int = 1) -> None:
        for _ in range(frames):
            self.scene.render()

    def read(self):
        return self.scene.read().convert("RGB")

    def set_wallpaper(self, image) -> None:
        self.background.set_transition_run(None)
        self.background.set_presentation_image(image)
        if self.owner is not None:
            self.owner.set_transition_active(False)
            self.owner.note_background_changed()

    def ensure_owner(self) -> None:
        """As the scene controller does on the first non-Normal surface (or a woken one)."""

        from rendering.quick.surface_backdrop_owner import SurfaceBackdropOwner

        if self.owner is None:
            self.owner = SurfaceBackdropOwner(self.scene.root, screen_index=0)
        elif self.owner.parked:
            self.owner.wake()
        else:
            return
        self.host.set_surface_backdrop(self.owner.item)

    def drop_owner(self) -> None:
        """As the scene controller does when the last surface goes Normal: unbind, park."""

        if self.owner is not None and not self.owner.parked:
            self.host.set_surface_backdrop(None)
            self.owner.park()

    def set_material(self, material: str) -> None:
        """Every card takes ``material`` through the card-style projection QML reads."""

        from rendering.quick.widgets.surface_material import surface_text_color

        text = surface_text_color()
        for widget in list(self.host._live):
            item = widget.item
            item.setProperty("cardSurfaceMaterial", material)
            item.setProperty("cardSurfaceTextColor", text)
            widget._surface_material = material
        if material == "normal":
            self.drop_owner()
        else:
            self.ensure_owner()
            self.owner.set_materials(frozenset({material}))

    def start_transition(self, identity: str, source, destination, progress: float):
        """A production-resolved run of ``identity`` placed at ``progress`` of its timeline now."""

        from tools.transition_contact_sheet import production_transition_spec
        from rendering.quick.transitions.state import TransitionRun

        spec = production_transition_spec(identity)
        request = spec.build_request(runtime_generation=0, source_image=source, destination_image=destination)
        self.run_id += 1
        duration_ns = request.duration_ms * 1_000_000
        start = time.monotonic_ns() - int(progress * duration_ns)
        run = TransitionRun.start(run_id=self.run_id, request=request, start_ns=start)
        self.background.set_transition_run(run)
        if self.owner is not None:
            self.owner.set_transition_active(True)
        return run

    def frame_at(self, identity: str, source, destination, progress: float, *, refresh: bool = True):
        """The scene at ``progress`` of ``identity``; ``refresh`` False keeps the previous backdrop.

        Offscreen frames come faster than real time, so the bounded continuous refresh is
        driven explicitly: interval 0 refreshes this frame, a huge interval keeps the last one.
        """

        self.start_transition(identity, source, destination, progress)
        if self.owner is not None:
            self.owner.item.set_continuous(True, 0.0 if refresh else 1e9)
        self.render(1)
        return self.read()

    def card_boxes(self) -> list[tuple[int, int, int, int]]:
        from PySide6.QtCore import QRectF

        boxes = []
        for presentation in self.presentations:
            item = presentation.item
            rect = item.mapRectToScene(QRectF(0.0, 0.0, item.width(), item.height()))
            boxes.append((int(rect.left()) + 6, int(rect.top()) + 6, int(rect.right()) - 6, int(rect.bottom()) - 6))
        return boxes

    def close(self) -> None:
        for presentation in self.presentations:
            try:
                presentation.retire()
            except Exception:
                pass
        self.drop_owner()
        self.render(2)
        self.scene.close()


def presentation_image(path: Path, size: tuple[int, int], identity: str):
    """``path`` cover-fitted to ``size`` as the opaque detached image the runtime presents."""

    from PIL import Image, ImageOps
    from rendering.quick.image_state import PresentationImage

    image = ImageOps.fit(Image.open(path).convert("RGB"), size, Image.Resampling.LANCZOS).convert("RGBA")
    return PresentationImage(identity, str(path), (float(size[0]), float(size[1])), 1.0, size,
                             size[0] * 4, image.tobytes())


def build_cards(material_scene: MaterialScene, art: Path) -> None:
    """Real family presentations spread over the scene (busy and flat regions alike)."""

    from datetime import datetime
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.clock import (ClockPresentationConfig, ClockPresentationModel,
        ClockPresentationStyle, RetainedClockPresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    scene = material_scene.scene
    material_scene.art = art
    width, height = SCENE
    built = []
    if CARD_SET == "lists":
        # The other list-like families: Gmail, a news Feed, Steam Friend Pulse, System Stats.
        for builder in (foundry._preview_gmail, foundry._preview_feeds, foundry._preview_steam,
                        foundry._preview_system_stats):
            built.append(builder(scene, art))
        slots = ((40, 40), (width - 700, 40), (40, height - 420), (width - 560, height - 420))
        for presentation, (x, y) in zip(built, slots):
            item = presentation.item
            presentation.set_geometry(OverlayWidgetGeometry(float(x), float(y), item.width(), item.height()))
        material_scene.presentations = built
        material_scene.render(8)
        return
    for builder in (foundry._preview_weather, foundry._preview_media, foundry._preview_reddit,
                    foundry._preview_system_stats):
        built.append(builder(scene, art))
    widgets = foundry._preview_widgets(clock={"display_mode": "digital"})
    config = ClockPresentationConfig.from_widgets_mapping("clock", widgets, display_signature="preview")
    model = ClockPresentationModel(config, ClockPresentationStyle.project(config, foundry._preview_shadows()),
                                   now_provider=lambda _zone: datetime(2026, 11, 6, 21, 47, 30), parent=scene.owner)
    clock = RetainedClockPresentation(host=scene.host, model=model,
                                      geometry=OverlayWidgetGeometry(60.0, 60.0, 300, 140),
                                      display_bounds=OverlayWidgetGeometry(0.0, 0.0, *SCENE),
                                      display_identity="preview")
    foundry._place_preferred(scene, clock)
    built.append(clock)
    slots = ((40, 40), (width - 680, 40), (40, height - 330), (width - 560, height - 300),
             ((width - 300) // 2, (height - 140) // 2))
    for presentation, (x, y) in zip(built, slots):
        item = presentation.item
        presentation.set_geometry(OverlayWidgetGeometry(float(x), float(y), item.width(), item.height()))
    material_scene.presentations = built
    material_scene.render(8)


def activate_theme(name: str) -> None:
    """Make the named curated Widget Theme the process's active one (no Settings write)."""

    from ui.widget_theme_active import set_active_widget_theme
    from ui.widget_theme_io import load_widget_theme_file

    path = ROOT / "themes" / "widgets" / f"{name}.srwtheme"
    set_active_widget_theme(load_widget_theme_file(path))


# --------------------------------------------------------------------------- sheets


def settle_still(scene: MaterialScene) -> None:
    scene.render(4)


def capture_sheets(scene: MaterialScene, wallpapers: list[Path], output: Path) -> list[dict]:
    from PIL import Image, ImageDraw

    rows = []
    size = SCENE
    images = [presentation_image(path, size, f"wall-{index}") for index, path in enumerate(wallpapers)]
    for theme in (DARK_THEME, LIGHT_THEME):
        activate_theme(theme)
        rebuild_styles(scene)
        for index, image in enumerate(images):
            scene.set_wallpaper(image)
            frames = {}
            for material in MATERIALS:
                scene.set_material(material)
                settle_still(scene)
                frames[material] = scene.read()
            name = f"still_{slug(theme)}_{index}.png"
            contact(frames, output / name, f"{theme} - {wallpapers[index].name} - still")
            rows.append({"kind": "still", "theme": theme, "wallpaper": wallpapers[index].name, "path": name})
        # Mid-transition: each material through several transitions at 0.35 and 0.6.
        for identity in TRANSITIONS:
            for progress in (0.35, 0.6):
                frames = {}
                for material in MATERIALS:
                    scene.set_wallpaper(images[0])
                    scene.set_material(material)
                    settle_still(scene)
                    scene.start_transition(identity, images[0], images[1 % len(images)], 0.0)
                    scene.render(3)       # first-use programs/geometry off the measured frame
                    frames[material] = scene.frame_at(identity, images[0], images[1 % len(images)], progress)
                name = f"transition_{slug(theme)}_{identity}_{int(progress * 100)}.png"
                contact(frames, output / name, f"{theme} - {identity} at {progress:.2f}")
                rows.append({"kind": "transition", "theme": theme, "transition": identity,
                             "progress": progress, "path": name})
    return rows


def rebuild_styles(scene: MaterialScene, art: Path | None = None) -> None:
    """Re-project each card's colours from the newly active Widget Theme.

    ``art`` is the Media artwork file ``main`` wrote into the output folder (it is removed with
    the run); nothing is written to ``%TEMP%``."""

    for presentation in list(scene.presentations):
        presentation.retire()
    scene.presentations = []
    scene.drop_owner()
    scene.render(2)
    build_cards(scene, art if art is not None else scene.art)
    settle_animations(scene)


def settle_animations(scene: MaterialScene, seconds: float = 1.6) -> None:
    """Let the cards' wall-time animations (fade-ins, meter fills, media crossfades) finish,
    so frames from different runs of the tool compare pixel for pixel."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        scene.render(1)
        time.sleep(0.02)


def slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")


def contact(frames: dict, path: Path, title: str) -> None:
    """A 3x2 sheet (half resolution) plus full-resolution frames beside it."""

    from PIL import Image, ImageDraw

    first = next(iter(frames.values()))
    w, h = first.width // 2, first.height // 2
    sheet = Image.new("RGB", (w * 3, (h + 28) * 2 + 30), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 8), title, fill=(235, 235, 235))
    for index, (material, frame) in enumerate(frames.items()):
        x, y = (index % 3) * w, 30 + (index // 3) * (h + 28)
        sheet.paste(frame.resize((w, h)), (x, y + 24))
        draw.text((x + 8, y + 6), material.upper(), fill=(235, 235, 235))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    full = path.with_suffix("")
    full.mkdir(exist_ok=True)
    for material, frame in frames.items():
        frame.save(full / f"{material}.png")


# --------------------------------------------------------------------------- cadence

CADENCE_HZ = (165.0, 120.0, 60.0, 30.0, 20.0, 15.0)
CADENCE_MATERIALS = ("glass", "acrylic", "mica")
CADENCE_POINTS = (0.2, 0.35, 0.5, 0.65, 0.8)


def measure_cadence(scene: MaterialScene, wallpapers: list[Path]) -> dict:
    """Worst-case staleness error inside the cards for each refresh rate.

    For refresh rate R the backdrop is at most one interval old: the card is drawn at
    progress p over a backdrop refreshed at p - (1/R)/duration. The error is the 8-bit
    difference against a backdrop refreshed at p, inside the card rectangles only.
    """

    import numpy
    from tools.transition_contact_sheet import production_transition_spec

    images = [presentation_image(path, SCENE, f"cad-{index}") for index, path in enumerate(wallpapers[:2])]
    boxes = scene.card_boxes()
    mask = numpy.zeros((SCENE[1], SCENE[0]), dtype=bool)
    for left, top, right, bottom in boxes:
        mask[max(0, top):bottom, max(0, left):right] = True
    results: dict = {}
    for material in CADENCE_MATERIALS:
        scene.set_material(material)
        for identity in TRANSITIONS:
            duration_s = production_transition_spec(identity).duration_ms / 1000.0
            scene.set_wallpaper(images[0])
            scene.render(4)
            scene.start_transition(identity, images[0], images[1], 0.0)
            scene.render(3)
            row = {}
            for hz in CADENCE_HZ:
                step = (1.0 / hz) / duration_s
                means, p99s = [], []
                for point in CADENCE_POINTS:
                    fresh = numpy.asarray(scene.frame_at(identity, images[0], images[1], point), numpy.int16)
                    scene.frame_at(identity, images[0], images[1], max(0.0, point - step))
                    stale = numpy.asarray(scene.frame_at(identity, images[0], images[1], point, refresh=False),
                                          numpy.int16)
                    diff = numpy.abs(fresh - stale).max(axis=2)[mask]
                    means.append(float(diff.mean()))
                    p99s.append(float(numpy.percentile(diff, 99)))
                row[f"{hz:g}"] = {"mean": round(max(means), 3), "p99": round(max(p99s), 1)}
            results.setdefault(material, {})[identity] = {"duration_s": duration_s, "rates": row}
            print(material, identity, {k: v["p99"] for k, v in row.items()}, flush=True)
    return results


# --------------------------------------------------------------------------- cost


def measure_cost(scene: MaterialScene, wallpapers: list[Path], frames: int = 80) -> dict:
    """Whole-frame GPU time (GL_TIME_ELAPSED around the scene's render) per material, relative
    to Normal measured alternately beside it, on a still wallpaper with no backdrop refresh: the
    steady cost of the card quads. Five cards on the 1600x900 scene."""

    import ctypes
    from OpenGL import GL as gl

    image = presentation_image(wallpapers[0], SCENE, "cost")
    scene.set_wallpaper(image)

    def timed() -> tuple[float, float]:
        scene.scene._make_current()
        query = int(gl.glGenQueries(1)[0])
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        cpu = time.perf_counter()
        scene.scene.control.render()
        scene.scene.control.endFrame()      # the GL backend executes the recorded frame here
        cpu = time.perf_counter() - cpu
        scene.scene._make_current()
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        value = ctypes.c_uint64()
        gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
        gl.glDeleteQueries(1, [query])
        return value.value / 1e6, cpu * 1e3

    def frame_cost(material: str) -> tuple[float, float]:
        """(GPU ms, render-thread CPU ms of sync + render) for one steady frame."""
        scene.set_material(material)
        scene.render(4)              # settle: refresh once, then disarmed
        app = scene.scene.app
        app.processEvents()
        scene.scene.control.polishItems()
        cpu = time.perf_counter()
        scene.scene.control.beginFrame()
        scene.scene.control.sync()
        sync = (time.perf_counter() - cpu) * 1e3
        gpu, render_cpu = timed()
        return gpu, sync + render_cpu

    def best(material: str) -> tuple[float, float]:
        samples = [frame_cost(material) for _ in range(4)]
        return min(s[0] for s in samples), min(s[1] for s in samples)

    results = {}
    # "normal" against itself first: the floor of the alternating method (must read zero).
    for material in MATERIALS:
        normal, case = [], []
        for _ in range(frames // 8):
            normal.append(best("normal"))
            case.append(best(material))
        n_gpu = statistics.median(s[0] for s in normal)
        c_gpu = statistics.median(s[0] for s in case)
        n_cpu = statistics.median(s[1] for s in normal)
        c_cpu = statistics.median(s[1] for s in case)
        results[material] = {"normal_ms": round(n_gpu, 4), "material_ms": round(c_gpu, 4),
                             "delta_ms": round(c_gpu - n_gpu, 4),
                             "normal_cpu_ms": round(n_cpu, 4), "material_cpu_ms": round(c_cpu, 4),
                             "delta_cpu_ms": round(c_cpu - n_cpu, 4)}
        print(material, results[material], flush=True)
    return results


# --------------------------------------------------------------------------- legibility

SMALL_TEXT_PX = 18.0      # below this a run needs 4.5:1 (WCAG AA body text), at or above it 3:1


def _relative_luminance(rgb):
    import numpy

    c = numpy.asarray(rgb, numpy.float64) / 255.0
    c = numpy.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def _text_runs(scene: MaterialScene):
    from PySide6.QtCore import QRectF
    from PySide6.QtQuick import QQuickItem

    runs = []
    mains, pending = [], [scene.scene.root]
    while pending:                      # the visual tree: Repeater delegates are not QObject children
        node = pending.pop()
        children = node.childItems()
        pending.extend(children)
        if node.objectName() == "shadowedTextMain":
            mains.append(node)
    for main in mains:
        item = main.parentItem()
        if item is None or not item.isVisible() or not main.isVisible() or not str(item.property("text") or ""):
            continue
        shadow = item.findChild(QQuickItem, "shadowedTextShadow")
        rect = main.mapRectToScene(QRectF(0.0, 0.0, main.width(), main.height()))
        font = main.property("font")
        size = font.pixelSize() if font.pixelSize() > 0 else font.pointSizeF() * 96.0 / 72.0
        runs.append((item, main, shadow, rect, float(size)))
    return runs


def measure_text_legibility(scene: MaterialScene, out: Path) -> list[dict]:
    """Per text run: WCAG contrast of the run's own colour against the pixels right under its
    glyphs (the frame re-rendered with every run's glyphs and shadows hidden), p5 over the glyph
    pixels. Saves the frame; returns one row per run."""

    import numpy

    scene.render(2)
    frame = scene.read()
    frame.save(out)
    full = numpy.asarray(frame, numpy.int16)
    runs = _text_runs(scene)
    saved = []
    for _item, main, shadow, _rect, _size in runs:
        saved.append((main.opacity(), shadow.opacity() if shadow is not None else None))
        main.setOpacity(0.0)
        if shadow is not None:
            shadow.setOpacity(0.0)
    scene.render(2)
    bare = numpy.asarray(scene.read(), numpy.int16)
    for (item, main, shadow, _rect, _size), (main_opacity, shadow_opacity) in zip(runs, saved):
        main.setOpacity(main_opacity)
        if shadow is not None:
            shadow.setOpacity(shadow_opacity)
    scene.render(1)
    rows = []
    height, width = full.shape[:2]
    for item, _main, _shadow, rect, size in runs:
        left, top = max(0, int(rect.left())), max(0, int(rect.top()))
        right, bottom = min(width, int(rect.right()) + 1), min(height, int(rect.bottom()) + 1)
        if right - left < 2 or bottom - top < 2:
            continue
        mask = numpy.abs(full[top:bottom, left:right] - bare[top:bottom, left:right]).max(axis=2) > 24
        if mask.sum() < 6:
            continue
        colour = item.property("color")
        text_l = float(_relative_luminance([colour.red(), colour.green(), colour.blue()]))
        back_l = _relative_luminance(bare[top:bottom, left:right][mask])
        hi = numpy.maximum(back_l, text_l)
        lo = numpy.minimum(back_l, text_l)
        contrast = (hi + 0.05) / (lo + 0.05)
        rows.append({"text": str(item.property("text"))[:40], "size_px": round(size, 1),
                     "small": size < SMALL_TEXT_PX, "rect": [left, top, right, bottom],
                     "colour": colour.name(), "p5": round(float(numpy.percentile(contrast, 5)), 2),
                     "min": round(float(contrast.min()), 2), "median": round(float(numpy.median(contrast)), 2)})
    return rows


def capture_legibility(scene: MaterialScene, wallpapers: list[Path], output: Path, themes=None) -> dict:
    """Light and dark themes (or ``themes``), every wallpaper, every material: frames plus
    per-run contrast."""

    report: dict = {}
    images = [presentation_image(path, SCENE, f"leg-{index}") for index, path in enumerate(wallpapers)]
    for theme in (themes or (LIGHT_THEME, DARK_THEME)):
        activate_theme(theme)
        rebuild_styles(scene)
        for index, image in enumerate(images):
            scene.set_wallpaper(image)
            for material in MATERIALS:
                scene.set_material(material)
                scene.render(4)
                folder = output / slug(theme) / wallpapers[index].stem
                folder.mkdir(parents=True, exist_ok=True)
                rows = measure_text_legibility(scene, folder / f"{material}.png")
                report.setdefault(slug(theme), {}).setdefault(wallpapers[index].stem, {})[material] = rows
                small = [row["p5"] for row in rows if row["small"]]
                large = [row["p5"] for row in rows if not row["small"]]
                print(f"{theme[:14]:14s} {wallpapers[index].stem:12s} {material:8s} runs {len(rows):3d}  "
                      f"small p5 min {min(small) if small else 0:5.2f}  large p5 min {min(large) if large else 0:5.2f}",
                      flush=True)
    boxes = scene.card_boxes()
    report["card_boxes"] = boxes
    return report


def compare_legibility(before: Path, after: Path, output: Path) -> dict:
    """Before/after crops at 1x and 3x for every material on the light theme's busiest
    wallpaper: the smallest text run that was worst before, and a card edge over the busiest
    region, each labelled with its contrast. Also a per-material summary of both runs."""

    from PIL import Image, ImageDraw

    old = json.loads((before / "report.json").read_text(encoding="utf-8"))["legibility"]
    new = json.loads((after / "report.json").read_text(encoding="utf-8"))["legibility"]
    summary: dict = {}
    for theme, walls in new.items():
        if theme == "card_boxes":
            continue
        for material in MATERIALS:
            row = {}
            for tag, data in (("before", old), ("after", new)):
                runs = [run for wall, rows in data[theme].items() for run in rows[material]]
                row[tag] = {"small_p5_min": min(r["p5"] for r in runs if r["small"]),
                            "large_p5_min": min(r["p5"] for r in runs if not r["small"])}
            summary.setdefault(theme, {})[material] = row
    theme = slug(LIGHT_THEME)
    # The busiest wallpaper: where Glass small text was worst before.
    wall = min(old[theme], key=lambda w: min(r["p5"] for r in old[theme][w]["glass"] if r["small"]))
    boxes = new["card_boxes"]
    reddit = boxes[2]
    edge = (reddit[2] - 34, reddit[1] + 40, reddit[2] + 22, reddit[1] + 110)
    tiles = []
    for material in MATERIALS:
        runs_before = {r["text"] + str(r["rect"]): r for r in old[theme][wall][material]}
        runs_after = {r["text"] + str(r["rect"]): r for r in new[theme][wall][material]}
        small = [r for r in old[theme][wall][material] if r["small"]]
        worst = min(small, key=lambda r: r["p5"])
        key = worst["text"] + str(worst["rect"])
        left, top, right, bottom = worst["rect"]
        glyphs = (left - 8, top - 6, min(right, left + 150) + 8, bottom + 6)
        images = {tag: Image.open(folder / theme / wall / f"{material}.png").convert("RGB")
                  for tag, folder in (("before", before), ("after", after))}
        label = (f"{material.upper()}  '{worst['text'][:22]}' {worst['size_px']:.0f}px  p5 "
                 f"{worst['p5']:.2f} -> {runs_after.get(key, worst)['p5']:.2f}")
        tiles.append((label, {tag: (img.crop(glyphs), img.crop(edge)) for tag, img in images.items()}))
    scale = 3
    rows = []
    for label, crops in tiles:
        text_w, text_h = crops["before"][0].size
        edge_w, edge_h = crops["before"][1].size
        width = (text_w + edge_w) * (1 + scale) * 2 + 60
        height = 18 + max(text_h, edge_h) * scale
        tile = Image.new("RGB", (width, height), (18, 18, 20))
        draw = ImageDraw.Draw(tile)
        draw.text((4, 2), label, fill=(235, 235, 235))
        x = 4
        for tag in ("before", "after"):
            text_crop, edge_crop = crops[tag]
            for crop in (text_crop, edge_crop):
                tile.paste(crop, (x, 18))
                x += crop.width + 4
                big = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
                tile.paste(big, (x, 18))
                x += big.width + 8
            draw.text((x - 40, 2), tag.upper(), fill=(255, 220, 90))
            x += 14
        rows.append(tile)
    sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height + 6 for r in rows) + 24), (10, 10, 12))
    ImageDraw.Draw(sheet).text((6, 4), f"{LIGHT_THEME} on {wall}: smallest worst text and a card edge, "
                                       f"1x and 3x, before | after", fill=(235, 235, 235))
    y = 24
    for tile in rows:
        sheet.paste(tile, (0, y))
        y += tile.height + 6
    output.mkdir(parents=True, exist_ok=True)
    sheet.save(output / "legibility_before_after.png")
    (output / "legibility_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- style pass

STYLE_REGION_NAMES = ("mediaControlsRow", "mediaSystemMuteButton", "weatherDetailsRow", "weatherForecastText",
                      "redditPostRow_0", "redditPostRow_1", "redditPostRow_2", "mediaTrackMetadata",
                      "systemStatsPresentation", "weatherPresentation", "mediaPresentation",
                      "redditPresentation", "clockPresentation")


def named_rects(scene: MaterialScene, names=STYLE_REGION_NAMES) -> dict:
    """Scene rectangles of the named items (the visual tree, so Repeater delegates count)."""

    from PySide6.QtCore import QRectF

    wanted = set(names)
    found: dict = {}
    pending = [scene.scene.root]
    while pending:
        node = pending.pop()
        pending.extend(node.childItems())
        name = node.objectName()
        if name in wanted and name not in found and node.isVisible():
            rect = node.mapRectToScene(QRectF(0.0, 0.0, node.width(), node.height()))
            found[name] = [round(rect.left(), 2), round(rect.top(), 2), round(rect.right(), 2),
                           round(rect.bottom(), 2)]
    for presentation in scene.presentations:
        item = presentation.item
        rect = item.mapRectToScene(QRectF(0.0, 0.0, item.width(), item.height()))
        found.setdefault(item.objectName() or type(presentation).__name__,
                         [rect.left(), rect.top(), rect.right(), rect.bottom()])
    return found


def capture_style(scene: MaterialScene, wallpapers: list[Path], output: Path,
                  themes=(None, None), transition: str = "wipe", progress: float = 0.5) -> dict:
    """Full-resolution frames for the style pass: each theme, each wallpaper, each material,
    still, plus one mid-transition frame per material; and the named item rectangles."""

    report: dict = {}
    images = [presentation_image(path, SCENE, f"style-{index}") for index, path in enumerate(wallpapers)]
    for theme in (themes[0] or DARK_THEME, themes[1] or LIGHT_THEME):
        activate_theme(theme)
        rebuild_styles(scene)
        for index, image in enumerate(images):
            scene.set_wallpaper(image)
            for material in MATERIALS:
                scene.set_material(material)
                settle_still(scene)
                folder = output / slug(theme) / wallpapers[index].stem
                folder.mkdir(parents=True, exist_ok=True)
                scene.read().save(folder / f"{material}.png")
        for material in MATERIALS:
            scene.set_wallpaper(images[0])
            scene.set_material(material)
            settle_still(scene)
            scene.start_transition(transition, images[0], images[1 % len(images)], 0.0)
            scene.render(3)
            frame = scene.frame_at(transition, images[0], images[1 % len(images)], progress)
            folder = output / slug(theme) / f"transition_{transition}"
            folder.mkdir(parents=True, exist_ok=True)
            frame.save(folder / f"{material}.png")
        scene.set_material("normal")
        report[slug(theme)] = named_rects(scene)
        print("style", theme, flush=True)
    (output / "regions.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def capture_theme_sheet(scene: MaterialScene, wallpapers: list[Path], output: Path, themes) -> list[Path]:
    """One contact sheet per wallpaper: every named Widget Theme on its own material (the
    "Theme" baseline), a labelled tile each, plus the full frames."""

    from PIL import Image, ImageDraw
    from ui.widget_theme_io import load_widget_theme_file
    from rendering.quick.widgets.surface_material import theme_surface_material

    images = [presentation_image(path, SCENE, f"sheet-{index}") for index, path in enumerate(wallpapers)]
    frames: dict = {}
    for theme in themes:
        spec = load_widget_theme_file(ROOT / "themes" / "widgets" / f"{theme}.srwtheme")
        activate_theme(theme)
        rebuild_styles(scene)
        material = theme_surface_material(spec)
        for index, image in enumerate(images):
            scene.set_wallpaper(image)
            scene.set_material(material)
            settle_still(scene)
            frame = scene.read()
            folder = output / "frames" / slug(theme)
            folder.mkdir(parents=True, exist_ok=True)
            frame.save(folder / f"{wallpapers[index].stem}.png")
            frames.setdefault(index, []).append((f"{theme}  ({material})", frame))
        print("sheet", theme, material, flush=True)
    sheets = []
    columns = 3
    for index, tiles in frames.items():
        w, h = SCENE[0] * 2 // 5, SCENE[1] * 2 // 5
        rows = (len(tiles) + columns - 1) // columns
        sheet = Image.new("RGB", (w * columns, (h + 22) * rows + 26), (14, 14, 16))
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 6), f"{wallpapers[index].name}: each theme on its own material", fill=(235, 235, 235))
        for n, (label, frame) in enumerate(tiles):
            x, y = (n % columns) * w, 26 + (n // columns) * (h + 22)
            draw.text((x + 6, y + 4), label, fill=(255, 220, 90))
            sheet.paste(frame.resize((w, h)), (x, y + 20))
        path = output / f"theme_sheet_{wallpapers[index].stem}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compare-legibility", type=Path, nargs=2, metavar=("BEFORE", "AFTER"),
                        help="compose before/after crops and the contrast summary from two --legibility runs")
    parser.add_argument("--wallpapers", type=Path, nargs="+",
                        help="wallpaper files (the first two also drive the transitions)")
    parser.add_argument("--output", type=artifact_paths.evidence_arg,
                        default=artifact_paths.default_evidence("widgets", "surface_material"))
    parser.add_argument("--sheets", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="one still per material, for a quick look")
    parser.add_argument("--cadence", action="store_true", help="staleness error per backdrop refresh rate")
    parser.add_argument("--cost", action="store_true", help="steady whole-frame GPU per material vs Normal")
    parser.add_argument("--legibility", action="store_true",
                        help="per text run contrast against its local backdrop, light and dark themes")
    parser.add_argument("--theme-sheet", nargs="+", metavar="THEME",
                        help="contact sheets: each named Widget Theme on its own material, per wallpaper")
    parser.add_argument("--legibility-themes", nargs="+", metavar="THEME",
                        help="Widget Theme names for --legibility (default: the light and dark pair)")
    parser.add_argument("--style", action="store_true",
                        help="full frames per theme/wallpaper/material plus a mid-transition frame, and item rects")
    parser.add_argument("--dpr", type=float, default=1.0,
                        help="device pixel ratio of the hidden scene (1.6 = 2560x1440, 2.4 = 3840x2160)")
    parser.add_argument("--card-set", choices=("main", "lists"), default="main",
                        help="main: Weather/Media/Reddit/Stats/Clock; lists: Gmail/Feed/Steam/Stats")
    parser.add_argument("--themes", nargs=2, metavar=("DARK", "LIGHT"),
                        help="Widget Theme names for --style (default: Default Dark, Polished Chrome)")
    args = parser.parse_args(argv)
    evidence_media.redirect_output(args, "output", "surface_material_capture")
    global CARD_SET
    CARD_SET = args.card_set
    if args.compare_legibility:
        summary = compare_legibility(*args.compare_legibility, args.output)
        print(json.dumps(summary, indent=1))
        return 0
    if not args.wallpapers:
        parser.error("--wallpapers is required")

    from PySide6.QtGui import QGuiApplication
    from rendering.quick.bootstrap import configure_quick_graphics

    if os.environ.get("QT_QPA_PLATFORM", "").lower() not in ("", "windows"):
        raise SystemExit("needs the Windows QPA (hidden GL); nothing is ever shown")
    configure_quick_graphics(reason="surface-material-capture")
    app = QGuiApplication(["surface-material-capture"])
    del app
    from tools import onboarding_preview_foundry as foundry

    args.output.mkdir(parents=True, exist_ok=True)
    # The preview builders write their fixture images (avatars, stories) beside the art: keep them
    # all in one folder that the run removes.
    fixtures = args.output / "_fixtures"
    fixtures.mkdir(exist_ok=True)
    art = foundry._gradient_art(fixtures / "_media_art.png", (480, 480), ("#27336e", "#e7678a"), 1)
    scene = MaterialScene(*SCENE, dpr=args.dpr)
    report ={"scene": list(SCENE), "wallpapers": [p.name for p in args.wallpapers]}
    try:
        activate_theme(DARK_THEME)
        build_cards(scene, art)
        if args.smoke:
            image = presentation_image(args.wallpapers[0], SCENE, "smoke")
            scene.set_wallpaper(image)
            frames = {}
            for material in MATERIALS:
                scene.set_material(material)
                settle_still(scene)
                frames[material] = scene.read()
            contact(frames, args.output / "smoke.png", "smoke")
        if args.legibility:
            report["legibility"] = capture_legibility(scene, list(args.wallpapers), args.output,
                                                      themes=args.legibility_themes)
        if args.cost:
            report["cost"] = measure_cost(scene, list(args.wallpapers))
        if args.cadence:
            report["cadence"] = measure_cadence(scene, list(args.wallpapers))
        if args.sheets:
            report["sheets"] = capture_sheets(scene, list(args.wallpapers), args.output)
        if args.theme_sheet:
            report["theme_sheet"] = [str(p) for p in capture_theme_sheet(scene, list(args.wallpapers),
                                                                          args.output, args.theme_sheet)]
        if args.style:
            report["style"] = capture_style(scene, list(args.wallpapers), args.output,
                                            themes=tuple(args.themes) if args.themes else (None, None))
    finally:
        scene.close()
        import shutil

        shutil.rmtree(fixtures, ignore_errors=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
