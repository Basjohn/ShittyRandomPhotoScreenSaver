"""Event admission and birth geometry, independent of mutable authored presets."""
from dataclasses import replace
from types import SimpleNamespace
import math
import numpy as np
from core.ribbon_bursts import CAPACITY, RibbonAccentControls, RibbonBursts
from core.ribbon_ring import RibbonRing


def controls():
    return RibbonAccentControls({key:(value,value) for key,value in dict(spark_count=36.,spark_lifetime=8.,
        spark_drift=1.,spark_rise=.4,spark_size=5.,spark_light=12.,spark_white=.2).items()})


def snapshot(now=0.):
    ring=RibbonRing(1)
    for index in range(10):ring.append(index/6,[(index-5,2.,0.)],[.5],twists=.7)
    return SimpleNamespace(time=now,ready=True,packet=ring.packet(),head_x=0.,travel=0.,
                           drives=(('sparkle',.4),),realized=(('sparkle',1.),))


def test_sparks_are_born_on_the_actual_rolled_rim_and_silence_cannot_respawn_them():
    field=RibbonBursts();s=snapshot()
    assert field.admit(s,controls(),1.)
    records=np.frombuffer(field.payload,np.float32).reshape(CAPACITY,16)
    born=records[records[:,7]>0]
    assert len(born)==36
    # Independent straight-sheet cross-section; the rim has zero camber and uses the shader's floor map.
    side=np.sign(born[:,2]);raw_y=2.+side*.5*math.cos(.7)
    np.testing.assert_allclose(born[:,2],side*.5*math.sin(.7),atol=1e-6)
    np.testing.assert_allclose(born[:,1],.03+.15*np.logaddexp(0.,(raw_y-.03)/.15),atol=1e-6)
    payload=field.payload
    assert not field.admit(snapshot(.01),controls(),1.)
    assert not field.admit(snapshot(1.),controls(),0.)
    assert field.serial==1 and field.payload is payload
    assert field.visible_payload(8.)==b''


def test_capacity_admission_and_epoch_rebase_preserve_living_births_without_truncation():
    field=RibbonBursts();base=1_000_000_000.
    for index in range(100):assert field.admit(snapshot(base+index*.161),controls(),1.)
    records=np.frombuffer(field.payload,np.float32).reshape(CAPACITY,16)
    age=base+99*.161-field.origin-records[:,3]
    active=(records[:,7]>0)&(age>=0)&(age<records[:,7])
    assert active.sum()==50*36 and field.serial==100
    assert age[active].max()<8. and np.isfinite(records).all()


def test_both_count_handles_reach_event_owned_population():
    baseline=controls()
    def population(pair):
        field=RibbonBursts();ranges={**baseline.ranges,'spark_count':pair}
        assert field.admit(snapshot(),replace(baseline,ranges=ranges),.75)
        return np.count_nonzero(field.records[:,7])
    reference=population((8.,24.))
    assert population((16.,24.))>reference
    assert population((8.,36.))>reference
