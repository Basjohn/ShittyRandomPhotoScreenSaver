from utils.audio_capture import _build_block_size_candidates


def test_block_size_candidates_honor_preference():
    candidates = _build_block_size_candidates(512)
    assert candidates[0] == 512
    # Remaining entries should include all other canonical sizes without duplicates
    assert sorted(candidates[1:]) == [128, 256, 1024]


def test_block_size_candidates_default_order_without_preference():
    assert _build_block_size_candidates(0) == [128, 256, 512, 1024]
    assert _build_block_size_candidates(999) == [128, 256, 512, 1024]
