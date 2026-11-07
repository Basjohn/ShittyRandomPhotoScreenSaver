"""Spectrum customization evidence: pixel identity, showcase renders and GPU cost through the production renderer.

Every frame comes from the production offline replay (``ui.studio.spectrum_recorded_inputs.extract``: the real beat
engine, ``logical_tick`` and Spectrum's capture under a pinned clock) over a shipped Studio clip, and is drawn by the
production ``QuickVisualizerRenderHost`` -> ``QuickSpectrumRenderer`` into an offscreen FBO (no window is shown).

    python tools/spectrum_decor_evidence.py baseline OUT_DIR      # record pixels (before a change)
    python tools/spectrum_decor_evidence.py compare BASELINE_DIR   # the same renders now: byte for byte
    python tools/spectrum_decor_evidence.py showcase OUT_DIR       # Organs with each new option on: stills + strips
    python tools/spectrum_decor_evidence.py cost [OUT_JSON]        # GPU time per option at card size (TIME_ELAPSED)
    python tools/spectrum_decor_evidence.py presets OUT_DIR        # every curated preset: contact sheets + metrics

"Organs" is curated Preset 1 read from ``presets/visualizer_modes/spectrum`` at run time (authored content: this
tool records what it looks like; it never asserts preset values).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODE = "spectrum"
SCALES = (1.0, 2.0)                  # the canonical 420x280 card, and the same card at 2x
FRACTIONS = (0.35, 0.6, 0.85)        # replay instants (fraction of the replayed clip)
SECONDS = 4.0


def canonical_values() -> dict:
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in require_mode_settings(MODE).controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def organs_values() -> dict:
    from core.settings import visualizer_presets as vp
    path = next(iter(sorted((ROOT / "presets" / "visualizer_modes" / MODE).glob("preset_1_*.json"))))
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = canonical_values()
    for section in vp._collect_visualizer_sections(payload):
        values.update(section)
    values["mode"] = MODE
    return values


def clip_path() -> str:
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    clips = studio_clips(recordings_directory())
    if not clips:
        raise SystemExit("no shipped Studio clip")
    return clips[0].description


def production_frames(values: dict, *, seconds: float = SECONDS, fractions=FRACTIONS, every: int = 0):
    """(now, frame) from the production replay at ``fractions`` of it (or every ``every``-th tick)."""
    from ui.studio.spectrum_recorded_inputs import extract
    captured: list = []
    extract(clip_path(), values, seconds=seconds, frames_out=captured)
    if every:
        return captured[::every]
    return [captured[min(len(captured) - 1, int(len(captured) * f))] for f in fractions]


class GLTarget:
    """An offscreen GL 4.6 context and FBO the production render host draws into."""

    def __init__(self) -> None:
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
        from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setVersion(4, 6)
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        if not self.context.create():
            raise RuntimeError("OpenGL 4.6 context unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(fmt)
        self.surface.create()
        if not self.surface.isValid() or not self.context.makeCurrent(self.surface):
            raise RuntimeError("offscreen OpenGL context unavailable")
        self.host = QuickVisualizerRenderHost()
        self._fbos: dict = {}

    def _fbo(self, width: int, height: int) -> int:
        from OpenGL import GL as gl
        key = (width, height)
        if key not in self._fbos:
            color = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, color)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            fbo = gl.glGenFramebuffers(1)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
            assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            self._fbos[key] = (fbo, color)
        return self._fbos[key][0]

    @staticmethod
    def presentation(scale: float):
        from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
        from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
        return resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy(MODE), display_size=(420.0 * scale, 280.0 * scale),
            uniform_visual_scale=scale, viewport_extent=(420.0, 280.0), border_width=0.0, corner_radius=0.0,
            content_inset=0.0, background_color=(0, 0, 0, 0), border_color=(255, 255, 255, 255),
            shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0, shadow_offset=(0.0, 0.0),
            shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))

    def draw(self, frame, scale: float, *, background=(0.0, 0.0, 0.0, 0.0)) -> None:
        from OpenGL import GL as gl
        from widgets.spotify_visualizer.render_state import compose_visualizer_render_snapshot
        width, height = int(420 * scale), int(280 * scale)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo(width, height))
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(*background)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        snapshot = compose_visualizer_render_snapshot(frame, self.presentation(scale), logical_revision=1)
        matrix = (2 / width, 0, 0, 0, 0, 2 / height, 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)
        assert self.host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                                logical_size=(float(width), float(height)), matrix_values=matrix) == MODE

    def timed_draw(self, frame, scale: float, repeat: int, query: int) -> float:
        """GPU ms of the production Spectrum draw of ``frame``: the renderer's own draw call (every uniform, blend and
        quad state it and the host set) issued ``repeat`` times in one instanced call inside a TIME_ELAPSED query,
        so the figure is the shader's cost, not Python submission."""
        from OpenGL import GL as gl
        import rendering.quick.visualizer.implementations.spectrum as spectrum_module

        class TimedGL:
            def __getattr__(self, name):
                return getattr(gl, name)

            @staticmethod
            def glDrawArrays(mode, first, count):
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
                gl.glDrawArraysInstanced(mode, first, count, repeat)
                gl.glEndQuery(gl.GL_TIME_ELAPSED)

        spectrum_module.gl = TimedGL()
        try:
            self.draw(frame, scale)
        finally:
            spectrum_module.gl = gl
        return float(gl.glGetQueryObjectuiv(query, gl.GL_QUERY_RESULT)) / 1e6 / repeat

    def render(self, frame, scale: float, *, background=(0.0, 0.0, 0.0, 0.0)):
        """Top-origin RGBA uint8 pixels of ``frame`` drawn at ``scale``."""
        import numpy as np
        from OpenGL import GL as gl
        self.draw(frame, scale, background=background)
        width, height = int(420 * scale), int(280 * scale)
        raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.frombuffer(bytes(raw), dtype=np.uint8).reshape(height, width, 4).copy()   # the item matrix keeps item-top at row 0

    def release(self) -> None:
        from OpenGL import GL as gl
        self.host.release_resources()
        for fbo, color in self._fbos.values():
            gl.glDeleteFramebuffers(1, [fbo])
            gl.glDeleteTextures([color])
        self._fbos.clear()
        self.context.doneCurrent()
        self.surface.destroy()


