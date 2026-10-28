import math
import numpy as np
import pytest

from core.ribbon_geometry import PathSample
from core.ribbon_packet import MAX_PACKET_BYTES, RIBBON_BYTES, pack_ribbons


def path(n=2, origin=0):
    return ([PathSample(origin+i/60, (i/100, 0, -10), .1, 1e5+i*.1) for i in range(n)],
            [(1, 0, 0)]*n, None)


def test_packet_caps_stride_and_rebased_phase_are_explicit():
    packet = pack_ribbons([path(256, 1e9)]*8, period=.7)
    assert packet.instances == 8 and packet.vertices == 12240
    assert len(packet.payload) == MAX_PACKET_BYTES == 131584
    records = np.frombuffer(packet.payload, np.float32).reshape(8, -1, 4)
    assert records[0, 0, 0] == 256
    assert records[0, 5, 0] == 0  # oldest local coordinate
    assert records[0, 5, 1] == 0  # oldest local twist
    assert records[0, 1, 0] == pytest.approx(1e5 % (2*math.pi))
    # Same material mark after eviction, no normalized-count UV sliding.
    samples, tangents, _ = path(5, 1e9)
    a = np.frombuffer(pack_ribbons([(samples, tangents, None)], period=.7).payload, np.float32).reshape(-1, 4)
    b = np.frombuffer(pack_ribbons([(samples[1:], tangents[1:], None)], period=.7).payload, np.float32).reshape(-1, 4)
    phase_a = (a[0, 2]+a[5+3*4, 0]/a[0, 3]) % 1
    phase_b = (b[0, 2]+b[5+2*4, 0]/b[0, 3]) % 1
    assert phase_a == pytest.approx(phase_b, abs=1e-6)


def test_empty_and_gapped_input_have_no_hidden_population():
    empty = pack_ribbons([])
    assert empty.instances == 0 and empty.vertices == 0 and not empty.payload
    samples, _, _ = path(3)
    packet = pack_ribbons([(samples, [(1, 0, 0), (0, 0, 0), (1, 0, 0)], None)])
    assert not packet.payload


@pytest.mark.parametrize('paths', [[path()]*9, [path(257)],
    [([PathSample(0, (0, 0, -10)), PathSample(65, (1, 0, -10))], [(1, 0, 0)]*2, None)],
    [([PathSample(0, (100000.003, 0, -10)), PathSample(1, (102000.003, 0, -10))], [(1, 0, 0)]*2, None)]])
def test_unrepresentable_or_over_budget_input_is_rejected(paths):
    with pytest.raises(ValueError):
        pack_ribbons(paths)


def test_invalid_subdivision_and_phase_budget_fail_before_any_gpu_admission():
    for divisions in (0, 9, True):
        with pytest.raises(ValueError):
            pack_ribbons([path()], subdivisions=divisions)
    for period in (0, math.nan, 1e-30):
        with pytest.raises(ValueError):
            pack_ribbons([path()], period=period)
