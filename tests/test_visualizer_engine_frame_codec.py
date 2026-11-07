"""Native core P2: the exact frame codec (Docs/Future_Work/Native_Core_P2_Engine_Design.md, work order 2).

Every logical frame the production owner publishes, for every mode, round-trips through the codec to the identical
frame (``repr``, the production frame digest's identity) and re-encodes to the identical bytes; a value outside the
canonical domain is refused."""
import pytest

from core.visualizer_engine import frame_codec


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.mark.qt
@pytest.mark.parametrize('mode', _modes())
def test_every_published_frame_round_trips_exactly(qt_app, monkeypatch, mode):
    import tools.expanded_visualizer_evidence as evidence
    seen = []
    digest = evidence.frame_digest

    def checked(logical):
        payload = frame_codec.encode(logical)
        back = frame_codec.decode(payload)
        assert repr(back) == repr(logical), mode
        assert frame_codec.encode(back) == payload        # every field, incl. those repr hides (EB drift sources)
        seen.append(len(payload))
        return digest(logical)

    monkeypatch.setattr(evidence, 'frame_digest', checked)
    evidence.owner_replay(evidence.shipped_clip(1.5), mode)
    assert len(seen) > 30, (mode, len(seen))           # real frames of this mode went through the codec


def test_negative_zero_and_full_precision_survive():
    from widgets.spotify_visualizer.render_state import VisualizerEnergyState, freeze_render_fields
    value = VisualizerEnergyState(bass=-0.0, mid=0.1+0.2, high=1e-308, overall=12345.678901234567)
    back = frame_codec.decode(frame_codec.encode(value))
    assert repr(back) == repr(value) and str(back.bass) == '-0.0'
    fields = freeze_render_fields({'b': b'\x00\xff', 'n': None, 's': 'xé', 't': (1, 2.5, (True, -0.0)), 'z': ()})
    assert repr(frame_codec.decode(frame_codec.encode(fields))) == repr(fields)


def test_a_value_outside_the_canonical_domain_is_refused():
    with pytest.raises(frame_codec.FrameCodecError):
        frame_codec.encode([1.0])                       # lists never reach a frozen frame
    with pytest.raises(frame_codec.FrameCodecError):
        frame_codec.encode(1 << 70)
    with pytest.raises(frame_codec.FrameCodecError):
        frame_codec.decode(b'\x02\x00\x00')             # another codec schema
    payload = frame_codec.encode((1.0, 2.0))
    with pytest.raises(frame_codec.FrameCodecError):
        frame_codec.decode(payload+b'\x00')             # trailing bytes