def _app():
    from PySide6.QtGui import QGuiApplication
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    return QGuiApplication.instance() or QGuiApplication(sys.argv[:1])


def identity_renders(target: GLTarget) -> dict:
    """{name: pixels} for the canonical defaults and Organs at every replay instant and scale."""
    out = {}
    for config, values in (("default", canonical_values()), ("organs", organs_values())):
        for index, (_now, frame) in enumerate(production_frames(values)):
            for scale in SCALES:
                out[f"{config}_t{index}_x{scale:g}"] = target.render(frame, scale)
    return out


def _png(path: Path, pixels) -> None:
    from PySide6.QtGui import QImage
    import numpy as np
    data = np.ascontiguousarray(pixels)
    image = QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 4, QImage.Format.Format_RGBA8888)
    image.copy().save(str(path))


_BACKDROP = (16.0, 18.0, 24.0)


def _on_black(pixels):
    """Render pixels composited over the card's dark background, for viewing.

    The render host blends SRC_ALPHA / ONE_MINUS_SRC_ALPHA (colour) and ONE / ONE_MINUS_SRC_ALPHA (alpha) into a
    target cleared to transparent black, so the FBO holds premultiplied colour: composite with ``rgb + bg * (1 - a)``
    (multiplying by alpha again would darken every translucent ghost, glow and fill pixel)."""
    import numpy as np
    rgb = pixels[..., :3].astype(float)
    alpha = pixels[..., 3:4].astype(float) / 255.0
    background = np.array(_BACKDROP)
    out = rgb + background * (1.0 - alpha)
    return np.concatenate([out.clip(0, 255).astype(np.uint8), np.full(pixels.shape[:2] + (1,), 255, np.uint8)], -1)


