"""The display's background layer on the native core (Current_Plan.md N5.7a, D7 point 1; D10 point 3).

On the Vulkan rehearsal path (the backend owner's choice, ``rendering.quick.bootstrap``) the display's wallpaper comes
from the native core: ``BackgroundRenderItem`` keeps everything it owns (the presentation image, its identity rule, the
transition run, the timing of every change) and hands each new image to this layer, a native composite item in it that
draws the photo with N4.a's fullscreen pass as a still (``native/core/src/mode_content.h``, "Stills") into a target it
keeps. On OpenGL nothing here is created: production keeps the Python presenter (the retained ``QSGImageNode``,
07486d83) until the background family switches as one unit (N5.2h).

- The photo's textures are the core's: the pixels (the item's ``PresentationImage``, which it keeps) are copied once
  into the core and uploaded by N3.8's job service on a Vulkan device with a second queue (in the frame elsewhere); the
  photo drawn changes at the frame edge its job is published at, and until then the previous photo stays (never a
  blank between two photos). The wrapped-texture bridge of the Python presenter (PR-04) is OpenGL only and is not used.
- The fit and crop is the presenter's one owner, ``rendering.quick.background_placement`` (the Python presenter's
  ``QSGImageNode`` reads it too): the pass's ``u_source_uv``, over the item's own rect.
- At rest nothing is drawn again: the layer's target is retained and the core records only when the photo, the placement
  or the item's size changed; Qt composites the retained texture, opaque, in its opaque pass as it does the retained
  image node (``opaque``), and the frame driver records the layer before every other surface (``layer``, D5.2).
- Fade, never vanish: the layer fades in with its first photo and out when the item's image goes or the core's content
  fails; a lost texture (a node made again) is sent again from the image the item keeps.
- Transitions (N5.2a): the item's run is drawn by the core from the transition's own product fragment (its pack baked
  from the Python renderer's text, ``transition_pack_path``), as data: the two photos are the item's two texture slots
  (the destination uploaded into the other one by its job), every value is the Python renderer's own
  (``FullscreenPassRenderer.block_values``) less the core's members, and the run's clock is the window's
  ``afterAnimating`` while the run lasts (the frame Qt Quick is preparing, as the Python renderer samples the run at its
  render): nothing is connected and nothing is drawn again at rest. Beam's sparks (N5.2b's leftover) follow its
  fragment as instanced quads of their own vertex stage (``transition_program``'s ``instanced``), in the run's program
  only while its Sparks switch is on. N5.2c: a 3D transition (``NativeScenePasses``: Blinds, Cube Turn, Depth Card
  Cascade, Jigsaw) is drawn as its scene (``scene_program``: N4.j's photo environment, its passes and meshes into one
  scene target, the opaque composite), its values the Python renderer's ``scene_values``; the frames its Python
  renderer draws as one photograph exactly are the background's own program on that slot, switched only when what is
  shown changes. A transition with no pass on the core is drawn as
  Crossfade. At the run's end the slots swap and the background's pass draws the destination (the run's last frame is
  the destination itself: no pop).

GUI thread only. Events, never timers: the item's size changes, the window's ``afterSynchronizing`` (once, while the
layer waits for its window's framebuffer), ``afterRendering`` (once after a change, to read the core's verdict) and
``afterAnimating`` (every frame of a run only).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from core.logging.logger import get_logger

logger = get_logger(__name__)

#: The layer's texture and its pass (``background_layer.frag``'s sampler and block).
TEXTURE = "photo"
PASS_NAME = "background_layer"
SAMPLER = "uPhoto"
#: N5.2a: the photo a transition reveals is held in the other slot; at the run's end the slots swap (the destination
#: becomes the photo drawn, with no second upload). A transition's fragment samples the two by its own names.
NEXT_TEXTURE = "photo_next"
OLD_SAMPLER = "uOldTex"
NEW_SAMPLER = "uNewTex"
#: Drawn where a run's transition has no pass on the core (the backend's fallback, ``transition_registry``).
FALLBACK_TRANSITION = "crossfade"
#: N5.2c: a scene's target (its passes draw into it; the opaque composite lays it onto the layer) and its photo
#: environment step (its mipped copy is "<step>.environment").
SCENE_TARGET = "scene"
SCENE_ENVIRONMENT = "environment"


def _other_slot(slot: str) -> str:
    return NEXT_TEXTURE if slot == TEXTURE else TEXTURE


def _fade_ms() -> int:
    """The layer fades in with its first photo and out when it goes (fade, never vanish): the Visualizer's activation
    fade, the product's fade for a surface that appears (read lazily, so importing this module stays light)."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import ACTIVATION_SCENE_FADE_DURATION_S

    return round(ACTIVATION_SCENE_FADE_DURATION_S * 1000.0)


