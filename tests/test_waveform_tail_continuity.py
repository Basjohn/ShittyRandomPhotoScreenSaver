"""Side-angle tail stagger (operator, 5 Nov: "if you make the camera angle all the way to the side the outgoing part of
the waveform staggers"). From the framed camera's extreme turn the far end of the history and its continuation are in
view. Per logical tick, the cloth at FIXED scene positions near and beyond the tail must move as smoothly as the
interior: no step at each knot admission/eviction. Evaluated with the Qt-free mirror of the shader's cloth
(core.ribbon_continuation.cloth_values with the packet's admission phase). Test-owned controls; structure only."""
from tests.test_waveform_ribbon_dynamics import primed
from tools.visualizer_replay.waveform_ribbon_tail_probe import measure


def test_the_tail_and_its_continuation_flow_as_smoothly_as_the_interior():
    result = measure(primed(), seconds=4.)
    assert result['tail'] <= 3.*result['interior']+1e-3, result
    assert result['continuation'] <= 3.*result['interior']+1e-3, result


def test_negative_control_the_end_knot_continuation_steps_at_every_admission():
    result = measure(primed(), seconds=4., legacy=True)
    assert result['tail'] > 10.*result['interior']+1e-3, result