def cmd_baseline(out_dir: Path) -> int:
    import numpy as np
    _app()
    target = GLTarget()
    try:
        renders = identity_renders(target)
    finally:
        target.release()
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "pixels.npz", **renders)
    digests = {name: hashlib.sha256(p.tobytes()).hexdigest() for name, p in renders.items()}
    (out_dir / "digests.json").write_text(json.dumps(digests, indent=2), encoding="utf-8")
    for name, pixels in renders.items():
        if name.endswith("x1"):
            _png(out_dir / f"{name}.png", _on_black(pixels))
    print(json.dumps(digests, indent=2))
    return 0


def cmd_compare(baseline: Path) -> int:
    import numpy as np
    _app()
    target = GLTarget()
    try:
        renders = identity_renders(target)
    finally:
        target.release()
    before = np.load(baseline / "pixels.npz")
    report = {}
    for name, pixels in renders.items():
        old = before[name]
        report[name] = {"identical": bool(np.array_equal(old, pixels)),
                        "differing_pixels": int((np.abs(old.astype(int) - pixels.astype(int)).max(-1) > 0).sum()),
                        "sha256": hashlib.sha256(pixels.tobytes()).hexdigest()}
    print(json.dumps(report, indent=2))
    return 0 if all(r["identical"] for r in report.values()) else 1


# ------------------------------------------------------------------------------------- showcase / cost
def variants() -> dict:
    """Organs with each new option on (one at a time, plus a combined look). Option values are showcase choices."""
    on = {
        "ghost_custom": {"spectrum_rainbow_ghost": False, "spectrum_ghost_color_source": "Custom",
                         "spectrum_ghost_color": [255, 170, 60, 255]},
        "ghost_gradient": {"spectrum_ghost_gradient": True, "spectrum_ghost_tip_color": [255, 60, 200, 255]},
        "fill_gradient": {"spectrum_fill_gradient": True, "spectrum_fill_tip_color": [40, 120, 255, 235]},
        "peak_caps": {"spectrum_peak_caps": True, "spectrum_peak_cap_color": [255, 255, 255, 255]},
        "gloss": {"spectrum_gloss": 0.8},
    }
    for pattern in ("Horizontal Bands", "Scanlines", "Dots", "Diagonal Stripes", "Grid", "Chevrons"):
        on["pattern_" + pattern.lower().replace(" ", "_")] = {
            "spectrum_pattern": pattern, "spectrum_pattern_color": [120, 200, 255, 170]}
    for pattern in ("Horizontal Bands", "Scanlines", "Dots", "Diagonal Stripes", "Grid", "Chevrons"):
        on["pattern_shared_" + pattern.lower().replace(" ", "_")] = {
            "spectrum_pattern": pattern, "spectrum_pattern_anchor": "Shared",
            "spectrum_pattern_color": [120, 200, 255, 170]}
    on["combined"] = {**on["fill_gradient"], **on["peak_caps"], **on["gloss"], **on["pattern_scanlines"],
                      "spectrum_pattern_color": [255, 255, 255, 60]}
    return on


def cmd_showcase(out_dir: Path, only: str = "") -> int:
    import numpy as np
    _app()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = GLTarget()
    try:
        base = organs_values()
        looks = {name: v for name, v in {"organs": {}, **variants()}.items() if only in name}
        for name, overrides in looks.items():
            values = dict(base, **overrides)
            stills = [target.render(frame, 2.0) for _now, frame in production_frames(values, fractions=(0.6,))]
            _png(out_dir / f"still_{name}.png", _on_black(stills[0]))
            # A short motion strip: 8 consecutive production ticks (~90 ms) stacked, at card size.
            strip = [target.render(frame, 1.0) for _now, frame in
                     production_frames(values, seconds=SECONDS, every=1)[300:308]]
            _png(out_dir / f"strip_{name}.png", _on_black(np.concatenate(strip, axis=0)))
            print("showcase", name)
    finally:
        target.release()
    return 0