def background_layer_pack_path() -> Path:
    """The pass's fragment pack, baked beside its source by ``tools/regen_qrc.py --shaders`` (the frozen build ships the
    folder with the QML)."""
    from rendering.quick.bootstrap import quick_qml_root

    return quick_qml_root() / "shaders" / "background_layer.frag.qsb"


def background_layer_program(pack: bytes | None = None, texture: str = TEXTURE) -> list:
    """The layer's one pass: the photo (the item's texture ``texture``) over the whole target, replacing it (the photo
    is opaque), sampled linearly with no mips and clamped, as the retained image node samples it."""
    from rendering.native.mode import ModePass, PassSampler

    data = background_layer_pack_path().read_bytes() if pack is None else bytes(pack)
    return [ModePass(PASS_NAME, data, "replace", (PassSampler(SAMPLER, texture, "linear", "clamp", "none"),))]


def transition_pack_path(transition_id: str) -> Path:
    """A fullscreen transition's fragment pack, baked from its Python renderer's own fragment by ``tools/regen_qrc.py
    --shaders`` (shipped with the QML folder)."""
    from rendering.quick.bootstrap import quick_qml_root

    return quick_qml_root() / "shaders" / "transitions" / f"{transition_id}.frag.qsb"


def instanced_pack_paths(name: str) -> tuple[Path, Path]:
    """An instanced pass's vertex and fragment packs (N5.2b's leftover, ``NativeQuadInstances``), baked from its Python
    renderer's own texts beside the transitions' fragment packs."""
    folder = transition_pack_path(name).parent
    return folder / f"{name}.vert.qsb", folder / f"{name}.frag.qsb"


def scene_pack_paths(transition_id: str, pass_name: str) -> tuple[Path, Path]:
    """N5.2c: a scene pass's vertex and fragment packs (``NativeScenePasses``), baked from its Python renderer's own
    texts beside the transitions' fragment packs as ``<transition>_<pass>``."""
    folder = transition_pack_path(transition_id).parent
    stem = f"{transition_id}_{pass_name}"
    return folder / f"{stem}.vert.qsb", folder / f"{stem}.frag.qsb"


def native_transition_renderer(transition_id: str) -> Any:
    """The Python renderer whose values the core's passes read, when the core draws ``transition_id`` (a fragment
    pass, ``NativeFragmentPass``, with its pack shipped, and the packs of every instanced pass it may draw; N5.2c: a
    scene, ``NativeScenePasses``, with the packs of every pass it may draw); None otherwise."""
    from rendering.quick.transitions.fullscreen_pass import NativeFragmentPass
    from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
    from rendering.quick.transitions.native_scene import NativeScenePasses

    try:
        renderer = resolve_quick_transition_renderer(transition_id, enabled_transition_ids=frozenset({transition_id}))
    except ValueError:
        return None                                               # not a transition the product knows
    if isinstance(renderer, NativeScenePasses):
        shipped = all(path.is_file() for p in renderer.native_scene_passes()
                      for path in scene_pack_paths(transition_id, p.name))
        return renderer if shipped else None
    if not transition_pack_path(transition_id).is_file() or not isinstance(renderer, NativeFragmentPass):
        return None
    shipped = all(path.is_file() for p in renderer.instanced_passes for path in instanced_pack_paths(p.name))
    return renderer if shipped else None


