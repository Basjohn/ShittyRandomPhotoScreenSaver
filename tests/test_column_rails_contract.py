"""Pure semantic permutation contract for the repeated-list CUSTOM editor."""

import itertools

import pytest

from rendering.quick.column_rails import (
    COLUMN_RAIL_IDS, COLUMN_RAILS_PAYLOAD_KEY,
    normalize_column_rails, swap_column_rails,
)


@pytest.mark.parametrize("family", ("reddit", "reddit2", "gmail"))
def test_only_exact_widget_wide_permutations_are_accepted(family):
    authored = COLUMN_RAIL_IDS[family]
    assert COLUMN_RAILS_PAYLOAD_KEY == "column_rails"
    for permutation in itertools.permutations(authored):
        assert normalize_column_rails(family, permutation) == permutation
        assert normalize_column_rails(family, list(permutation)) == permutation
    for invalid in (None, [], [authored[0]] * 3,
                    list(authored[:2]), list(authored) + ["extra"],
                    [0, authored[1], authored[2]],
                    "".join(authored)):
        assert normalize_column_rails(family, invalid) is None
    assert normalize_column_rails("media", authored) is None


@pytest.mark.parametrize("family", ("reddit", "reddit2", "gmail"))
def test_one_swap_is_reversible_and_does_not_mutate_its_source(family):
    authored = COLUMN_RAIL_IDS[family]
    original = list(authored)
    swapped = swap_column_rails(family, original, authored[0], authored[2])
    assert swapped == (authored[2], authored[1], authored[0])
    assert original == list(authored)
    assert swap_column_rails(family, swapped, authored[0], authored[2]) == authored
    assert swap_column_rails(family, authored, authored[0], authored[0]) is None
    assert swap_column_rails(family, authored, authored[0], "missing") is None