def cmd_cost(out_json: Path | None) -> int:
    """Median / p90 GPU ms of one Spectrum draw per option (``GLTarget.timed_draw``: the production draw repeated
    200 times in one instanced call), at the card (x1), x2 and x4 (1680x1120, a near full-screen card)."""
    import statistics
    from OpenGL import GL as gl
    _app()
    target = GLTarget()
    results = {}
    try:
        base = organs_values()
        # Organs first and last: the control the options are judged against (absolute ms swing with GPU clocks).
        looks = {"organs": {}, **variants(), "organs_again": {}}
        query = gl.glGenQueries(1)[0]
        _now, warm = production_frames(base, fractions=(0.5,))[0]
        for _ in range(40):                       # raise the GPU clocks before the first measurement
            target.timed_draw(warm, 4.0, 500, query)
        for name, overrides in looks.items():
            values = dict(base, **overrides)
            frames = [f for _n, f in production_frames(values, fractions=(0.3, 0.5, 0.7, 0.9))]
            entry = {}
            for scale in (*SCALES, 4.0):
                for frame in frames:            # warm
                    target.render(frame, scale)
                samples = []
                for _repeat in range(20):
                    for frame in frames:
                        samples.append(target.timed_draw(frame, scale, 200, query))
                samples.sort()
                entry[f"x{scale:g}"] = {"median_ms": round(float(statistics.median(samples)), 5),
                                        "p90_ms": round(float(samples[int(len(samples) * 0.9)]), 5)}
            results[name] = entry
            print(name, entry)
        gl.glDeleteQueries(1, [query])
    finally:
        target.release()
    try:
        import psutil
        results["_conditions"] = {"cpu_percent": psutil.cpu_percent(interval=0.5),
                                  "memory_percent": psutil.virtual_memory().percent}
    except Exception:
        pass
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


# ------------------------------------------------------------------------------------- curated preset review
def curated_presets() -> list[tuple[str, dict]]:
    """(file stem, values) of every curated Spectrum preset in slot order, each over the canonical defaults."""
    from core.settings import visualizer_presets as vp
    folder = ROOT / "presets" / "visualizer_modes" / MODE
    found = []
    for path in folder.glob("*.json"):
        slot = vp._infer_preset_index_from_name(path.stem)
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = canonical_values()
        for section in vp._collect_visualizer_sections(payload):
            values.update(section)
        values["mode"] = MODE
        found.append((slot if slot is not None else 999, path.stem, values))
    return [(stem, values) for _slot, stem, values in sorted(found)]


def _srgb_to_lab(rgb):
    """(..., 3) sRGB 0..255 -> CIELAB (D65)."""
    import numpy as np
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], -1)


def look_metrics(pixels) -> dict:
    """Vividness and contrast of the drawn pixels (alpha > 0.25) of one straight-alpha render, composited on the
    card's dark background, plus a 4-colour Lab palette for distinctness.

    chroma: mean (max - min) / 255 (0 = grey, 1 = a pure primary). colourfulness: Hasler-Suesstrunk M.
    contrast_L: p95 - p5 of the drawn pixels' Lab lightness (0..100). backdrop_contrast_L: their mean lightness above
    the card backdrop's."""
    import numpy as np
    alpha = pixels[..., 3].astype(float) / 255.0
    drawn = alpha > 0.25
    shown = _on_black(pixels)[..., :3].astype(float)[drawn]
    if len(shown) < 16:
        return {"drawn_fraction": float(drawn.mean())}
    chroma = (shown.max(-1) - shown.min(-1)) / 255.0
    rg = shown[:, 0] - shown[:, 1]
    yb = 0.5 * (shown[:, 0] + shown[:, 1]) - shown[:, 2]
    colourfulness = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))
    lab = _srgb_to_lab(shown)
    lightness = np.percentile(lab[:, 0], [5, 95])
    # Palette: 4 weighted k-means centroids in Lab (deterministic farthest-point seeding).
    rng = np.random.default_rng(7)
    sample = lab[rng.choice(len(lab), size=min(len(lab), 6000), replace=False)]
    centres = [sample[0]]
    for _ in range(3):
        d = np.min([np.linalg.norm(sample - c, axis=1) for c in centres], axis=0)
        centres.append(sample[int(d.argmax())])
    centres = np.array(centres)
    for _ in range(12):
        label = np.argmin(np.linalg.norm(sample[:, None] - centres[None], axis=2), axis=1)
        centres = np.array([sample[label == k].mean(0) if (label == k).any() else centres[k] for k in range(4)])
    weights = np.bincount(label, minlength=4) / len(sample)
    return {"drawn_fraction": round(float(drawn.mean()), 4), "chroma": round(float(chroma.mean()), 4),
            "colourfulness": round(colourfulness, 2), "contrast_L": round(float(lightness[1] - lightness[0]), 2),
            "backdrop_contrast_L": round(float(lab[:, 0].mean() - _srgb_to_lab(np.array(_BACKDROP))[0]), 2),
            "palette_lab": [[round(float(v), 2) for v in c] for c in centres], "palette_weight": [
                round(float(w), 4) for w in weights]}


