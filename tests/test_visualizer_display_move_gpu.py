"""A display move on the render side (Current_Plan 1C.2): what crosses, what is rebuilt, and that the target is warm.

Two hidden production hosts (``tools/expanded_visualizer_evidence.HiddenDisplayHost``: the production scene and the
real Visualizer render item, each its own GL context, as two display windows have) drawing one real logical controller
(Extruded Bubble, the looped music fixture, a deterministic clock). ``share=True`` puts both contexts in the
application's share group, as every product display window's is (``AA_ShareOpenGLContexts``, proven for Qt Quick's
own context factory by ``.artifacts/evidence/visualizers/expanded/20261112_1c2_root_cause/``). The hop is the
product's retained scene transfer (``QuickSceneController.transfer_visualizer_to``), which every move path runs.
"""
from __future__ import annotations

import time

import numpy
import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy

MODE = "extruded_bubble"
W, H = 480, 270
HOP_AT = 150                     # past the drift step log's 128 steps: a fresh solver could not replay the history
COMPARE = range(HOP_AT + 3, HOP_AT + 15)


@pytest.fixture
def hosts_factory(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production host needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    made = []

    def make(share: bool):
        pair = (HiddenDisplayHost(W, H, dpr=1.0, share=share), HiddenDisplayHost(W, H, dpr=1.0, share=share))
        made.extend(pair)
        return pair
    yield make
    for host in made:
        host.close()


def _render_host(scene):
    node = scene._visualizer_item._retirement._node if scene._visualizer_item is not None else None
    return None if node is None else node.render_host


def _run(hosts, hop_at, *, prewarm_at=None, last=COMPARE[-1]):
    """Replay the fixture into ``hosts[0]``; at ``hop_at`` move the admission to ``hosts[1]``. Returns the frames of
    ``COMPARE`` from whichever host draws, and what the hop saw."""
    from dataclasses import replace

    from tools.expanded_visualizer_evidence import CARD, looped_fixture
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    clip = looped_fixture()
    seen: dict = {"frames": {}}
    with deterministic_clock() as clock:
        current = {"host": hosts[0]}
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=MODE,
                                                 engine_factory=lambda _count, e=engine: e)
        controller.engine = engine
        configure_offline_controller(controller, MODE, 0)
        identity = controller.begin_render_activation(engine_generation=engine.get_generation_id(),
                                                      activation_id=engine.get_activation_id())
        hosts[0].scene.set_visualizer_render_source(controller.render_bridge, identity)

        def resolve():
            return resolve_visualizer_presentation(policy=get_visualizer_presentation_policy(MODE),
                                                   display_size=(W, H), outer_origin=(10.0, 10.0), dpr=1.0, **CARD)

        sync = QuickVisualizerPresentationSync(
            controller, resolve_presentation=resolve,
            commit_presentation=lambda p: current["host"].scene.apply_visualizer_presentation(p, active=True),
            request_present=lambda: current["host"].scene.request_visualizer_present())
        for index, feature in enumerate(clip.frames[:last + 1]):
            clock[0] = feature.timestamp_us / 1_000_000.0
            controller.playing = feature.playing
            engine.set_playback_state(feature.playing)
            engine.accept_feature_frame(feature)
            if prewarm_at is not None and index == prewarm_at:
                record = replace(resolve(), scene_fade=0.002, content_fade=0.0)
                assert hosts[1].scene.begin_visualizer_prewarm(identity, record)
                seen["empty_target"] = None
            if hop_at is not None and index == hop_at:
                target_host = _render_host(hosts[1].scene)
                seen["renderer_before"] = target_host and target_host._implementations.get(MODE)
                seen["prepared_before"] = target_host and target_host.prepared_activation
                seen["units_before"] = target_host and target_host.preparation_progress(
                    identity.mode_id, identity.activation_id)
                hosts[0].scene.transfer_visualizer_to(hosts[1].scene)
                current["host"] = hosts[1]
            assert logical_tick(controller.logical_tick_state) is not None
            sync.sync_latest()
            if prewarm_at is not None and prewarm_at <= index < (hop_at or index + 1) and \
                    current["host"] is hosts[0]:
                hosts[1].scene.feed_visualizer_prewarm(controller.render_bridge.peek())
            hosts[0].render()
            hosts[1].render()
            if prewarm_at is not None and index >= prewarm_at and (hop_at is None or index < hop_at):
                seen.setdefault("prewarm_frames", []).append(hosts[1].read())
                time.sleep(0.035)                    # the render host spaces its preparation units (real time)
            if index in COMPARE:
                seen["frames"][index] = current["host"].read()
        if hop_at is not None:
            seen["renderer_after"] = _render_host(hosts[1].scene)._implementations.get(MODE)
            seen["prepared_after"] = _render_host(hosts[1].scene).prepared_activation
        seen["identity"] = identity
        controller.close_render_admission()
    return seen


def _max_diff(a, b) -> list[int]:
    return [int(numpy.abs(a["frames"][i].astype(int) - b["frames"][i].astype(int)).max()) for i in COMPARE]


def test_extruded_bubbles_drift_history_crosses_a_display_move(hosts_factory):
    """In shared contexts the target continues the source's GPU drift history exactly: every frame after the hop
    equals an uninterrupted run. Controls: two uninterrupted runs are equal; across contexts that do not share (and on
    the pre-1C.2 code, where nothing crossed) the history restarts and every compared frame differs."""
    plain = _run(hosts_factory(True), None)
    assert _max_diff(plain, _run(hosts_factory(True), None)) == [0] * len(COMPARE)       # determinism
    moved = _run(hosts_factory(True), HOP_AT)
    assert _max_diff(moved, plain) == [0] * len(COMPARE)
    unshared = _run(hosts_factory(False), HOP_AT)
    assert all(diff > 0 for diff in _max_diff(unshared, plain))


def test_the_target_is_prepared_before_the_swap_and_shows_nothing_meanwhile(hosts_factory):
    """The target's renderer is built and prepared on its own context while the source draws, at a sub-visible card
    opacity that leaves its frame identical to an empty one; the swap then keeps that very renderer (nothing is
    built on the first visible frame). Control: without the prewarm the target has no renderer at the swap."""
    hosts = hosts_factory(True)
    empty = hosts[1]
    empty.render()
    blank = empty.read().astype(int)
    seen = _run(hosts, HOP_AT, prewarm_at=HOP_AT - 110)        # Extruded Bubble prepares in a few dozen units
    identity = seen["identity"]
    assert seen["renderer_before"] is not None
    assert seen["prepared_before"] == (identity.mode_id, identity.activation_id), seen["units_before"]
    assert seen["renderer_after"] is seen["renderer_before"]
    assert seen["prepared_after"] == (identity.mode_id, identity.activation_id)
    assert max(int(numpy.abs(frame.astype(int) - blank).max()) for frame in seen["prewarm_frames"]) <= 1
    cold = _run(hosts_factory(True), HOP_AT)
    assert cold["renderer_before"] is None
