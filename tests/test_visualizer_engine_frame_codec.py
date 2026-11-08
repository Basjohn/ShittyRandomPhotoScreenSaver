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


def test_every_ribbon_style_dataclass_round_trips():
    # Waveform Ribbon's style types reach its frame (shading picks them); RibbonStrays was missing from the type table
    # and a frame carrying it was refused at the worker's publish (found by the owner-on-the-worker identity gate,
    # work order 5 slice 5.2).
    import dataclasses
    import inspect

    import core.ribbon_style as ribbon_style

    styles = [cls for _name, cls in inspect.getmembers(ribbon_style, inspect.isclass)
              if cls.__module__ == ribbon_style.__name__ and dataclasses.is_dataclass(cls)]
    assert {cls.__name__ for cls in styles} >= {"RibbonMaterial", "RibbonSparks", "RibbonStrays"}
    for cls in styles:
        value = cls()
        assert repr(frame_codec.decode(frame_codec.encode(value))) == repr(value), cls


def _codec_garbage(calls) -> list:
    """The codec's own objects that ``calls`` left for the cyclic collector (with automatic collection off)."""
    import gc

    gc.collect()
    gc.disable()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        calls()
        gc.collect()
        return [obj for obj in gc.garbage
                if getattr(obj, "__module__", None) == frame_codec.__name__ and callable(obj)]
    finally:
        gc.set_debug(0)
        gc.garbage.clear()
        gc.enable()


def test_encoding_and_decoding_leave_nothing_for_the_cyclic_collector():
    # R-179: ``encode``'s recursive ``put`` and ``decode``'s recursive ``take`` were closures that referred to themselves
    # through their own cell, so every call left a cycle holding its buffers (the encoded payload being built, or the
    # memoryview over the decoded payload) until the next cyclic collection. The engine worker encodes every frame and
    # the GUI thread decodes it: Waveform Ribbon's worker grew ~32 MB/s between collections (a 60-100 MB sawtooth; the
    # frozen check's 277-286 MB). Negative control: before the fix each call left its closure (``put`` / ``take``)
    # here; the refusal paths (a value outside the domain, trailing bytes) too.
    from widgets.spotify_visualizer.render_state import VisualizerEnergyState, freeze_render_fields

    value = freeze_render_fields({"energy": VisualizerEnergyState(bass=0.1, mid=0.2, high=0.3, overall=0.4),
                                  "wave": tuple(float(index) for index in range(4096)),
                                  "nested": (1, "x", (True, None, b"\x00"))})
    payload = frame_codec.encode(value)              # the type tables are built once, outside the measured calls

    def round_trips() -> None:
        for _ in range(10):
            assert repr(frame_codec.decode(frame_codec.encode(value))) == repr(value)

    def refusals() -> None:
        for call, argument in ((frame_codec.encode, (1.0, [2.0])), (frame_codec.decode, payload + b"\x00")):
            try:
                call(argument)
            except frame_codec.FrameCodecError:
                pass
            else:
                raise AssertionError(f"{call.__name__} accepted {argument!r:.40}")

    assert _codec_garbage(round_trips) == []
    assert _codec_garbage(refusals) == []
