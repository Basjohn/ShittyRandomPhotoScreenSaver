"""The production owner's own configure-and-start path, replayed over a shipped clip (checkpoint audit 6, A6-L5).

    python tools/visualizer_replay/owner_production_replay.py --out <file.json> [--root <tree>] [--modes ...]
        [--seconds 1.5]

``owner_replay`` (``tools/expanded_visualizer_evidence.py``) configures the owner with the offline replays'
``configure_offline_controller`` and never runs the product's configure, bind, Media edge and start. This replay does:
the host binding's own ``VisualizerHostBinding.construct`` builds the real ``QuickDisplayVisualizerOwner`` on an unshown
``QuickDisplayRuntime`` (a stub host around it: no window is shown, created or mapped by this tool), resolving the
activation from the Settings section and passing the production presentation kwargs (``DisplayManager``'s: the model
plus the resolved 3D Detail tier, no Settings manager), then configures, binds, commits Media's state and starts it,
on the in-process path, stated (the engine worker's fallback; the worker, the product's default, is covered by
``owner_worker_gate``'s identity against this same owner in process).
The only substitutions: the recorded ``ReplayBeatEngine`` (deterministic inputs, as every replay) and the cadence
thread (``start_logical_runtime`` keeps the step the owner installed and runs no thread; each recorded frame then
runs that step once, the authored clock pinned to the frame's time, and the owner's ``sync_present`` publishes it).
Media's play edges go through the owner's ``set_playing``. Every logical frame's digest is reported per mode.

``--root`` imports the tree under test from another checkout (the A6-L5 reference: the same run at ``32f28d4f^``, the
commit before the configure refactor); the tool itself uses only interfaces both trees have. Offscreen output only.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GENERATION = 9001
HERE = Path(__file__).resolve().parents[2]


def checked_out(value: str, root: str) -> Path:
    """``--out`` through THIS tree's evidence layout owner (``tools/artifact_paths.py``), before the tree under test
    is imported. When ``--root`` names another checkout, every module the check loaded from this tree (the owner,
    the mode registry it reads) is forgotten again, so the tree under test imports its own."""
    saved = list(sys.path)
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    try:
        from tools import artifact_paths

        return artifact_paths.checked_output(value)
    finally:
        sys.path[:] = saved
        if Path(root).resolve() != HERE:
            for name, module in list(sys.modules.items()):
                if name in ("__main__", __name__):
                    continue
                # ``tools`` is a namespace package: no ``__file__``, only ``__path__``.
                origins = [getattr(module, "__file__", None), *(getattr(module, "__path__", None) or ())]
                if any(origin and Path(origin).resolve().is_relative_to(HERE) for origin in origins):
                    del sys.modules[name]


class _Runtime:
    """The host unit's runtime as the binding sees it: the real runtime, with a window that has no screen (the
    binding reads ``window.screen()`` only to hydrate a committed CUSTOM rect, which this replay has none of)."""

    def __init__(self, real: Any) -> None:
        from types import SimpleNamespace

        self._real = real
        self.window = SimpleNamespace(screen=lambda: None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _Presenter:
    authored_layout_enabled = True

    def authored_geometry_for(self, _widget_id):
        return None

    def presentation_for_widget_id(self, _widget_id):
        return None

    def set_layout_observer(self, _observer) -> None:
        return None

    def set_external_stack_obstacles(self, _obstacles, **_kwargs) -> None:
        return None


class _Host:
    """A host unit around the unshown runtime: only the binding's host surface."""

    def __init__(self, runtime: Any) -> None:
        from rendering.quick.widgets.host import OverlayWidgetGeometry

        self.screen_index = 0
        self.is_retired = False
        self.runtime = _Runtime(runtime)
        self.presenter = _Presenter()
        self.visualizer_owner = None
        self._bounds = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)

    def display_bounds(self):
        return self._bounds

    def attach_visualizer_owner(self, owner) -> None:
        self.visualizer_owner = owner

    def detach_visualizer_owner(self, owner) -> bool:
        self.visualizer_owner = None
        return True


