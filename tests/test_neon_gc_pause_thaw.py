"""RUN freeze and strict Settings retirement must coexist without frame-time GC."""
import gc
import weakref

from core.performance.gc_policy import RuntimeGCPolicy


def test_neon_activation_lifetime_freeze_releases_cycles_before_settings_barrier():
    class Owner:
        pass

    policy = RuntimeGCPolicy()
    assert policy.start()
    try:
        owner = Owner()
        owner.callback_cycle = lambda root=owner: root
        owner_ref = weakref.ref(owner)
        # Production's one-shot RUN freeze includes the live Quick generation.
        assert policy.freeze_stable_generation()
        del owner
        assert owner_ref() is not None
        assert policy.thaw_for_runtime_retirement()
        assert policy.frozen is False
        # The existing barrier is allowed to request exactly one sweep only
        # after all Qt/native roots have drained.
        assert policy.collect_thawed_retirement_cycles_once()
        assert owner_ref() is None
        assert not policy.collect_thawed_retirement_cycles_once()
        assert not policy.thaw_for_runtime_retirement()
    finally:
        policy.stop()


def test_no_gc_sweep_on_unfrozen_normal_settings_pause():
    policy = RuntimeGCPolicy()
    policy.start()
    try:
        assert not policy.thaw_for_runtime_retirement()
        assert not policy.collect_thawed_retirement_cycles_once()
    finally:
        policy.stop()
