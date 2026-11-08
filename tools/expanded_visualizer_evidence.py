"""Expanded Visualizer M2 evidence (plan 01 §0.2 / §H Gate 2): digests, the ordinary round trip, display-wide renders.

    .venv/Scripts/python tools/expanded_visualizer_evidence.py                     # everything, default layout
    .venv/Scripts/python tools/expanded_visualizer_evidence.py --digests-only      # also runs on main (no M2 API)

Three proofs, all offscreen (no window is ever shown):

1. **Reactivity and payload digests.** Recorded clips replay through the production owner
   (``QuickDisplayVisualizerOwner`` on an unshown ``QuickDisplayRuntime``) and its real publication path
   (``sync_present`` -> the presentation route -> the scene controller), for every capable mode. Every published
   logical frame is hashed (``repr``: every field, exact floats). The ordinary run is the M0 path; the expanded runs
   show the display-wide card from the first frame, or enter and leave it mid-clip with the fade-through. All
   digests must match, and (``--digests-only`` on main) match main's ordinary digests. Bubble and Waveform Ribbon
   read the whole committed extent, so a display-wide record leaking into the controller would change their frames;
   ``leak_control`` proves the digests see exactly that. (Spectrum reads only the extent's height, which a landscape
   expansion keeps, so it is no sentinel on a landscape display.)
2. **Ordinary round trip.** The ordinary ``ResolvedVisualizerPresentation`` before an expand and after the
   collapse, compared by ``==`` and by ``repr`` bytes; the controller's committed extent likewise; the drawn
   item's presentation as well.
3. **Production-host renders.** The production ``DisplayScene.qml`` through ``QQuickRenderControl`` into a hidden
   GL texture (the window is never shown or mapped), with the production ``QuickSceneController``,
   ``VisualizerRenderItem`` and mode render node; the snapshot is a replayed frame and the record is
   ``resolve_expanded_visualizer_presentation`` of the ordinary card on that display, inset by only what the card's
   chrome needs (``expanded_card_inset``; full display is not edge to edge). Extruded Bubble at 16:9, 16:10, 21:9,
   portrait and three DPRs, every
   other capable mode at 3840 x 2160 (150 %) and portrait: stills (PNG, lossless) with the card for reference, and
   one animated WebP of the fade-through.

Offscreen output is not physical acceptance (no real window, display timing or listening).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rendering.gl_error_policy import disable_per_call_gl_error_checking  # noqa: E402

disable_per_call_gl_error_checking()

from tools import artifact_paths  # noqa: E402

AREA = "visualizers/extruded_bubble"
TOPIC = "expanded_m2"
MODE = "extruded_bubble"
def ordinary_edge_margin() -> float:
    """The ordinary card's slot margin: Media's anchored slot (canonical), where the ordinary card is placed here.

    The expanded card does not use it: it is inset by only what its chrome needs (``expanded_card_inset``).
    """
    from core.settings.default_contract import get_raw_default_settings
    from rendering.quick.widgets.geometry_resolver import resolve_overlay_geometry_policy

    return float(resolve_overlay_geometry_policy("media", get_raw_default_settings()["widgets"]).margin)


# Neutral-but-real card chrome: a visible border and radius, so the shell/clip are exercised.
CARD = {
    "border_width": 3.0, "corner_radius": 8.0, "content_inset": 0.0,
    "background_color": (20, 22, 26, 200), "border_color": (230, 234, 240, 255),
    "shadow_enabled": False, "shadow_color": (0, 0, 0, 0), "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0), "shadow_spread": 0.0, "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}


def frame_digest(logical: Any) -> str:
    return hashlib.sha256(repr(logical).encode()).hexdigest()


def series_digest(digests: list[str]) -> str:
    return hashlib.sha256("".join(digests).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ owner replay


@contextmanager
def fresh_drift_revisions():
    """Number Extruded Bubble's drift families from 1 for one replay, then restore the process counter.

    The revision is a process-wide unique label (``extruded_bubble_drift_log._REVISIONS``), so a second replay in
    one process would otherwise publish different labels for identical frames. Main's digests come from a fresh
    process, which starts at 1 too.
    """
    import itertools

    from widgets.spotify_visualizer import extruded_bubble_drift_log

    saved = extruded_bubble_drift_log._REVISIONS
    extruded_bubble_drift_log._REVISIONS = itertools.count(1)
    try:
        yield
    finally:
        extruded_bubble_drift_log._REVISIONS = saved


def owner_replay(clip: Any, mode: str, *, preset: int = 0, settings: Any = None, expand_at: int | None = None,
                 collapse_at: int | None = None, animate: bool = False, generation: int = 9001,
                 committed: tuple[tuple[float, float, float, float], tuple[float, float]] | None = None,
                 bar_count: int = 32) -> dict:
    """Replay ``clip`` through the production owner's publication path; optionally expand/collapse it.

    No cadence thread runs: each recorded frame is accepted, ticked once (the authored step) and published through
    ``owner.sync_present()``, exactly the edge the logical runtime's wake drives. Returns per-frame logical digests,
    the drawn presentation records' outer rects, the controller's committed extents and the completion events.
    ``bar_count``: the owner and engine are built at it (32 by default, as every existing digest was made; the
    configuration then applies the mode's own bar count, which advances the engine's identity when it differs). The
    host binding builds them at the mode's resolved bar count (``tools/visualizer_replay/owner_production_replay.py``).
    """
    from PySide6.QtWidgets import QApplication

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    app = QApplication.instance() or QApplication([])
    # A raw-musical mode (Waveform Ribbon) reads production DSP recomputed from each frame's native PCM.
    reanalysis = PcmReanalysis() if get_visualizer_mode_descriptor(mode).raw_musical_signals else None
    has_route = hasattr(QuickDisplayVisualizerOwner, "set_expanded_display")
    if not has_route and (expand_at is not None or collapse_at is not None):
        raise RuntimeError("this tree has no display-wide viewport (main): ordinary digests only")
    digests: list[str] = []
    drawn: list[tuple[float, ...]] = []
    extents: list[tuple[float, float]] = []
    events: list[tuple[int, str]] = []
    ordinary_records: dict[str, Any] = {}
    current = [0]
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0, runtime_generation=generation, screen=app.primaryScreen(), scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    owner = None
    try:
        with deterministic_clock() as clock, fresh_drift_revisions():
            engine = ReplayBeatEngine(bar_count)
            owner = QuickDisplayVisualizerOwner(
                runtime, bar_count=bar_count, initial_mode=mode, engine_factory=lambda _count: engine,
                card_shadow_kwargs=CARD, transition_clock=lambda: clock[0],
            )
            controller = owner.controller
            controller.engine = engine
            configure_offline_controller(controller, mode, preset, None, settings)
            if committed is not None:
                # A saved CUSTOM rect and world, hydrated exactly as the host binding does before start.
                owner.configure_committed_layout(local_rect=committed[0], viewport_extent=committed[1])
            owner.bind(engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
            item = runtime.scene_controller
            for index, feature in enumerate(clip.frames):
                current[0] = index
                clock[0] = feature.timestamp_us / 1_000_000.0
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                if not engine.accept_feature_frame(feature):
                    raise RuntimeError(f"rejected replay input {clip.name}:{index}")
                if reanalysis is not None:
                    reanalysis.accept(engine, feature)
                if index == expand_at:
                    ordinary_records["before"] = owner._resolve_current_presentation()
                    ordinary_records["before_extent"] = controller.committed_viewport_extent
                    owner.set_expanded_display(True, animate=animate,
                                               on_complete=lambda: events.append((current[0], "entered")))
                if index == collapse_at:
                    owner.set_expanded_display(False, animate=animate,
                                               on_complete=lambda: events.append((current[0], "collapsed")))
                logical = logical_tick(controller.logical_tick_state)
                if logical is None:
                    raise RuntimeError(f"missing logical frame {clip.name}:{index}")
                digests.append(frame_digest(logical))
                owner.sync_present()
                presentation = item.visualizer_item.presentation if item.visualizer_item is not None else None
                drawn.append(tuple(presentation.outer_rect) if presentation is not None else ())
                extents.append(tuple(controller.committed_viewport_extent))
            if collapse_at is not None:
                ordinary_records["after"] = owner._resolve_current_presentation()
                ordinary_records["after_extent"] = controller.committed_viewport_extent
                ordinary_records["after_drawn"] = item.visualizer_item.presentation
            display = tuple(runtime.display_identity.geometry)
    finally:
        if owner is not None and not owner.is_retired:
            owner.retire()
        runtime.close_runtime()
        factory.deleteLater()
        app.processEvents()
    return {"digests": digests, "drawn": drawn, "extents": extents, "events": events,
            "ordinary": ordinary_records, "display": display}


# ------------------------------------------------------------------------------- production host, hidden render


class HiddenDisplayHost:
    """The production ``DisplayScene.qml`` and ``QuickSceneController`` rendered into a hidden GL texture.

    ``QQuickRenderControl`` owns the render loop, so the window is a scene container that is never shown or mapped
    (the onboarding foundry's pattern). The scene controller gets the few window hooks it binds (input hit tests,
    orbit target) as inert stand-ins: nothing here receives input.
    """

    def __init__(self, width: int, height: int, *, dpr: float) -> None:
        from OpenGL import GL as gl
        from PySide6.QtCore import QObject, QSize
        from PySide6.QtGui import QColor, QGuiApplication, QOffscreenSurface, QOpenGLContext
        from PySide6.QtQuick import QQuickGraphicsDevice, QQuickRenderControl, QQuickRenderTarget, QQuickWindow

        from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory

        class _SceneContainer(QQuickWindow):
            screen_index = 0
            runtime_generation = 1

            def bind_semantic_double_click_hit_test(self, _test) -> None: pass
            def bind_semantic_middle_click_hit_test(self, _test) -> None: pass
            def bind_plain_orbit_target(self, _target, grabber_blocks=None) -> None: pass
            def watch_plain_orbit_card(self, _card) -> None: pass
            def set_custom_layout_input_blocked(self, _blocked) -> None: pass

        self.app = QGuiApplication.instance()
        if self.app is None or self.app.platformName().strip().lower() != "windows":
            raise RuntimeError("the hidden production-host render needs the Windows QPA GL")
        self._gl = gl
        self.logical = (width, height)
        self.dpr = float(dpr)
        self.pixels = (round(width * self.dpr), round(height * self.dpr))
        self.context = QOpenGLContext()
        if not self.context.create():
            raise RuntimeError("hidden render GL context is unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        self.control = QQuickRenderControl()
        # The control's RHI keeps a raw pointer to this context: Qt children of the control (R-172/R-173).
        self.context.setParent(self.control)
        self.surface.setParent(self.control)
        self.window = _SceneContainer(self.control)
        self.window.resize(width, height)
        self.window.setColor(QColor("#0b0d10"))
        self.window.setGraphicsDevice(QQuickGraphicsDevice.fromOpenGLContext(self.context))
        if not self.control.initialize():
            raise RuntimeError("hidden render control did not initialize")
        self._current()
        self.texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, *self.pixels, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        target = QQuickRenderTarget.fromOpenGLTexture(self.texture, QSize(*self.pixels))
        target.setDevicePixelRatio(self.dpr)
        self.window.setRenderTarget(target)
        self._owner = QObject()
        self.factory = QuickSceneFactory(self._owner)
        self.scene = QuickSceneController(window=self.window, factory=self.factory)
        root = self.window.contentItem()
        root.setWidth(width)
        root.setHeight(height)

    def _current(self) -> None:
        if not self.context.makeCurrent(self.surface):
            raise RuntimeError("hidden render GL context could not be made current")

    def render(self) -> None:
        self.app.processEvents()
        self.control.polishItems()
        self.control.beginFrame()
        self.control.sync()
        self.control.render()
        self.control.endFrame()

    def read(self):
        """The rendered frame, top-down RGBA (numpy, uint8)."""
        import numpy

        gl = self._gl
        self._current()
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        data = gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        width, height = self.pixels
        return numpy.flipud(numpy.frombuffer(bytes(data), dtype=numpy.uint8).reshape(height, width, 4)).copy()

    def close(self) -> None:
        from PySide6.QtCore import QCoreApplication, QEvent

        self._current()
        self.control.invalidate()          # render nodes release their GL with the context current
        self.scene._retire_qml_objects()   # the scene's own QML retirement (what admission closure triggers)
        self.app.processEvents()
        self._current()
        self._gl.glDeleteTextures([self.texture])
        self.window.deleteLater()
        self.control.deleteLater()
        self.factory.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()


def _fade_sample(elapsed: float, half: float) -> tuple[bool, float]:
    """(target side drawn, opacity) of the owner's fade-through at ``elapsed`` (smoothstep halves)."""
    if elapsed >= 2.0 * half:
        return True, 1.0
    target_side = elapsed >= half
    linear = (elapsed - half) / half if target_side else 1.0 - elapsed / half
    return target_side, linear * linear * (3.0 - 2.0 * linear)


