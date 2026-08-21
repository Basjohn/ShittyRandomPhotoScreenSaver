"""Phase-C closure gate: canonical production transitions must all have Quick renderers."""

from rendering.transition_registry import iter_transition_descriptors
from rendering.quick.transitions.implementation_registry import (
    iter_quick_transition_implementations,
)


def test_phase_c_quick_catalog_exactly_matches_canonical_transition_registry():
    canonical_ids = tuple(
        descriptor.stable_id for descriptor in iter_transition_descriptors()
    )
    quick_ids = tuple(
        descriptor.transition_id
        for descriptor in iter_quick_transition_implementations()
    )

    assert len(canonical_ids) == len(set(canonical_ids))
    assert len(quick_ids) == len(set(quick_ids))
    assert set(quick_ids) == set(canonical_ids)
