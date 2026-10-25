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
        # The barrier requests the retirement sweep only after all Qt/native roots have drained.
        assert policy.collect_retirement_cycles()
        assert owner_ref() is None
        assert not policy.retirement_collection_pending
        assert not policy.thaw_for_runtime_retirement()      # no second freeze, so nothing to thaw
    finally:
        policy.stop()


def test_a_later_unfrozen_retirement_also_sweeps_its_cycles():
    """Later generations are not frozen but are just as long-lived (the oldest GC generation, scanned rarely):
    each retirement's sweep reclaims their callback cycles; without it the barrier timed out."""
    class Owner:
        pass

    policy = RuntimeGCPolicy()
    policy.start()
    try:
        owner = Owner()
        owner.callback_cycle = lambda root=owner: root
        owner_ref = weakref.ref(owner)
        gc.collect()                                        # promote it to the oldest generation, as in a session
        del owner
        assert not policy.thaw_for_runtime_retirement()
        assert policy.collect_retirement_cycles()
        assert owner_ref() is None
    finally:
        policy.stop()


def test_no_sweep_without_an_active_policy():
    policy = RuntimeGCPolicy()
    assert not policy.collect_retirement_cycles()