def render_views(clip: Any, *, logical: tuple[int, int], dpr: float, capture_at: int, preset: int = 0,
                 sequence: tuple[int, int] | None = None, sequence_out: Path | None = None,
                 enter_at: int | None = None, collapse_at: int | None = None, stride: int = 1,
                 mode: str = MODE) -> dict:
    """Replay ``clip`` through ``mode`` into the hidden production host on a ``logical`` display at ``dpr``.

    The ordinary record is the canonical card at an authored origin (bottom-left); the display-wide record is
    ``resolve_expanded_visualizer_presentation`` of it, published through the production presentation sync and
    committed to the production scene controller. Without ``sequence`` the card is captured at ``capture_at`` and
    then the display-wide view at ``capture_at`` of a second pass; with it every frame of the range is written to
    ``sequence_out`` (PNG, scratch) while the route fades through at ``enter_at`` / ``collapse_at`` exactly as the
    owner's does (same half duration, same smoothstep). Returns the measured geometry and pixel coverage.
    """
    from PIL import Image

    from core.settings.visualizer_mode_registry import (
        get_visualizer_mode_descriptor,
        get_visualizer_presentation_policy,
    )
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_display_visualizer_owner import _MODE_TRANSITION_HALF_DURATION_S
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    width, height = logical
    host = HiddenDisplayHost(width, height, dpr=dpr)
    results: dict[str, Any] = {"logical": [width, height], "dpr": dpr, "device": list(host.pixels)}
    try:
        with deterministic_clock() as clock:
            scene = host.scene
            margin = ordinary_edge_margin()
            origin = (margin, float(height) - 280.0 - margin)

            def ordinary():
                return resolve_visualizer_presentation(
                    policy=get_visualizer_presentation_policy(mode), display_size=(width, height),
                    outer_origin=origin, dpr=dpr, **CARD)

            def expanded():
                return resolve_expanded_visualizer_presentation(ordinary(), display_size=(width, height), dpr=dpr)

            route = {"expanded": False, "start": None, "target": False}

            def resolve():
                start = route["start"]
                if start is None:
                    return expanded() if route["expanded"] else ordinary()
                target_side, opacity = _fade_sample(clock[0] - start, _MODE_TRANSITION_HALF_DURATION_S)
                drawn = route["target"] if target_side else not route["target"]
                if target_side and opacity >= 1.0:
                    route.update(expanded=route["target"], start=None)
                base = expanded() if drawn else ordinary()
                return replace(base, scene_fade=float(base.scene_fade) * opacity)

            passes = ("ordinary", "expanded") if sequence is None else ("sequence",)
            last = capture_at if sequence is None else sequence[1]
            for name in passes:
                # Each pass replays the clip from its start on a fresh engine and controller (one activation).
                engine = ReplayBeatEngine(32)
                controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode,
                                                         engine_factory=lambda _count, e=engine: e)
                controller.engine = engine
                configure_offline_controller(controller, mode, preset)
                reanalysis = (PcmReanalysis() if get_visualizer_mode_descriptor(mode).raw_musical_signals
                              else None)
                identity = controller.begin_render_activation(
                    engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
                scene.set_visualizer_render_source(controller.render_bridge, identity)
                sync = QuickVisualizerPresentationSync(
                    controller, resolve_presentation=resolve,
                    commit_presentation=lambda presentation: scene.apply_visualizer_presentation(
                        presentation, active=True),
                    request_present=scene.request_visualizer_present,
                )
                route.update(expanded=name == "expanded", start=None)
                for index, feature in enumerate(clip.frames[:last + 1]):
                    clock[0] = feature.timestamp_us / 1_000_000.0
                    controller.playing = feature.playing
                    engine.set_playback_state(feature.playing)
                    engine.accept_feature_frame(feature)
                    if reanalysis is not None:
                        reanalysis.accept(engine, feature)
                    if index == enter_at:
                        route.update(start=clock[0], target=True)
                    if index == collapse_at:
                        route.update(start=clock[0], target=False)
                    if logical_tick(controller.logical_tick_state) is None:
                        raise RuntimeError(f"missing logical frame {index}")
                    if not sync.sync_latest():
                        raise RuntimeError(f"snapshot rejected at {index}")
                    host.render()
                    if (sequence is not None and index >= sequence[0] and sequence_out is not None
                            and (index - sequence[0]) % stride == 0):
                        Image.fromarray(host.read(), "RGBA").convert("RGB").save(
                            sequence_out / f"frame_{(index - sequence[0]) // stride:04d}.png")
                if sequence is None:
                    rgba = host.read()
                    presentation = scene.visualizer_item.presentation
                    lit = float((rgba[..., :3].max(axis=2) > 24).mean())
                    results[name] = {
                        "outer_rect": list(presentation.outer_rect),
                        "content_rect": list(presentation.content_rect),
                        "viewport_extent": list(presentation.viewport_extent),
                        "uniform_visual_scale": presentation.uniform_visual_scale,
                        "content_device_px": [round(presentation.content_rect[2] * dpr),
                                              round(presentation.content_rect[3] * dpr)],
                        "lit_fraction": round(lit, 4),
                        "image": Image.fromarray(rgba, "RGBA").convert("RGB"),
                    }
                controller.close_render_admission()
    finally:
        host.close()
    return results


# ------------------------------------------------------------------------------------------------------- CLI

RECORDINGS = ("anything_mixed2", "heavy1", "quiet_intro", "1985_loud1")
#: Every mode that declares ``supports_expanded_display`` (operator, 7 Nov: all but Voxel Sphere and Extruded
#: Spectrum), resolved from the registry.
def capable_modes() -> tuple[str, ...]:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors() if d.supports_expanded_display)