def _presentation_kwargs(model: Any, mode: str) -> dict:
    """``DisplayManager._visualizer_presentation_kwargs`` with no Settings manager (the model plus the 3D tier)."""
    from dataclasses import asdict

    from core.settings.scene3d_quality import resolve_visualizer_tier
    from rendering.quick.bootstrap import last_validated_gpu

    return {**asdict(model), "scene3d_detail": resolve_visualizer_tier(None, str(mode), gpu=last_validated_gpu())}


@contextlib.contextmanager
def _in_process_path():
    """The in-process path, stated (the engine worker is the product's default: on Windows since 8 Nov, on Linux since H3; this replay
    ticks the owner's own in-process cadence step, which is also the worker's fallback). A tree from before the
    default flip (``--root``) has the same field with ``False`` meaning in process."""
    import dataclasses

    from core.diagnostics import experiment_flags

    flags = experiment_flags.active_experiment_flags()
    if not hasattr(flags, "visualizer_engine_worker"):
        yield                                   # a tree from before the engine worker: in process is its only path
        return
    experiment_flags.override_active_flags_for_testing(dataclasses.replace(flags, visualizer_engine_worker=False))
    try:
        yield
    finally:
        experiment_flags.override_active_flags_for_testing(flags)


def production_owner_replay(clip: Any, mode: str, *, preset: int = 0, generation: int = GENERATION) -> list[str]:
    """Per recorded frame of ``clip``, the digest of the logical frame the production owner's own in-process path
    ticks (stated explicitly: the in-process fallback, ``_in_process_path``)."""
    from unittest import mock

    from PySide6.QtWidgets import QApplication

    import tools.expanded_visualizer_evidence as evidence
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.feature_replay import (
        REPLAY_SEED, PcmReanalysis, ReplayBeatEngine, deterministic_clock,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding, VisualizerHostServices

    app = QApplication.instance() or QApplication([])
    reanalysis = PcmReanalysis() if get_visualizer_mode_descriptor(mode).raw_musical_signals else None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0, runtime_generation=generation, screen=app.primaryScreen(), scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    host = _Host(runtime)
    frames = clip.frames
    playing = [bool(frames[0].playing)]
    widgets = {
        "family_activation": {"media": True, "visualizers": True},
        "media": {"enabled": True, "position": "Top Left", "monitor": "1"},
        # The mode switched on (Settings' Mode Activation: the binding would otherwise substitute an enabled mode).
        "spotify_visualizer": {"enabled": True, "visualizers_enabled": True, "mode": mode, f"preset_{mode}": preset,
                               "mode_activation": {mode: True}},
    }
    record: dict = {"owner": None, "unit": None}
    services = VisualizerHostServices(
        admitted_owner=lambda: record["owner"], admitted_unit=lambda: record["unit"],
        record_admission=lambda owner, unit: record.update(owner=owner, unit=unit),
        record_unit=lambda unit: record.update(unit=unit), live_units=lambda: [host],
        caller_retired=lambda: False, widgets_config=lambda: widgets,
        shadow_values=lambda: require_canonical_default("widgets.shadows"),
        thread_manager=lambda: None, process_supervisor=lambda: None, display_power_on=lambda: True,
        set_construct_outcome=lambda *args: record.update(outcome=args),
        committed_layout_profile_resolver=lambda _mode: None, edit_layout_profile_activator=lambda _mode: True,
        transition_failure=lambda _reason: None, presentation_kwargs=_presentation_kwargs,
        media_model_for=lambda _unit: type("Media", (), {"playbackState": "playing" if playing[0] else "paused"})(),
        bind_media=lambda _model: None, disconnect_media=lambda: None, publish_view_orbit_admission=lambda: None,
        release_view_state=lambda: None, cycle_mode=lambda: None, cycle_preset=lambda: None,
        volume_step=lambda _direction: True, refresh_context_menus=lambda: None, refresh_transfer_glyphs=lambda: None,
    )
    digests: list[str] = []
    ticked: list[Any] = []
    steps: list[Any] = []
    real_owner = owner_module.QuickDisplayVisualizerOwner
    real_tick = tick_pipeline.logical_tick

    def recording_tick(state):
        frame = real_tick(state)
        ticked.append(frame)
        return frame

    def keep_step(self, *, step, interval_s):            # the cadence the owner started, without its thread
        del self, interval_s
        steps.append(step)

    owner = None
    try:
        with deterministic_clock() as clock, evidence.fresh_drift_revisions():
            clock[0] = frames[0].timestamp_us / 1_000_000.0
            engines: list = []

            def engine_factory(count):              # the production factory's shape: one engine at the bar count
                engines.append(ReplayBeatEngine(count))
                return engines[-1]

            def build(_runtime, **kwargs):
                return real_owner(runtime, engine_factory=engine_factory, transition_clock=lambda: clock[0], **kwargs)

            with mock.patch.object(owner_module, "QuickDisplayVisualizerOwner", build), \
                    mock.patch.object(tick_pipeline, "logical_tick", recording_tick), \
                    mock.patch.object(VisualizerRuntimeController, "start_logical_runtime", keep_step), \
                    _in_process_path():
                if not VisualizerHostBinding(services).construct(host):
                    raise RuntimeError(f"the binding refused the owner: {record.get('outcome')}")
                owner = record["owner"]
                controller = owner.controller
                if controller.mode_id != mode or len(steps) != 1 or len(engines) != 1:
                    raise RuntimeError(f"the binding built {controller.mode_id} with {len(steps)} cadence starts and "
                                       f"{len(engines)} engines")
                engine = engines[0]
                # The replay's mode-generator seed (Bubble's spawn), as ``configure_offline_controller`` seeds the
                # offline replay's: the product's path never seeds, so the replay seeds its controller before a step.
                controller.seed_mode_generators(REPLAY_SEED)
                for index, feature in enumerate(frames):
                    clock[0] = feature.timestamp_us / 1_000_000.0
                    if bool(feature.playing) != bool(controller.playing):
                        owner.set_playing(bool(feature.playing))          # Media's edge, the owner's own
                    if not engine.accept_feature_frame(feature):
                        raise RuntimeError(f"rejected replay input {clip.name}:{index}")
                    if reanalysis is not None:
                        reanalysis.accept(engine, feature)
                    del ticked[:]
                    steps[-1](clock[0])                                   # the step the owner installed
                    if len(ticked) != 1 or ticked[0] is None:
                        raise RuntimeError(f"the owner's step ticked no logical frame {clip.name}:{index}")
                    digests.append(evidence.frame_digest(ticked[0]))
                    owner.sync_present()
    finally:
        if owner is not None and not owner.is_retired:
            owner.retire()
        runtime.close_runtime()
        factory.deleteLater()
        app.processEvents()
    return digests


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--modes", nargs="*")
    parser.add_argument("--seconds", type=float, default=1.5)
    args = parser.parse_args(argv)
    root = str(Path(args.root).resolve())
    try:
        out = checked_out(args.out, root)
    except ValueError as exc:                   # ArtifactPathError
        parser.error(str(exc))
    sys.path[:] = [root] + [entry for entry in sys.path
                            if Path(entry or ".").resolve() != Path(__file__).resolve().parent]
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    import tools.expanded_visualizer_evidence as evidence
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    if not str(Path(evidence.__file__).resolve()).startswith(root):
        raise RuntimeError(f"imported {evidence.__file__}, not the tree under {root}")
    clip = evidence.shipped_clip(args.seconds)
    modes = args.modes or [d.mode_id for d in iter_all_visualizer_mode_descriptors()]
    report = {"root": root, "clip": clip.name, "seconds": args.seconds, "frames": len(clip.frames), "modes": {}}
    for mode in modes:
        digests = production_owner_replay(clip, mode)
        report["modes"][mode] = {"frames": len(digests), "digests": digests,
                                 "series": hashlib.sha256("".join(digests).encode()).hexdigest()}
        print(f"[OWNER] {mode:18s} {len(digests)} frames {report['modes'][mode]['series'][:16]}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
