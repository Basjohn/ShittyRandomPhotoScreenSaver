"""The production owner's own configure-and-start path ticks the offline replay's frames (checkpoint audit 6, A6-L5).

``owner_replay`` (the reference every engine-worker identity gate compares against) configures with the offline
replays' ``configure_offline_controller``; the product configures through the host binding's ``construct`` (the
activation resolved from Settings, the owner's ``configure`` with it, bind, Media's play edge, ``start`` and its
cadence). ``tools/visualizer_replay/owner_production_replay.py`` replays a shipped clip through that real path (the
recorded engine, the owner's installed cadence step run once per frame, no thread, no window shown). For every mode its
frames equal the offline replay's, once both build the engine at the mode's bar count (the binding's construction):
so the engine-worker identity gates, which compare against the offline replay, compare against the product's frames.

The same replay at ``32f28d4f^`` (before the configure refactor) gave identical digests for every mode (A6-L5 record in
``Docs/Future_Work/Native_Core_P2_Engine_Design.md``); this test keeps the real path tied to the offline one."""
import pytest


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.mark.qt
@pytest.mark.parametrize("mode", _modes())
def test_the_production_owner_path_ticks_the_offline_replays_frames(qt_app, mode):
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay.owner_production_replay import production_owner_replay
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    clip = evidence.shipped_clip(1.5)
    bar_count = offline_activation_request(mode)["settings_model"].resolve_bar_count(mode)
    production = production_owner_replay(clip, mode)
    offline = evidence.owner_replay(clip, mode, generation=9001, bar_count=bar_count)["digests"]
    assert len(production) == len(clip.frames) > 30
    assert production == offline, (mode, next(i for i, (a, b) in enumerate(zip(production, offline)) if a != b))