#: The modes whose logical worlds read the controller's committed extent: a display-wide record leaking into the
#: controller would change their frames, so they sentinel the ordinary-metrics rule.
EXTENT_SENSITIVE = ("bubble", "waveform_ribbon")
STUDIO_CLIPS = ("growing_pains", "human")
#: (label, logical size, DPR): 16:9 at 100 % and the operator's TV (3840 x 2160 at 150 %), 16:10, 21:9, portrait,
#: and a 125 % display, so three DPRs resolve the same ordinary card.
DISPLAYS = (
    ("16x9_1920x1080_100", (1920, 1080), 1.0),
    ("16x9_3840x2160_150", (2560, 1440), 1.5),
    ("16x10_1920x1200_100", (1920, 1200), 1.0),
    ("21x9_3440x1440_100", (3440, 1440), 1.0),
    ("portrait_1080x1920_100", (1080, 1920), 1.0),
    ("16x9_1920x1080_125", (1536, 864), 1.25),
)
#: A saved CUSTOM card (rect, world) whose ordinary geometry must come back byte-identical.
CUSTOM_CARD = ((96.0, 180.0, 840.0, 280.0), (840.0, 280.0))


def load_recording(name: str, seconds: float) -> Any:
    """The first ``seconds`` of one of the operator's recordings, read only."""
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame

    path = artifact_paths.main_checkout() / "logs" / "visualizer_recordings" / f"{name}.jsonl"
    frames = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            if frames and (frame.timestamp_us - frames[0].timestamp_us) / 1e6 > seconds:
                break
            frames.append(frame)
    return FeatureClip(name, tuple(frames))


