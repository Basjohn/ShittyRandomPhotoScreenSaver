"""9/10 SST completeness gate.

Fail-loud canonical defaults are only safe if completeness is proven statically:
every key the runtime can resolve must have a canonical default (or be derivable
by design). This test enumerates the runtime-resolvable keys and asserts each one
resolves, so a future dropped/renamed default fails here at test time instead of
crashing the app (WidgetsTab construction, sphere selection, etc. were exactly
this class of gap during the settings migration).

Reference-independent: unlike ``tools/settings_migration_audit.py``'s pre-migration
diff, this uses only the current canonical authority, so it runs in CI without the
``deleteme/PreSettings`` oracle tree.
"""
from __future__ import annotations

from tools.settings_migration_audit import resolvable_key_gaps


def test_every_runtime_resolvable_key_has_a_canonical_default() -> None:
    gaps = resolvable_key_gaps()
    assert gaps == [], (
        "runtime-resolvable keys with no canonical default (recover the value or "
        "declare it derivable-by-design): "
        + ", ".join(f"widgets.{s}.{k} <- {src}" for s, k, src in gaps)
    )
