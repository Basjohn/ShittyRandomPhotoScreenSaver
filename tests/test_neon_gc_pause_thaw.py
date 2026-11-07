"""The per-generation freeze and the strict Settings retirement barrier coexist without any collection."""
import gc
import weakref

from core.performance.gc_policy import RuntimeGCPolicy


def test_a_thawed_generation_is_released_by_refcount_and_nothing_sweeps():
    class Owner:
        pass

    policy = RuntimeGCPolicy()
    assert policy.start()
    try:
        owner = Owner()
        owner_ref = weakref.ref(owner)
        assert policy.freeze_stable_generation()     # the generation's coordinated reveal
        assert policy.thaw_for_runtime_retirement()  # its teardown
        assert policy.frozen is False and gc.get_freeze_count() == 0
        del owner
        assert owner_ref() is None                   # refcount alone, the barrier's standard (R-53/R-154)
        assert not policy.thaw_for_runtime_retirement()
        assert not hasattr(policy, "collect_thawed_retirement_cycles_once")
    finally:
        policy.stop()


def test_no_thaw_on_an_unfrozen_normal_settings_pause():
    policy = RuntimeGCPolicy()
    policy.start()
    try:
        assert not policy.thaw_for_runtime_retirement()
    finally:
        policy.stop()