def looped_fixture(loops: int = 8) -> Any:
    """The synthetic music fixture looped to ~11 s (as the EB exactness bar does), long enough for fades."""
    from tools.visualizer_replay.driver import load_clips
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    base = load_clips()["representative_music_features"]
    span = base.frames[-1].timestamp_us - base.frames[0].timestamp_us + 11_111
    frames = tuple(replace(frame, timestamp_us=frame.timestamp_us + loop * span)
                   for loop in range(loops) for frame in base.frames)
    return FeatureClip("representative_music_features_looped", frames)


def shipped_clip(seconds: float, name: str = "growing_pains") -> Any:
    """The opening of a shipped Studio clip: compact, with native PCM on every frame (Waveform Ribbon needs it)."""
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    clip = load_feature_clip(ROOT / "assets" / "production" / "studio_clips" / f"{name}.srclip")
    origin = clip.frames[0].timestamp_us
    frames = tuple(frame for frame in clip.frames if (frame.timestamp_us - origin) / 1e6 <= seconds)
    return FeatureClip(f"studio_{name}", frames)


def _clips(seconds: float) -> list[Any]:
    clips = [looped_fixture()]
    for name in RECORDINGS:
        try:
            clips.append(load_recording(name, seconds))
        except FileNotFoundError:
            print(f"recording {name} not present; skipped", flush=True)
    return clips


