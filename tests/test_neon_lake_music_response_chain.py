"""The Neon Lake music-response trace's continuous play: songs chained back to back into one replay (one activation),
so whatever the drives carry from one song into the next shows (``neon_lake_music_response.chain_clips``)."""
from __future__ import annotations

from widgets.spotify_visualizer.feature_frame import FeatureClip


def _song(fixture: str, frames: int = 40) -> FeatureClip:
    from ui.studio.engine_answers import synthetic_features
    return FeatureClip(fixture, tuple(synthetic_features(fixture)[:frames]))


def test_chained_songs_play_back_to_back_on_one_clock_with_fresh_capture_serials():
    from tools.visualizer_replay.neon_lake_music_response import CHAIN_GAP, chain_clips
    first, second = _song("peak"), _song("quiet", 30)
    chained, songs = chain_clips([first, second])
    assert len(chained.frames) == len(first.frames) + len(second.frames)
    assert [(begin, end) for _start, begin, end in songs] == [(0, 40), (40, 70)]
    stamps = [frame.timestamp_us for frame in chained.frames]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)          # one clock, strictly forward
    # The second song starts the gap after the first ends, its own spacing kept, its content unchanged.
    assert stamps[40] - stamps[39] == int(CHAIN_GAP * 1e6)
    assert songs[1][0] == (stamps[40] - stamps[0]) / 1e6
    offset = stamps[40] - second.frames[0].timestamp_us
    assert all(a.timestamp_us + offset == b.timestamp_us for a, b in zip(second.frames, chained.frames[40:]))
    assert all(a.real == b.real for a, b in zip(second.frames, chained.frames[40:]))
    # Capture serials keep rising across the boundary: the second song is new audio, never a stale history.
    serials = [frame.capture_history.capture_serial for frame in chained.frames]
    assert serials == sorted(serials) and serials[40] > serials[39]


def test_the_chained_clip_replays_as_one_activation():
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay.neon_lake_music_response import chain_clips
    chained, _songs = chain_clips([_song("peak", 20), _song("mid", 20)])
    result = replay_clip(chained, "shockwave_grid", snapshots_at=(10, 30))
    assert set(result["snapshots"]) == {10, 30}