def palette_distance(a: dict, b: dict) -> float:
    """Weighted symmetric mean nearest-centroid Delta-E (CIE76) between two looks' palettes."""
    import numpy as np
    pa, pb = np.array(a["palette_lab"]), np.array(b["palette_lab"])
    wa, wb = np.array(a["palette_weight"]), np.array(b["palette_weight"])
    d = np.linalg.norm(pa[:, None] - pb[None], axis=2)
    return float(0.5 * ((d.min(1) * wa).sum() + (d.min(0) * wb).sum()))


def image_distance(a, b) -> float:
    """Mean Lab Delta-E between two renders of the same instant over the pixels either draws: how differently the
    two looks paint the same bars (colour, pattern, shape and trims together)."""
    import numpy as np
    drawn = (a[..., 3] > 64) | (b[..., 3] > 64)
    la = _srgb_to_lab(_on_black(a)[..., :3][drawn].astype(float))
    lb = _srgb_to_lab(_on_black(b)[..., :3][drawn].astype(float))
    return float(np.linalg.norm(la - lb, axis=1).mean())


def _labelled_tile(pixels, title: str):
    """A dark-backdrop render with its preset title painted along the top, as a QImage."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    import numpy as np
    data = np.ascontiguousarray(_on_black(pixels))
    image = QImage(data.data, data.shape[1], data.shape[0], data.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()
    painter = QPainter(image)
    painter.setPen(QColor(235, 235, 235))
    font = QFont("Segoe UI")
    font.setPixelSize(max(12, data.shape[0] // 18))
    painter.setFont(font)
    painter.drawText(image.rect().adjusted(8, 4, -8, -4), int(Qt.AlignTop | Qt.AlignLeft), title)
    painter.end()
    return image


def _sheet(tiles, columns: int, path: Path) -> None:
    from PySide6.QtGui import QColor, QImage, QPainter
    width, height = tiles[0].width(), tiles[0].height()
    rows = (len(tiles) + columns - 1) // columns
    gap = 4
    sheet = QImage(columns * (width + gap) + gap, rows * (height + gap) + gap, QImage.Format.Format_RGBA8888)
    sheet.fill(QColor(60, 60, 66))
    painter = QPainter(sheet)
    for index, tile in enumerate(tiles):
        painter.drawImage(gap + (index % columns) * (width + gap), gap + (index // columns) * (height + gap), tile)
    painter.end()
    sheet.save(str(path))


def cmd_presets(out_dir: Path, clip_id: str = "human", scale: float = 1.0) -> int:
    """Every curated Spectrum preset at the same loud and quiet instants of one shipped clip (contact sheets, one
    still per preset per instant, a motion strip each) and ``metrics.json``: vividness, contrast and pairwise palette
    distance. Preset 1's own replay picks the instants: the tick with the most drawn bar area (loud) and one at the
    15th percentile of drawn area (quiet). Every curated preset shares Preset 1's reactivity, so the bars match."""
    import numpy as np
    from ui.studio.waveform_recorded_inputs import shipped_clips
    _app()
    clips = {fixture.id.split(":", 1)[1]: fixture.description for fixture in shipped_clips()}
    clip = clips[clip_id]
    out_dir.mkdir(parents=True, exist_ok=True)
    presets = curated_presets()
    target = GLTarget()
    report: dict = {"clip": clip_id, "scale": scale, "presets": {}}
    try:
        def replay(values):
            from ui.studio.spectrum_recorded_inputs import extract
            frames: list = []
            extract(clip, values, frames_out=frames)
            return frames

        base_frames = replay(presets[0][1])
        candidates = list(range(len(base_frames) // 10, len(base_frames), 4))
        area = {i: float((target.render(base_frames[i][1], 1.0)[..., 3] > 64).mean()) for i in candidates}
        loud = max(area, key=area.get)
        ordered = sorted((a, i) for i, a in area.items() if a > 0.02)
        quiet = ordered[int(len(ordered) * 0.15)][1]
        report["instants"] = {"loud_tick": loud, "quiet_tick": quiet, "loud_area": area[loud],
                              "quiet_area": area[quiet]}
        tiles: dict = {"loud": [], "quiet": []}
        renders: dict = {"loud": {}, "quiet": {}}
        for stem, values in presets:
            frames = replay(values)
            entry = {}
            for label, tick in (("loud", loud), ("quiet", quiet)):
                pixels = target.render(frames[tick][1], scale)
                _png(out_dir / f"{label}_{stem}.png", _on_black(pixels))
                entry[label] = look_metrics(pixels)
                renders[label][stem] = pixels
                tiles[label].append(_labelled_tile(pixels, stem.replace("preset_", "").replace("_", " ")))
            strip = [target.render(frame, 1.0) for _now, frame in frames[loud - 12:loud + 12:3]]
            _png(out_dir / f"strip_{stem}.png", _on_black(np.concatenate(strip, axis=0)))
            report["presets"][stem] = entry
            print(stem, {k: {m: v for m, v in e.items() if not m.startswith("palette")} for k, e in entry.items()})
        for label, images in tiles.items():
            _sheet(images, 4, out_dir / f"contact_{label}.png")
    finally:
        target.release()
    stems = list(report["presets"])
    for label in ("loud", "quiet"):
        matrix = {a: {b: round(palette_distance(report["presets"][a][label], report["presets"][b][label]), 2)
                      for b in stems if b != a} for a in stems}
        report[f"palette_distance_{label}"] = matrix
        report[f"nearest_{label}"] = {a: min(row.items(), key=lambda kv: kv[1]) for a, row in matrix.items()}
        pixels = renders[label]
        image = {a: {b: round(image_distance(pixels[a], pixels[b]), 2) for b in stems if b != a} for a in stems}
        report[f"image_distance_{label}"] = image
        report[f"nearest_image_{label}"] = {a: min(row.items(), key=lambda kv: kv[1]) for a, row in image.items()}
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for a in stems:
        loud_m = report["presets"][a]["loud"]
        print(f"{a:34s} chroma {loud_m.get('chroma', 0):.3f} colourful {loud_m.get('colourfulness', 0):6.1f} "
              f"contrast {loud_m.get('contrast_L', 0):5.1f} vs-backdrop {loud_m.get('backdrop_contrast_L', 0):5.1f} "
              f"nearest palette {report['nearest_loud'][a]} image {report['nearest_image_loud'][a]}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("baseline", "compare", "showcase", "presets"):
        sub.add_parser(name).add_argument("path", type=Path)
    sub.choices["showcase"].add_argument("--only", default="", help="only looks whose name contains this")
    sub.choices["presets"].add_argument("--clip", default="human", help="shipped Studio clip id")
    sub.choices["presets"].add_argument("--scale", type=float, default=1.0)
    sub.add_parser("cost").add_argument("path", type=Path, nargs="?")
    args = parser.parse_args(argv)
    if args.command == "baseline":
        return cmd_baseline(args.path)
    if args.command == "compare":
        return cmd_compare(args.path)
    if args.command == "showcase":
        return cmd_showcase(args.path, args.only)
    if args.command == "presets":
        return cmd_presets(args.path, args.clip, args.scale)
    return cmd_cost(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
