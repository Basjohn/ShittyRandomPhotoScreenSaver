"""Every card on a surface material, one at a time, on the production scene; never on screen.

The card-surface acceptance pass (Docs/Architecture/Card_Surface_Materials.md 3.3, 3.4): each
widget family and each carded Visualizer mode is placed alone on a real wallpaper in the hidden
production ``DisplayScene`` (``tools/surface_material_capture.MaterialScene``: ``QQuickRenderControl``
into a hidden GL texture, Windows QPA, no window is shown or mapped) and captured on Normal and
the given materials. Each capture is the card cropped with its shadow margin, a lossless PNG.

    python tools/card_surface_capture.py --label before [--materials normal glass acrylic]
    python tools/card_surface_capture.py --sheet BEFORE_DIR AFTER_DIR --label sheets

``--sheet`` composes one contact sheet per widget (before | after, a row per material) from two
capture runs. Output goes through ``tools/artifact_paths.py``
(``.artifacts/evidence/widgets/card_surfaces/<date>_<label>/``).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402

DEFAULT_WALLPAPER = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET\859804.png")
DEFAULT_THEME = "Default Dark [Single]"
ORIGIN = (180.0, 140.0)
MARGIN = 28
# Carded Visualizer modes (the frameless 3D modes have no card).
VISUALIZER_MODES = ("spectrum", "devcurve", "oscilloscope", "bubble", "shockwave_grid", "extruded_bubble",
                    "waveform_ribbon")
VISUALIZER_SIZE = (600, 250)


def _clock(scene, art, *, mode: str):
    from datetime import datetime
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.clock import (ClockPresentationConfig, ClockPresentationModel,
        ClockPresentationStyle, RetainedClockPresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    widgets = foundry._preview_widgets(clock={"display_mode": mode, "show_timezone": True})
    config = ClockPresentationConfig.from_widgets_mapping("clock", widgets, display_signature="preview")
    model = ClockPresentationModel(config, ClockPresentationStyle.project(config, foundry._preview_shadows()),
                                   now_provider=lambda _zone: datetime(2026, 11, 6, 21, 47, 30), parent=scene.owner)
    clock = RetainedClockPresentation(host=scene.host, model=model, geometry=OverlayWidgetGeometry(*ORIGIN, 300, 300),
                                      display_bounds=OverlayWidgetGeometry(0.0, 0.0, 1600.0, 900.0),
                                      display_identity="preview")
    foundry._place_preferred(scene, clock)
    return clock


def _steam_art(path: Path, accent: str, size=(360, 504)) -> "object":
    from PySide6.QtGui import QImage
    from tools import onboarding_preview_foundry as foundry

    foundry._gradient_art(path, size, (accent, "#10141c"), 2)
    return QImage(str(path))


def _abandonment(scene, art):
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.abandonment_issues import (AbandonmentIssuesPresentationConfig,
        AbandonmentIssuesPresentationModel, AbandonmentIssuesPresentationStyle,
        RetainedAbandonmentIssuesPresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from widgets.steam_abandonment_preparation import AbandonmentPreparedPresentation
    from widgets.steam_card_models import SteamCardField, SteamCardViewModel

    config = AbandonmentIssuesPresentationConfig.from_widgets_mapping(foundry._preview_widgets(abandonment_issues={}))
    model = AbandonmentIssuesPresentationModel(
        config, AbandonmentIssuesPresentationStyle.project(config, foundry._preview_shadows()), parent=scene.owner)
    presentation = RetainedAbandonmentIssuesPresentation(host=scene.host, model=model,
                                                         geometry=OverlayWidgetGeometry(*ORIGIN, 600, 331),
                                                         fade_opacity=1.0)
    presentation.activate()
    card = SteamCardViewModel(
        card_id="abandonment_issues", appid=753640, header="Abandonment Issues", title="Outer Wilds",
        subtitle="You Don't Even Remember Buying This One Do You?", metric_label="Last Visit",
        metric_value="18 MONTHS AGO", status="BACKLOG 03/19", accent="#de9d58",
        fields=(SteamCardField("playtime", "Played", "18h"),
                SteamCardField("achievements", "Achievements", "7 / 31"),
                SteamCardField("last_unlock", "Last Unlock", "14 MONTHS AGO"),
                SteamCardField("last_played", "Last Played", "14/02/2025")))
    path = art.parent / "abandonment_art.png"
    image = _steam_art(path, "#8e4f2d")
    model.on_abandonment_presentation(AbandonmentPreparedPresentation(
        model=card, artwork=image, artwork_identity=str(path), desaturation_bucket=0), animate=False)
    return presentation


def _achievement(scene, art):
    from tools import onboarding_preview_foundry as foundry
    from rendering.quick.widgets.achievement_pulse import (AchievementPulsePresentationConfig,
        AchievementPulsePresentationModel, AchievementPulsePresentationStyle, RetainedAchievementPulsePresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from widgets.steam_achievement_preparation import AchievementPulsePreparedPresentation
    from widgets.steam_card_models import build_mock_steam_view_model

    config = AchievementPulsePresentationConfig.from_widgets_mapping(foundry._preview_widgets(achievement_pulse={}))
    model = AchievementPulsePresentationModel(
        config, AchievementPulsePresentationStyle.project(config, foundry._preview_shadows()), parent=scene.owner)
    presentation = RetainedAchievementPulsePresentation(host=scene.host, model=model,
                                                        geometry=OverlayWidgetGeometry(*ORIGIN, 600, 334),
                                                        fade_opacity=1.0)
    presentation.activate()
    base = build_mock_steam_view_model("achievement_pulse")
    path = art.parent / "achievement_art.png"
    latest = art.parent / "achievement_latest.png"
    image = _steam_art(path, "#357ea7")
    latest_image = _steam_art(latest, "#be802d", size=(720, 344))
    model.on_achievement_presentation(AchievementPulsePreparedPresentation(
        model=base, artwork=image, artwork_identity=str(path), artwork_key=f"{base.appid or 0}:capture",
        latest_artwork=latest_image, latest_artwork_identity=str(latest), latest_artwork_key="capture-unlock"),
        animate=False)
    return presentation


def _games_you_follow(scene, art):
    from dataclasses import replace
    from tools import onboarding_preview_foundry as foundry
    from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsStory
    from rendering.quick.widgets.games_you_follow import (FollowedPresentationConfig,
        GamesYouFollowPresentationModel, RetainedGamesYouFollowPresentation, followed_visual_style)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    widgets = foundry._preview_widgets(steam_progress={})
    config = FollowedPresentationConfig.from_widgets_mapping(widgets)
    visual = followed_visual_style(widgets, foundry._preview_shadows())
    model = GamesYouFollowPresentationModel(config, runtime_generation=1, visual_style=visual, widgets=widgets)
    model.set_runtime_service(foundry._Lease())
    titles = (("Hades II", "Patch 1.2: The Night Market opens"), ("Outer Wilds", "Anniversary soundtrack"),
              ("Limbus Company", "Season 6 roadmap"), ("Factorio", "Space Age hotfix 2.0.21"))
    paths = []
    for index in range(len(titles)):
        path = foundry._gradient_art(art.parent / f"followed_{index}.png", (460, 215),
                                     (("#244c7e", "#65c5e8"), ("#663f8c", "#e67d9f"), ("#2c706d", "#c6dc72"),
                                      ("#8a4b2a", "#f2b26b"))[index], index)
        paths.append(str(path))
    snapshot = FollowedNewsSnapshot("available", tuple(FollowedNewsStory(
        appid=10000 + n, gid=str(90000 + n), title=title, published_at=1762400000 - 3600 * n, feed_name="News",
        action_available=True, article_url=f"https://store.steampowered.com/news/app/{10000 + n}/view/{80000 + n}",
        game_name=game, preview="Fixture preview text for the capture.")
        for n, (game, title) in enumerate(titles)), followed_count=42, checked_count=4)
    snapshot = replace(snapshot, artwork_paths=tuple(paths))
    presentation = RetainedGamesYouFollowPresentation(
        host=scene.host, model=model, geometry=OverlayWidgetGeometry(*ORIGIN, config.base_width, config.base_height),
        card_style=visual.card_style)
    presentation.activate(object())
    model.on_games_followed_runtime_snapshot(snapshot)
    return presentation


def widget_builders():
    from tools import onboarding_preview_foundry as foundry

    def feeds(scene, art):
        return foundry._preview_feeds(scene, art)

    return {
        "media": foundry._preview_media,
        "weather": foundry._preview_weather,
        "reddit": foundry._preview_reddit,
        "gmail": foundry._preview_gmail,
        "feeds_world_news": feeds,
        "friend_pulse": foundry._preview_steam,
        "system_stats": foundry._preview_system_stats,
        "clock_digital": lambda scene, art: _clock(scene, art, mode="digital"),
        "clock_analog": lambda scene, art: _clock(scene, art, mode="analog"),
        "games_you_follow": _games_you_follow,
        "abandonment_issues": _abandonment,
        "achievement_pulse": _achievement,
    }


def _settle(material_scene, seconds: float = 1.4) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        material_scene.render(1)
        time.sleep(0.02)


def _crop(frame, rect, dpr: float):
    k = dpr
    left, top = int(rect.left() * k) - MARGIN, int(rect.top() * k) - MARGIN
    right, bottom = int(rect.right() * k) + MARGIN, int(rect.bottom() * k) + MARGIN
    return frame.crop((max(0, left), max(0, top), min(frame.width, right), min(frame.height, bottom)))


def capture_widgets(material_scene, art: Path, materials, output: Path, only=None) -> dict:
    from PySide6.QtCore import QRectF
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    report = {}
    for name, builder in widget_builders().items():
        if only and name not in only:
            continue
        try:
            presentation = builder(material_scene.scene, art)
        except Exception as error:  # a fixture the family no longer accepts: report, keep going
            report[name] = f"skipped: {type(error).__name__}: {error}"
            print("skip", name, error, flush=True)
            continue
        material_scene.presentations = [presentation]
        item = presentation.item
        presentation.set_geometry(OverlayWidgetGeometry(*ORIGIN, item.width(), item.height()))
        _settle(material_scene)
        rect = item.mapRectToScene(QRectF(0.0, 0.0, item.width(), item.height()))
        for material in materials:
            material_scene.set_material(material)
            _settle(material_scene, 0.5)
            _crop(material_scene.read(), rect, material_scene.scene.dpr).save(output / f"{name}__{material}.png")
        material_scene.set_material("normal")
        presentation.retire()
        material_scene.presentations = []
        material_scene.render(3)
        report[name] = "ok"
        print("widget", name, flush=True)
    return report


def capture_visualizers(material_scene, art: Path, materials, output: Path, *, fill_variants: bool) -> dict:
    """The real Visualizer card shell in the scene, each mode's canonical render composited inside
    (the mode's pixels sit above the card fill, so the composite is what the display shows)."""

    from PIL import Image
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor
    from PySide6.QtQuick import QQuickItem
    from tools import onboarding_preview_foundry as foundry
    from widgets.spotify_visualizer.presentation_geometry import VisualizerShellPolicy

    scene = material_scene.scene
    report = {}
    width, height = VISUALIZER_SIZE
    for mode in VISUALIZER_MODES:
        bars_path = art.parent / f"{mode}_bars.png"
        try:
            snapshot = foundry._render_spectrum_preview(bars_path, width=width, height=height, mode=mode)
        except Exception as error:
            report[mode] = f"skipped: {type(error).__name__}: {error}"
            print("skip", mode, error, flush=True)
            continue
        presentation = snapshot.presentation
        style = presentation.shell_style
        loader = scene.find("visualizerPresentationLoader")
        loader.setProperty("active", True)
        root = loader.property("item")
        if not isinstance(root, QQuickItem):
            raise RuntimeError("VisualizerPresentation.qml did not load")
        loader.setX(ORIGIN[0]); loader.setY(ORIGIN[1]); loader.setWidth(width); loader.setHeight(height)
        root.setX(0.0); root.setY(0.0); root.setWidth(width); root.setHeight(height)

        def color(value):
            return QColor(*(int(channel) for channel in value))

        root.setProperty("cardShellEnabled", presentation.shell_policy is VisualizerShellPolicy.CARD)
        authored_fill = color(style["background_color"])
        root.setProperty("cardBackgroundColor", authored_fill)
        root.setProperty("cardBorderColor", color(style["border_color"]))
        root.setProperty("cardBorderWidth", presentation.border_width)
        root.setProperty("cardCornerRadius", float(style["corner_radius"]))
        root.setProperty("cardShadowEnabled", bool(style["shadow_enabled"]))
        root.setProperty("cardShadowColor", color(style["shadow_color"]))
        root.setProperty("cardShadowBlur", float(style["shadow_blur"]))
        root.setProperty("presentationActive", True)
        rect = root.mapRectToScene(QRectF(0.0, 0.0, width, height))
        k = scene.dpr
        with Image.open(bars_path) as bars:
            bars = bars.convert("RGBA").resize((round(width * k), round(height * k)), Image.Resampling.LANCZOS)
        coverage = _interior_coverage(bars, presentation.border_width * k)
        variants = [(material, None) for material in materials]
        if fill_variants:
            variants += [("glass", "tint_capped"), ("glass", "theme_tint")]
        for material, variant in variants:
            fill = authored_fill
            if variant == "theme_tint":
                fill = _theme_card_colour()
            elif variant == "tint_capped":
                fill = QColor(authored_fill)
                fill.setAlpha(min(fill.alpha(), 64))
            root.setProperty("cardBackgroundColor", fill)
            material_scene.set_material(material)
            # The Visualizer card's material and backdrop (absent on main: Normal fill).
            root.setProperty("cardSurfaceMaterial", material)
            root.setProperty("cardSurfaceBackdrop",
                             material_scene.owner.item if material != "normal" and material_scene.owner else None)
            _settle(material_scene, 0.6)
            frame = material_scene.read().convert("RGBA")
            frame.alpha_composite(bars, (int(rect.left() * k), int(rect.top() * k)))
            suffix = material if variant is None else f"{material}_{variant}"
            _crop(frame, rect, k).convert("RGB").save(output / f"visualizer_{mode}__{suffix}.png")
        root.setProperty("cardSurfaceMaterial", "normal")
        root.setProperty("cardSurfaceBackdrop", None)
        root.setProperty("cardBackgroundColor", authored_fill)
        material_scene.set_material("normal")
        loader.setProperty("active", False)
        material_scene.render(3)
        report[mode] = {"interior_coverage": coverage}
        print("visualizer", mode, coverage, flush=True)
    return report


def _interior_coverage(bars, inset: float) -> float:
    """Share of the card interior the mode's own pixels cover opaquely (alpha >= 250)."""

    import numpy

    alpha = numpy.asarray(bars.getchannel("A"))
    pad = int(round(inset)) + 2
    inner = alpha[pad:alpha.shape[0] - pad, pad:alpha.shape[1] - pad]
    return round(float((inner >= 250).mean()), 4)


def _theme_card_colour():
    from PySide6.QtGui import QColor
    from ui.settings_theme_spec import Rgba
    from ui.widget_theme_active import get_active_widget_theme
    from ui.widget_visual_roles import resolve_widget_visual_color

    rgba = resolve_widget_visual_color(get_active_widget_theme(), "card.surface",
                                       fallback=Rgba(16, 16, 16, 179)).color.as_tuple()
    return QColor(*rgba)


# --------------------------------------------------------------------------- sheets


def compose_sheets(before: Path, after: Path, output: Path) -> list[Path]:
    from PIL import Image, ImageDraw

    groups: dict[str, list[str]] = {}
    for path in sorted(after.glob("*__*.png")):
        name, suffix = path.stem.split("__", 1)
        groups.setdefault(name, []).append(suffix)
    sheets = []
    for name, suffixes in groups.items():
        rows = []
        for suffix in suffixes:
            pair = []
            for folder in (before, after):
                candidate = folder / f"{name}__{suffix}.png"
                pair.append(Image.open(candidate).convert("RGB") if candidate.is_file() else None)
            rows.append((suffix, pair))
        cell_w = max(img.width for _s, pair in rows for img in pair if img is not None)
        cell_h = max(img.height for _s, pair in rows for img in pair if img is not None)
        gap, head = 12, 26
        sheet = Image.new("RGB", (cell_w * 2 + gap * 3, head + (cell_h + head) * len(rows) + gap), (16, 16, 18))
        draw = ImageDraw.Draw(sheet)
        draw.text((gap, 6), f"{name}: before (main) | after", fill=(235, 235, 235))
        for row, (suffix, pair) in enumerate(rows):
            y = head + row * (cell_h + head)
            for column, image in enumerate(pair):
                x = gap + column * (cell_w + gap)
                draw.text((x, y + 6), f"{('BEFORE', 'AFTER')[column]}  {suffix}", fill=(255, 220, 90))
                if image is None:
                    draw.text((x, y + 30), "(not captured)", fill=(200, 120, 120))
                else:
                    sheet.paste(image, (x, y + head - 4))
        path = output / f"sheet_{name}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="run")
    parser.add_argument("--output", type=artifact_paths.evidence_arg, default=None)
    parser.add_argument("--wallpaper", type=Path, default=DEFAULT_WALLPAPER)
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--materials", nargs="+", default=["normal", "glass"])
    parser.add_argument("--visualizer-materials", nargs="+", default=["normal", "glass", "acrylic"])
    parser.add_argument("--only", nargs="+", help="widget names (or 'visualizer') to capture")
    parser.add_argument("--fill-variants", action="store_true",
                        help="also capture the Visualizer fill/material combination candidates")
    parser.add_argument("--sheet", type=Path, nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args(argv)
    output = args.output or artifact_paths.evidence_dir("widgets", "card_surfaces", args.label)
    output.mkdir(parents=True, exist_ok=True)
    if args.sheet:
        for path in compose_sheets(*args.sheet, output):
            print(path)
        return 0

    from PySide6.QtGui import QGuiApplication
    from rendering.quick.bootstrap import configure_quick_graphics

    if os.environ.get("QT_QPA_PLATFORM", "").lower() not in ("", "windows"):
        raise SystemExit("needs the Windows QPA (hidden GL); nothing is ever shown")
    configure_quick_graphics(reason="card-surface-capture")
    app = QGuiApplication(["card-surface-capture"])
    del app
    from tools import onboarding_preview_foundry as foundry
    from tools import surface_material_capture as smc

    with artifact_paths.scratch("card_surface_capture") as scratch:
        art = foundry._gradient_art(scratch / "media_art.png", (480, 480), ("#27336e", "#e7678a"), 1)
        smc.activate_theme(args.theme)
        material_scene = smc.MaterialScene(*smc.SCENE)
        report = {"theme": args.theme, "wallpaper": args.wallpaper.name, "materials": args.materials}
        try:
            material_scene.set_wallpaper(smc.presentation_image(args.wallpaper, smc.SCENE, "card-surfaces"))
            material_scene.render(4)
            only = set(args.only or ())
            widgets_only = only - {"visualizer"}
            if not only or widgets_only:
                report["widgets"] = capture_widgets(material_scene, art, args.materials, output, widgets_only)
            if not only or "visualizer" in only:
                report["visualizers"] = capture_visualizers(material_scene, art, args.visualizer_materials, output,
                                                            fill_variants=args.fill_variants)
        finally:
            material_scene.close()
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