def scene_program(renderer: Any, scene: Any, old: str, new: str, destination_size: tuple[int, int]) -> tuple:
    """N5.2c: the program of a run's scene (``NativeScene``): N4.j's photo environment of the new picture (when a pass
    reads it), each pass into the scene target (colour RGBA8 cleared to opaque black and D32F depth, the run's
    samples: the Python renderer's ``SceneTarget`` scope, or Quick's framebuffer, which a one-sample target copies
    exactly), then the opaque composite onto the layer. Returns (passes, targets)."""
    from rendering.native.mode import (BUILTIN_QUAD_MESH, BlendState, CompositeStep, EnvironmentStep, ModePass,
                                       ModeTarget, PassGeometry, PassSampler, TargetAttachment)
    from rendering.quick.scene3d.environment import environment_size
    from rendering.quick.transitions.native_scene import QUAD_MESH

    environment = f"{SCENE_ENVIRONMENT}.environment"
    textures = {"old": old, "new": new, "environment": environment}
    passes: list = []
    if scene.environment:
        passes.append(EnvironmentStep(SCENE_ENVIRONMENT, new, environment_size(destination_size)))
    for p in scene.passes:
        vertex, fragment = (path.read_bytes() for path in scene_pack_paths(renderer.transition_id, p.name))
        samplers = tuple(PassSampler(name, textures[kind], "linear", "clamp",
                                     "linear" if kind == "environment" else "none") for name, kind in p.samplers)
        mesh = BUILTIN_QUAD_MESH if p.mesh == QUAD_MESH else p.mesh
        geometry = PassGeometry(vertex, topology=p.topology, vertices=p.vertices, instances=p.instances, mesh=mesh,
                                instance_from=mesh if p.instances == "mesh" else None)
        blend = p.blend if isinstance(p.blend, str) else BlendState(tuple(p.blend[0]), tuple(p.blend[1]))
        passes.append(ModePass(p.name, fragment, blend, samplers, target=SCENE_TARGET,
                               depth_test="less" if p.depth else None, depth_write=bool(p.depth), geometry=geometry))
    passes.append(CompositeStep("scene_composite", "opaque", f"{SCENE_TARGET}.colour"))
    target = ModeTarget(SCENE_TARGET, (TargetAttachment("colour", "rgba8", clear=(0.0, 0.0, 0.0, 1.0)),), depth=True,
                        samples=max(1, int(scene.samples)))
    return passes, (target,)


def scene_mesh(mesh: Any) -> tuple:
    """N5.2c: a run's mesh (``NativeSceneMesh``) as ``NativeMode.mesh`` takes it: (vertices, layout, instances,
    instance layout)."""
    from rendering.native.mode import MeshAttribute, RecordLayout

    def layout(attributes) -> Any:
        if not attributes:
            return None
        found, offset = [], 0
        for name, components in attributes:
            found.append(MeshAttribute(name, int(components), offset))
            offset += 4 * int(components)
        return RecordLayout(offset, tuple(found))

    return bytes(mesh.vertices), layout(mesh.attributes), (None if mesh.instances is None else bytes(mesh.instances)), \
        layout(mesh.instance_attributes)


def scene_settings(renderer: Any, run: Any, sample: Any, logical_size: tuple[float, float]) -> dict:
    """N5.2c: the scene program's settings for this frame: the renderer's own values (``scene_values``, its one owner)
    less the core's members, an array given flat."""
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.transitions.native_scene import flat_values

    values = flat_values(renderer.scene_values(run, sample, logical_size))
    return {name: _flat(value) for name, value in values.items() if name not in MODE_CORE_MEMBERS}


def transition_program(transition_id: str, old: str, new: str, pack: bytes | None = None,
                       instanced: tuple = ()) -> list:
    """The transition's fragment pass over the whole target (replace): its two pictures bound to the item's textures
    ``old`` and ``new``, in the Python renderer's sampler state (linear, clamped, no mips); then each of ``instanced``
    (``NativeQuadInstances``, the run's ``native_instanced_passes``): the built-in quad drawn its instances from its own
    vertex stage, blended over the picture as the Python renderer blends it."""
    from rendering.native.mode import BUILTIN_QUAD_MESH, ModePass, PassGeometry, PassSampler

    data = transition_pack_path(transition_id).read_bytes() if pack is None else bytes(pack)
    passes = [ModePass(transition_id, data, "replace",
                       (PassSampler(OLD_SAMPLER, old, "linear", "clamp", "none"),
                        PassSampler(NEW_SAMPLER, new, "linear", "clamp", "none")))]
    for extra in instanced:
        vertex, fragment = (path.read_bytes() for path in instanced_pack_paths(extra.name))
        passes.append(ModePass(extra.name, fragment, extra.blend,
                               geometry=PassGeometry(vertex, topology="triangle_strip", mesh=BUILTIN_QUAD_MESH,
                                                     vertices="mesh", instances=int(extra.instances))))
    return passes


