"""Full parity evidence must detect changes that positions-only audits miss."""
from dataclasses import replace

from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay.bubble_fidelity import replay_bubbles
from tools.visualizer_replay.bubble_parity import canonical_bytes
from tools.visualizer_replay.driver import load_clips, replay_clip
from widgets.spotify_visualizer.render_state import VisualizerProtectedEdge


def test_full_parity_observer_preserves_replay_and_detects_nonposition_changes(qt_app):
    clip=load_clips()['isolated_impulse']
    index=len(clip.frames)-1
    ordinary=replay_clip(clip,'bubble',settings=frozen_visualizer_settings,snapshots_at=(index,))
    observed,samples,_settings=replay_bubbles(clip,settings=frozen_visualizer_settings,snapshots_at=(index,))
    assert observed['logical_series']==ordinary['logical_series']
    assert observed['snapshots']==ordinary['snapshots']
    snapshot=observed['snapshots'][index]
    state=snapshot.logical.mode_state
    assert state.extras and state.trails and samples[index]
    original=canonical_bytes(snapshot)
    for field in ('extras','trails'):
        values=getattr(state,field)
        altered=replace(state,**{field:(values[0]+.001,*values[1:])})
        candidate=replace(snapshot,logical=replace(snapshot.logical,mode_state=altered))
        assert candidate.logical.mode_state.positions==state.positions
        assert canonical_bytes(candidate)!=original
    edge=VisualizerProtectedEdge(999,'bubble_pop',1.,1.01,{'popped':True})
    candidate=replace(snapshot,logical=replace(snapshot.logical,protected_edges=(edge,)))
    assert candidate.logical.mode_state.positions==state.positions
    assert canonical_bytes(candidate)!=original
    candidate=replace(snapshot,presentation=replace(snapshot.presentation,content_fade=.5))
    assert canonical_bytes(candidate)!=original