def digests(seconds: float, *, ordinary_only: bool) -> dict:
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

    rows = []
    modes = capable_modes() if not ordinary_only else tuple(m for m in (
        "extruded_bubble", "spectrum", "oscilloscope", "devcurve", "bubble", "shockwave_grid", "waveform_ribbon"))
    native = [shipped_clip(seconds, name) for name in STUDIO_CLIPS]
    for clip in [*_clips(seconds), *native]:
        frames = len(clip.frames)
        has_pcm = all(frame.capture_history is not None for frame in clip.frames)
        for mode in modes:
            if get_visualizer_mode_descriptor(mode).raw_musical_signals and not has_pcm:
                continue            # Waveform Ribbon replays only from native PCM (the shipped clips)
            row = {"clip": clip.name, "mode": mode, "frames": frames}
            ordinary = owner_replay(clip, mode)
            row["ordinary"] = series_digest(ordinary["digests"])
            if not ordinary_only:
                full = owner_replay(clip, mode, expand_at=0)
                fade = owner_replay(clip, mode, expand_at=frames // 4, collapse_at=(3 * frames) // 4, animate=True)
                row["expanded_from_first_frame"] = series_digest(full["digests"])
                row["expand_and_collapse_mid_clip"] = series_digest(fade["digests"])
                row["identical"] = row["ordinary"] == row["expanded_from_first_frame"] == row[
                    "expand_and_collapse_mid_clip"]
                row["first_frame_drawn"] = list(full["drawn"][0])
                row["display"] = list(full["display"])
                row["events"] = fade["events"]
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "events"}), flush=True)
    return {"rows": rows}