def transition_settings(renderer: Any, run: Any, sample: Any, logical_size: tuple[float, float],
                        device_pixel_ratio: float) -> dict:
    """The pass's settings for this frame of ``run``: the Python renderer's own block values (its one owner,
    ``NativeFragmentPass.block_values``), less the members the core fills from the item (its conventions). An array
    member's elements (Surface Tension's pools, N5.2b) are given flat: the core packs them at the reflected stride."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    values = renderer.run_values(run, sample, logical_size, device_pixel_ratio)
    return {name: _flat(value) for name, value in values.items() if name not in MODE_CORE_MEMBERS}


def _flat(value: Any) -> Any:
    """A value of nested sequences as one flat list of its numbers (an array of vectors); anything else as it is."""
    if not isinstance(value, (tuple, list)) or not any(isinstance(item, (tuple, list)) for item in value):
        return value
    return [number for item in value for number in (_flat(item) if isinstance(item, (tuple, list)) else (item,))]


def background_layer_settings(pixel_size: tuple[int, int], logical_size: tuple[float, float]) -> dict:
    """The pass's settings for a photo of ``pixel_size`` over an item of ``logical_size``: the presenter's placement."""
    from rendering.quick.background_placement import background_placement

    return {"u_source_uv": list(background_placement(pixel_size, logical_size).source_uv)}


def background_card(logical_size: tuple[float, float], ratio: float) -> dict:
    """The layer's card (``rendering.native.mode.MODE_CARD_KEYS``): the display's background, upright, at ``ratio``,
    its own rect as its target. A transition's pass reads ``uItemSize`` from it (N5.2a; the background's own pass reads
    no card member); the maps are the item's own target's."""
    width, height = (float(v) for v in logical_size)
    ratio = float(ratio) if ratio > 0.0 else 1.0
    return {"quarters": 0, "item_size": [width, height], "oriented_size": [width, height], "dpr": ratio,
            "content_fade": 1.0, "border_width": 0.0, "window_from_target": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            "item_from_window": [1.0 / ratio, 0.0, 0.0, 0.0, 1.0 / ratio, 0.0]}


def native_background_wanted(backend: str | None = None) -> bool:
    """Whether the display's background comes from the native core on ``backend`` (the process's when None): Vulkan."""
    if backend is None:
        from rendering.quick.bootstrap import quick_backend_api

        backend = quick_backend_api()
    return str(backend) == "vulkan"


class NativeBackgroundLayer:
    """One display's background layer: a native composite item in ``item`` (the ``BackgroundRenderItem``) drawing the
    photo the item hands it."""

    def __init__(self, core: Any, item: Any, clock_ns: Callable[[], int] = time.monotonic_ns) -> None:
        self._core = core
        self._item = item
        self._mode: Any = None
        self._image: Any = None          # the PresentationImage drawn (the item keeps it; the core's copy goes)
        self._slot = TEXTURE             # the item's texture that holds it
        # N5.2a: the run drawn (its destination in the other slot) and the per-frame clock's edge.
        self._run: Any = None
        self._renderer: Any = None
        self._next_image: Any = None
        self._clock_ns = clock_ns
        self._clock_window: Any = None
        self._fallback_logged = False
        # N5.2c: a scene run's scene (``NativeScene``), what the layer shows of it (the program drawn: the effect, or
        # one photograph by the background's own program) and the meshes it sent.
        self._scene: Any = None
        self._show: int | None = None
        self._meshes: list[str] = []
        self.runs = 0                    # runs the core drew
        self.ticks = 0                   # frames of a run given their progress
        self._settings: dict | None = None
        self._placed: tuple | None = None
        self._shown = False
        self._failure: str | None = None
        self._edges: dict[str, Any] = {}
        self.closed = False
        self.sent = 0                    # images handed to the core
        self.resent = 0                  # images sent again after a lost edge

    # ---------------------------------------------------------------------------------------------------- the layer

    @property
    def mode(self) -> Any:
        return self._mode

    def _ensure(self) -> Any:
        if self._mode is None:
            mode = self._core.mode(self._item)
            # Hidden until its first photo, then faded in; a background layer, opaque, never clipped (it is the display).
            mode.composite.set(rect=[0.0, 0.0, 0.0, 0.0], coverage=None, quarters=0, visible=False, opacity=1.0,
                               layer="background", opaque=True)
            mode.still(True)
            mode.program(background_layer_program())
            mode.on_textures_lost(self._textures_lost)
            mode.on_meshes_lost(self._meshes_lost)                # N5.2c: a scene run's meshes after a remake
            self._mode = mode
        return self._mode

    def present(self, image: Any) -> None:
        """The item's presentation image changed (``None``: it has none). Never raises: a failure fades the layer out
        and is logged once until the layer draws again."""
        if self.closed:
            return
        try:
            self._present(image)
        except Exception as exc:
            self._fail(f"the background layer could not take the image: {exc}", exc)

    def _present(self, image: Any) -> None:
        if self._run is not None:
            if image is not None and self._next_image is not None and image.identity == self._next_image.identity:
                return                                            # the run's destination: drawn at its end
            self._end_run()                                       # another picture: the run gives way to it
        if image is None:
            self._image = None
            self._hide()
            return
        mode = self._ensure()
        if self._image is None or image.identity != self._image.identity:   # the item's identity rule: one content
            mode.texture(self._slot, image.rgba8, image.pixel_size)
            self.sent += 1
        self._image = image
        self._sync(force=True)

    # ---------------------------------------------------------------------------------------------- the transition

    def transition(self, run: Any) -> None:
        """The item's transition run changed (N5.2a; ``None``: it ended). A run is drawn by the core from its own
        fragment over the photo drawn, its destination in the other slot, its progress given every frame by the
        window's ``afterAnimating`` (the run's clock, ``tick``). At its end the destination is the photo drawn (the
        slots swap; nothing is uploaded again). Never raises: a failure ends the run at once (the photo stays, then
        the destination follows as the item hands it over)."""
        if self.closed:
            return
        try:
            if run is None:
                self._end_run()
            elif self._run is None or run.run_id != self._run.run_id:
                self._start_run(run)
        except Exception as exc:
            logger.error("[BACKGROUND][NATIVE] The transition could not be drawn natively; it ends as a cut",
                         exc_info=exc)
            try:
                self._end_run()
            except Exception:
                logger.debug("[BACKGROUND][NATIVE] ending the failed transition failed", exc_info=True)

    def _start_run(self, run: Any) -> None:
        if self._run is not None:
            self._end_run()
        from rendering.quick.transitions.native_scene import NativeScenePasses

        request = run.request
        renderer = native_transition_renderer(request.transition_id)
        transition_id = request.transition_id
        scene_run = isinstance(renderer, NativeScenePasses)          # N5.2c
        instanced = () if renderer is None or scene_run else renderer.native_instanced_passes(request.parameter_dict())
        if renderer is None:
            if not self._fallback_logged:
                logger.warning("[BACKGROUND][NATIVE] %s has no pass on the core; drawn as %s", transition_id,
                               FALLBACK_TRANSITION)
                self._fallback_logged = True
            transition_id, renderer = FALLBACK_TRANSITION, native_transition_renderer(FALLBACK_TRANSITION)
        mode = self._ensure()
        if self._image is None or request.source_image.identity != self._image.identity:
            mode.texture(self._slot, request.source_image.rgba8, request.source_image.pixel_size)
            self._image = request.source_image
            self.sent += 1
        other = _other_slot(self._slot)
        destination = request.destination_image
        mode.texture(other, destination.rgba8, destination.pixel_size)
        self.sent += 1
        self._run, self._renderer, self._next_image = run, renderer, destination
        if scene_run:
            self._start_scene(mode, run, renderer)
        else:
            mode.program(transition_program(transition_id, self._slot, other, instanced=instanced),
                         self._frame_settings())
        self._settings = None                                     # the background's settings are given again at the end
        self.runs += 1
        self._connect_clock()
        mode.update()

    def _logical(self) -> tuple[float, float]:
        return float(self._item.width()), float(self._item.height())

    def _start_scene(self, mode: Any, run: Any, renderer: Any) -> None:
        """N5.2c: a scene run (``NativeScenePasses``): its meshes sent once, then its first frame. The layer draws the
        old picture until the effect starts (the background's program on its slot, as it draws it now)."""
        from rendering.quick.transitions.native_scene import SHOW_OLD

        scene = renderer.native_scene(run, self._logical())
        for mesh in scene.meshes:
            vertices, layout, instances, instance_layout = scene_mesh(mesh)
            mode.mesh(mesh.name, vertices, layout, instances=instances, instance_layout=instance_layout)
            self._meshes.append(mesh.name)
        self._scene = scene
        self._show = SHOW_OLD
        self._scene_frame()

    def _scene_frame(self) -> None:
        """N5.2c: this frame of a scene run: the effect's program with this frame's values (only its settings once it
        is drawn), or one of the two photographs exactly by the background's own program (the frames the Python
        renderer draws as the plain picture), switched only when what is shown changes."""
        from rendering.quick.transitions.native_scene import SHOW_EFFECT, SHOW_OLD

        run, renderer, mode = self._run, self._renderer, self._mode
        sample = run.sample(self._clock_ns())
        show = renderer.scene_show(run, sample)
        logical = self._logical()
        if show == SHOW_EFFECT:
            settings = scene_settings(renderer, run, sample, logical)
            if self._show != SHOW_EFFECT:
                passes, targets = scene_program(renderer, self._scene, self._slot, _other_slot(self._slot),
                                                self._next_image.pixel_size)
                mode.program(passes, settings, targets=targets)
            else:
                mode.settings(settings)
        elif show != self._show:
            slot, image = ((self._slot, self._image) if show == SHOW_OLD
                           else (_other_slot(self._slot), self._next_image))
            mode.program(background_layer_program(texture=slot), background_layer_settings(image.pixel_size, logical))
        self._show = show

    def _frame_settings(self) -> dict:
        sample = self._run.sample(self._clock_ns())
        logical = (float(self._item.width()), float(self._item.height()))
        window = self._item.window()
        ratio = float(window.effectiveDevicePixelRatio()) if window is not None else 1.0
        return transition_settings(self._renderer, self._run, sample, logical, ratio)

    def tick(self) -> None:
        """The run's clock (the window's ``afterAnimating``, GUI thread, once per frame while a run is drawn): this
        frame's progress and time, as the Python renderer samples the run at its render. Never raises."""
        if self.closed or self._run is None or self._mode is None:
            return
        try:
            if self._scene is not None:
                self._scene_frame()                               # N5.2c
            else:
                self._mode.settings(self._frame_settings())
            self._mode.update()
            self.ticks += 1
        except Exception as exc:
            logger.error("[BACKGROUND][NATIVE] The transition's frame could not be given; it ends as a cut",
                         exc_info=exc)
            self._end_run()

    def _end_run(self) -> None:
        run, self._run = self._run, None
        self._disconnect_clock()
        self._renderer = None
        meshes, self._meshes = self._meshes, []                   # N5.2c: a scene run's, removed once not drawn
        self._scene = self._show = None
        if run is None or self._mode is None:
            self._next_image = None
            return
        destination, self._next_image = self._next_image, None
        previous = self._slot
        if destination is not None:
            self._slot, self._image = _other_slot(previous), destination
        if self._image is None:
            return
        settings = background_layer_settings(self._image.pixel_size,
                                             (float(self._item.width()), float(self._item.height())))
        self._mode.program(background_layer_program(texture=self._slot), settings)
        self._settings = settings
        if destination is not None:
            self._mode.remove_texture(previous)                   # the source goes once the destination is drawn
        for name in meshes:
            self._mode.remove_mesh(name)                          # N5.2c: after the program that drew them went
        self._sync(force=True)

    def _connect_clock(self) -> None:
        window = self._item.window()
        if window is None or self._clock_window is window:
            return
        self._disconnect_clock()
        window.afterAnimating.connect(self.tick)
        self._clock_window = window

    def _disconnect_clock(self) -> None:
        window, self._clock_window = self._clock_window, None
        if window is None:
            return
        try:
            window.afterAnimating.disconnect(self.tick)
        except (RuntimeError, TypeError):
            pass

    def geometry_changed(self) -> None:
        """The item's size changed (or its window's pixels): the layer is placed again. Never raises."""
        if self.closed or self._mode is None:
            return
        try:
            self._sync(force=False)
        except Exception as exc:
            self._fail(f"the background layer could not be placed: {exc}", exc)

    def _sync(self, *, force: bool) -> None:
        mode = self._mode
        image = self._image
        if mode is None or image is None:
            return
        width, height = float(self._item.width()), float(self._item.height())
        changed = force
        settings = background_layer_settings(image.pixel_size, (width, height))
        if self._run is None and settings != self._settings:      # a run's pass takes its own settings (tick)
            mode.settings(settings)
            self._settings = settings
            changed = True
        placed = (width, height, self._pixel_ratio())
        if placed != self._placed or force:
            changed = True
            if width > 0.0 and height > 0.0:
                window = self._item.window()
                ratio = placed[2][0] if placed[2] is not None else (
                    float(window.effectiveDevicePixelRatio()) if window is not None else 1.0)
                mode.card(background_card((width, height), ratio))       # unchanged: records nothing
            config: dict = {"rect": [0.0, 0.0, width, height]}
            if placed[2] is not None:
                config["pixel_ratio"] = list(placed[2])
            if not self._shown and self._failure is None and width > 0.0 and height > 0.0:
                config.update(visible=True, fade_ms=_fade_ms())   # fade, never vanish: in with its first photo
                self._shown = True
            mode.composite.set(**config)
            self._placed = placed
        if not changed:
            return                                                # nothing new: no frame asked for (never a loop)
        mode.update()
        self._arm("afterRendering")                               # the core's verdict, once this change has rendered

    def _pixel_ratio(self) -> tuple[float, float] | None:
        """The window's own logical-to-framebuffer ratio (audit 14 Nov, H1: not the dpr where the window's logical
        size is rounded), from the framebuffer the native item read at its last sync; None until it has read it (the
        window's device pixel ratio is used meanwhile, and the window's next synchronisation places the layer again)."""
        from rendering.native.composite import window_pixel_ratio

        window = self._item.window()
        pixels = self._mode.composite.window_pixels() if self._mode is not None else None
        if window is None or pixels is None:
            self._arm("afterSynchronizing")
            return None
        size = window.size()
        return window_pixel_ratio((float(size.width()), float(size.height())), pixels)

    def _hide(self) -> None:
        if self._mode is not None and self._shown:
            self._mode.composite.set(visible=False, fade_ms=_fade_ms())   # fade, never vanish
            self._shown = False

    def _fail(self, message: str, exc: BaseException | None = None) -> None:
        if self._failure is None:
            logger.error("[BACKGROUND][NATIVE] %s; the layer fades out until it draws again", message,
                         exc_info=exc)
        self._failure = message
        try:
            self._hide()
        except Exception:
            logger.debug("[BACKGROUND][NATIVE] fading the layer out failed", exc_info=True)

    def _verdict(self) -> None:
        """After a change rendered: a content that failed to build fades the layer out; one that draws again (after a
        failure) fades it back in."""
        if self._mode is None:
            return
        status = self._mode.composite.content_status()
        if status is None:
            return
        if status.failing:
            self._fail(f"the background layer's content failed to build ({status.failures} failure(s))")
        elif self._failure is not None and status.draws > 0 and self._image is not None:
            logger.info("[BACKGROUND][NATIVE] The background layer draws again; it fades back in")
            self._failure = None
            self._sync(force=True)

    def _textures_lost(self, names: list[str]) -> None:
        """The core lost the photo's texture (a node made again): it is sent again from the image the item keeps."""
        if self.closed or self._mode is None:
            return
        held = {self._slot: self._image, _other_slot(self._slot): self._next_image}
        lost = [(name, held[name]) for name in names if held.get(name) is not None]
        if not lost:
            return
        try:
            for name, image in lost:
                self._mode.texture(name, image.rgba8, image.pixel_size)
                self.resent += 1
            self._mode.update()
        except Exception as exc:
            self._fail(f"the background layer could not send its photo again: {exc}", exc)

    def _meshes_lost(self, names: list[str]) -> None:
        """N5.2c (playbook checklist 13): a content made again mid-run has nothing to upload the scene's meshes from:
        they are sent again from the run's scene and the run goes on (the photographs come back by ``_textures_lost``,
        the photo environment is the core's own and is drawn again once its photograph is). Never raises."""
        if self.closed or self._mode is None or self._scene is None:
            return
        held = {mesh.name: mesh for mesh in self._scene.meshes}
        lost = [held[name] for name in names if name in held and name in self._meshes]
        if not lost:
            return
        try:
            for mesh in lost:
                vertices, layout, instances, instance_layout = scene_mesh(mesh)
                self._mode.mesh(mesh.name, vertices, layout, instances=instances, instance_layout=instance_layout)
                self.resent += 1
            self._mode.update()
        except Exception as exc:
            logger.error("[BACKGROUND][NATIVE] The transition's meshes could not be sent again; it ends as a cut",
                         exc_info=exc)
            self._end_run()

    # ---------------------------------------------------------------------------------------------------- the edges

    def _arm(self, signal: str) -> None:
        from rendering.quick.visualizer.native_route import _WindowEdge

        window = self._item.window()
        if window is None:
            return
        edge = self._edges.get(signal)
        if edge is None:
            edge = self._edges[signal] = _WindowEdge(signal, lambda s=signal: self._edge_fired(s))
        edge.arm(window)

    def _edge_fired(self, signal: str) -> None:
        if self.closed:
            return
        try:
            if signal == "afterRendering":
                self._verdict()
            else:
                self._sync(force=False)
        except Exception as exc:
            self._fail(f"the background layer's {signal} edge failed: {exc}", exc)

    def close(self) -> None:
        """The layer goes with its display generation (before the scene root is deleted). Idempotent."""
        if self.closed:
            return
        self.closed = True
        self._disconnect_clock()
        self._run = self._renderer = self._next_image = None
        self._scene = self._show = None                           # N5.2c: its meshes go with the mode
        self._meshes = []
        for edge in self._edges.values():
            try:
                edge.disarm()
            except Exception:
                pass
        mode, self._mode = self._mode, None
        self._image = None
        if mode is not None:
            try:
                mode.retire()                     # the lost listener goes with it (audit N38 L4)
            except Exception:
                logger.debug("[BACKGROUND][NATIVE] retiring the layer failed", exc_info=True)
            mode.composite.destroy()

    def state(self) -> dict:
        """The layer's composite and content (the harness's and the rehearsal's reading)."""
        if self._mode is None:
            return {"made": False, "closed": self.closed}
        return {"made": True, "closed": self.closed, "shown": self._shown, "failure": self._failure,
                "sent": self.sent, "resent": self.resent, "slot": self._slot,
                "run": None if self._run is None else self._run.run_id, "runs": self.runs, "ticks": self.ticks,
                "clock_connected": self._clock_window is not None, "composite": self._mode.composite.state(),
                "mode": self._mode.state()}


def attach_native_background(item: Any, backend: str | None = None) -> NativeBackgroundLayer | None:
    """On the native background's backend: the layer of ``item`` (a ``BackgroundRenderItem``) from the process's native
    core (``rendering.quick.bootstrap.native_core``). Elsewhere None, and nothing is created."""
    if not native_background_wanted(backend):
        return None
    from rendering.quick.bootstrap import native_core

    core = native_core()
    if core is None:
        raise RuntimeError("the native background layer needs the native core (start_quick_backend on Vulkan)")
    return NativeBackgroundLayer(core, item)


__all__ = ["FALLBACK_TRANSITION", "NEW_SAMPLER", "NEXT_TEXTURE", "NativeBackgroundLayer", "OLD_SAMPLER", "PASS_NAME",
           "SAMPLER", "TEXTURE", "attach_native_background", "background_card", "background_layer_pack_path",
           "background_layer_program",
           "background_layer_settings", "instanced_pack_paths", "native_background_wanted", "native_transition_renderer",
           "SCENE_ENVIRONMENT", "SCENE_TARGET", "scene_mesh", "scene_pack_paths", "scene_program", "scene_settings",
           "transition_pack_path", "transition_program", "transition_settings"]
