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

MATERIALS = ("normal", "acrylic", "glass", "frosted", "mica", "smoked")
SCENE = (1600, 900)
# Several transitions, including 3D ones (Block Spins, Glass Shatter, Cube Turn, Page Curl).
TRANSITIONS = ("wipe", "slide", "block_spins", "glass_shatter", "cube_turn", "page_curl")
LIGHT_THEME = "Polished Chrome [Single]"
DARK_THEME = "Default Dark"


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
    width, height = SCENE
    built = []
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
    slots = ((40, 40), (width - 640, 40), (40, height - 330), (width - 560, height - 300),
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
                    scene.start_transition(identity, images[0], images[1 % len(images)], progress)
                    scene.render(1)
                    frames[material] = scene.read()
                name = f"transition_{slug(theme)}_{identity}_{int(progress * 100)}.png"
                contact(frames, output / name, f"{theme} - {identity} at {progress:.2f}")
                rows.append({"kind": "transition", "theme": theme, "transition": identity,
                             "progress": progress, "path": name})
    return rows


def rebuild_styles(scene: MaterialScene) -> None:
    """Re-project each card's colours from the newly active Widget Theme."""

    from tools import onboarding_preview_foundry as foundry

    for presentation in list(scene.presentations):
        presentation.retire()
    scene.presentations = []
    scene.drop_owner()
    scene.render(2)
    art = foundry._gradient_art(Path(os.environ.get("TEMP", ".")) / "surface_material_art.png",
                                (480, 480), ("#27336e", "#e7678a"), 1)
    build_cards(scene, art)


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


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wallpapers", type=Path, nargs="+", required=True,
                        help="wallpaper files (the first two also drive the transitions)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sheets", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="one still per material, for a quick look")
    args = parser.parse_args(argv)

    from PySide6.QtGui import QGuiApplication
    from rendering.quick.bootstrap import configure_quick_graphics

    if os.environ.get("QT_QPA_PLATFORM", "").lower() not in ("", "windows"):
        raise SystemExit("needs the Windows QPA (hidden GL); nothing is ever shown")
    configure_quick_graphics(reason="surface-material-capture")
    app = QGuiApplication(["surface-material-capture"])
    del app
    from tools import onboarding_preview_foundry as foundry

    args.output.mkdir(parents=True, exist_ok=True)
    art = foundry._gradient_art(args.output / "_media_art.png", (480, 480), ("#27336e", "#e7678a"), 1)
    scene = MaterialScene(*SCENE)
    report = {"scene": list(SCENE), "wallpapers": [p.name for p in args.wallpapers]}
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
        if args.sheets:
            report["sheets"] = capture_sheets(scene, list(args.wallpapers), args.output)
    finally:
        scene.close()
        (args.output / "_media_art.png").unlink(missing_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