def leak_control() -> dict:
    """Negative control: commit the display-wide record's metrics to the controller (the mistake the owner's
    expanded commit avoids) and show the digests of every extent-sensitive mode change."""
    from unittest.mock import patch

    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    def leaky(self, presentation):
        self._presentation_runtime.scene_controller.apply_visualizer_presentation(presentation, active=True)
        self._controller.commit_presentation_metrics(presentation)

    out = {}
    for mode in EXTENT_SENSITIVE:
        clip = shipped_clip(4.0) if mode == "waveform_ribbon" else looped_fixture()
        ordinary = series_digest(owner_replay(clip, mode)["digests"])
        with patch.object(QuickDisplayVisualizerOwner, "_apply_expanded_presentation", leaky):
            leaked = series_digest(owner_replay(clip, mode, expand_at=0)["digests"])
        out[mode] = {"ordinary": ordinary, "leaked": leaked, "detected": ordinary != leaked}
        print("leak_control", mode, out[mode]["detected"], flush=True)
    return out


def round_trip() -> dict:
    """The ordinary record, committed extent and drawn item before an expand and after the collapse."""
    clip = looped_fixture()
    out = {}
    for label, committed in (("authored_card", None), ("custom_card", CUSTOM_CARD)):
        result = owner_replay(clip, MODE, expand_at=30, collapse_at=300, animate=True, committed=committed)
        records = result["ordinary"]
        before, after, drawn = records["before"], records["after"], records["after_drawn"]
        out[label] = {
            "equal": before == after,
            "repr_bytes_equal": repr(before).encode() == repr(after).encode(),
            "drawn_equals_ordinary": drawn == after,
            "committed_extent_before_after": [list(records["before_extent"]), list(records["after_extent"])],
            "outer_rect": list(after.outer_rect), "viewport_extent": list(after.viewport_extent),
            "expanded_drawn_rect": list(result["drawn"][200]),
            "events": result["events"],
            "sha256_before": hashlib.sha256(repr(before).encode()).hexdigest(),
            "sha256_after": hashlib.sha256(repr(after).encode()).hexdigest(),
        }
        print(label, json.dumps({k: v for k, v in out[label].items() if not k.startswith("sha")}), flush=True)
    return out


