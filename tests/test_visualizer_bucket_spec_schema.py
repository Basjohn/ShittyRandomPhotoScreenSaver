"""Pure schema alignment for lazy Visualizer Settings disclosure buckets.

Run without Qt, user settings, display drivers, or a live Settings dialog.
A new bucket must be registered before its spec can construct any body:
missing registrations used to crash Bubble at first selection and leave stale UI.
Only schema key alignment is asserted, not authored defaults or presentation.
"""
from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_settings import iter_mode_settings


def test_every_spec_bucket_has_a_canonical_disclosure_identity():
    custom = DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]
    missing = [
        f"{spec.mode_id}:{bucket.key}"
        for spec in iter_mode_settings()
        for bucket in spec.buckets
        if f"{spec.mode_id}:{bucket.key}" not in custom
    ]
    assert missing == [], f"Unregistered Visualizer disclosure buckets: {missing}"
