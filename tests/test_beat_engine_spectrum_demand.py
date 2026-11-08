"""The analysis-spectrum demand (checkpoint audits 3 A3-M1 and 4 A4-M1): the mode rule's declaration requests ONE
spectrum on its rising edge, so the first commit after an activation publishes; afterwards only the tick's own reads
request publications, as before the rule existed (a standing every-commit publication changed Sphere's production
frames and cost Neon Lake, reaction off, a copy per commit nobody read)."""
from types import SimpleNamespace

from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


def _engine():
    engine = _SpotifyBeatEngine.__new__(_SpotifyBeatEngine)
    engine._pre_agc_analysis_spectrum = ()
    engine._pre_agc_analysis_spectrum_requested = False
    engine._analysis_spectrum_demanded = False
    return engine


def _commit(engine, values):
    engine._publish_pre_agc_analysis_spectrum_if_requested(SimpleNamespace(_freq_values=values))
    return engine._pre_agc_analysis_spectrum


def test_the_declaration_requests_only_the_first_publication():
    engine = _engine()
    engine.set_analysis_spectrum_demand(True)                  # activation: the rising edge
    assert _commit(engine, [1.0, 2.0]) == (1.0, 2.0)           # the first commit publishes before any read
    engine.set_analysis_spectrum_demand(True)                  # declared again every tick: no new request
    assert _commit(engine, [3.0, 4.0]) == (1.0, 2.0)           # no read asked: nothing new is copied
    engine.get_pre_agc_analysis_spectrum()                     # the tick's read requests the next one
    assert _commit(engine, [5.0, 6.0]) == (5.0, 6.0)


def test_an_undemanded_mode_never_publishes_and_a_reset_rearms_the_edge():
    engine = _engine()
    engine.set_analysis_spectrum_demand(False)
    assert _commit(engine, [1.0]) == ()                        # dormant: nothing copied
    engine.set_analysis_spectrum_demand(True)
    _commit(engine, [2.0])
    engine._pre_agc_analysis_spectrum_requested = False        # what an activation's reset does to both
    engine._analysis_spectrum_demanded = False
    engine.set_analysis_spectrum_demand(True)                  # the next activation's first declaration
    assert _commit(engine, [7.0]) == (7.0,)