#: Every capable mode is rendered on these two (Extruded Bubble, the gate mode, on all of ``DISPLAYS``).
MODE_DISPLAYS = ("16x9_3840x2160_150", "portrait_1080x1920_100")


def renders(out_dir: Path, webp: Path, seconds: float) -> dict:
    from tools import evidence_media

    clip = shipped_clip(max(seconds, 8.0))          # native PCM: every capable mode, Waveform included, replays it
    capture_at = min(len(clip.frames) - 1, 420)
    table: dict[str, Any] = {}
    jobs = [(MODE, display) for display in DISPLAYS]
    jobs += [(mode, display) for mode in capable_modes() if mode != MODE
             for display in DISPLAYS if display[0] in MODE_DISPLAYS]
    for mode, (label, logical, dpr) in jobs:
        result = render_views(clip, logical=logical, dpr=dpr, capture_at=capture_at, mode=mode)
        for view in ("ordinary", "expanded"):
            image = result[view].pop("image")
            image.save(out_dir / f"{mode}_{label}_{'card' if view == 'ordinary' else 'expanded'}.png")
        table[f"{mode}/{label}"] = result
        print(mode, label, json.dumps(result["expanded"]), flush=True)
    with artifact_paths.scratch("expanded-m2") as scratch:
        clip = load_recording(RECORDINGS[0], seconds)
        sequence = render_views(clip, logical=(1920, 1080), dpr=1.0, capture_at=0,
                                sequence=(360, 640), sequence_out=scratch, enter_at=400, collapse_at=560, stride=4)
        frames = sorted(scratch.glob("frame_*.png"))
        receipt = evidence_media.animated_webp(frames, webp, fps=24)
        table["fade_through"] = {"frames": len(frames), "webp": receipt, "logical": sequence["logical"],
                                 "enter_at_frame": 400, "collapse_at_frame": 560, "stride": 4}
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=artifact_paths.evidence_arg,
                        default=artifact_paths.default_evidence(AREA, TOPIC, "gate2"))
    parser.add_argument("--webp", type=artifact_paths.webp_arg,
                        default=artifact_paths.default_webp(AREA, TOPIC, "fade_through"))
    parser.add_argument("--seconds", type=float, default=12.0, help="seconds of each recording to replay")
    parser.add_argument("--digests-only", action="store_true",
                        help="ordinary digests only (runs on a tree without the M2 route, e.g. main)")
    args = parser.parse_args(argv)

    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="expanded-visualizer-evidence")
    from PySide6.QtWidgets import QApplication

    app = QApplication(["expanded-visualizer-evidence"])
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    import subprocess

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    document: dict[str, Any] = {"commit": commit, "seconds": args.seconds, "preset": "Preset 1 (index 0)",
                                "digests": digests(args.seconds, ordinary_only=args.digests_only)}
    if not args.digests_only:
        document["leak_control"] = leak_control()
        document["round_trip"] = round_trip()
        document["renders"] = renders(out_dir, Path(args.webp), args.seconds)
    name = "main_digests.json" if args.digests_only else "summary.json"
    (out_dir / name).write_text(json.dumps(document, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"wrote {out_dir / name}", flush=True)
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
