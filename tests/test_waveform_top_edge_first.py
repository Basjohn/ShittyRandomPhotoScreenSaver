"""Top edge first, floor second (lead review 6 Nov): the floor lift never raises a crest through the card's top edge.

* ``card_span`` supplies, after the scene-axis span, the world y of the card's top edge above the scene axis; a larger
  card shows more world above it.
* With that top supplied, a ribbon whose trough wants a lift keeps its crest (plus the sheet's hang) TOP_CLEARANCE below
  the top: the lift gives way and the floor may be grazed. With room under the top the floor lift is untouched.
* A lift the top lowers eases down at TROUGH_ATTACK, as fast as it rose, not over the slow TROUGH_RELEASE.

Test-owned inputs; structure only, never authored values. Negative controls: the same ribbon without a supplied top
(what main lifted), and the same lowering driven by the floor alone (the slow release)."""
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_scene import SPEC
from core.waveform_ribbon_view import card_span, physical_view, visible_top
from tests.test_waveform_ribbon_camera import camera
from tests.test_waveform_view_sized_rim_and_floor import model_for

DT = 1/90
SPAN = (-8., 8.)
TOP = 9.


def shift(model, crest, trough=3., reset=True):
    """(lift, headroom) for one ribbon with a crest of world height ``crest`` above rest at x=1 and a sheet hanging
    ``trough`` below rest at x=-1, everything inside the view."""
    x = np.tile(np.linspace(-6., 6., 121), (dyn.RIBBON_CAPACITY, 1))
    height = np.where(np.abs(x-1.) < .3, crest, 0.)
    hang = np.where(np.abs(x+1.) < .3, trough, .1)
    lift_value = .5
    headroom = None if model._view_top is None else \
        (model._view_top-dyn.PACKET_FLOOR_HEIGHT)*model.zoom-dyn.TOP_CLEARANCE-lift_value
    room = max(dyn.TROUGH_ROOM_MIN, dyn.PACKET_FLOOR_HEIGHT+lift_value-dyn.TROUGH_CLEARANCE)
    if reset:
        model._trough_time = None          # the first call takes the target at once
    return float(model._height_shift(height, hang, room, x, height, headroom).max()), headroom


def test_card_span_supplies_the_cards_top_edge_and_a_larger_card_shows_more_above_the_axis():
    values = camera(camera_fov=5.)
    small, large = card_span(values, (640., 560.), 280.), card_span(values, (1282., 1005.), 280.)
    assert len(small) == len(large) == 3
    assert large[2] > small[2] > SPEC.pivot[1]
    assert small[2] == visible_top(values, 640./560., 2.)
    # The top is where the pivot's vertical line leaves the frustum: it projects onto the top clip plane.
    view, projection, _, _ = physical_view(values, 640./560., 2.)
    clip = projection@view@np.array((SPEC.pivot[0], small[2], SPEC.pivot[2], 1.))
    assert abs(clip[1]/clip[3]-1.) < 1e-9


def test_the_floor_lift_never_raises_a_crest_through_the_top():
    capped = model_for('Centre Out', span=SPAN+(TOP,))
    free = model_for('Centre Out', span=SPAN)
    high, headroom = shift(capped, crest=6.)
    assert headroom-6.-.1 < .9                         # the crest leaves less room than the trough asks for
    assert abs(high-max(0., headroom-6.-.1)) < 1e-9    # ... so the lift stops at the top (hang .1 at the crest)
    unbounded, _ = shift(free, crest=6.)
    assert unbounded > high+.5                         # negative control: without the top it lifted through it


def test_with_room_under_the_top_the_floor_lift_is_unchanged():
    capped = model_for('Centre Out', span=SPAN+(TOP,))
    free = model_for('Centre Out', span=SPAN)
    assert shift(capped, crest=1.)[0] == shift(free, crest=1.)[0] > 0.


def test_a_lift_the_top_lowers_eases_down_as_fast_as_it_rose():
    def lowered(model, crest_after, trough_after):
        shift(model, crest=1.)                          # lifted for the trough at once
        start = float(model._trough_lift.max())
        for _ in range(round(.4/DT)):
            model.time += DT
            lift, _ = shift(model, crest=crest_after, trough=trough_after, reset=False)
        return start, lift
    capped = model_for('Centre Out', span=SPAN+(TOP,))
    start, by_top = lowered(capped, crest_after=6., trough_after=3.)
    goal = shift(model_for('Centre Out', span=SPAN+(TOP,)), crest=6.)[0]
    assert start-by_top > .7*(start-goal)               # most of the way down within .4 s
    # Negative control: the same lowering asked for by the floor alone (a shallower trough) eases over the release.
    floor = model_for('Centre Out', span=SPAN)
    start_f, by_floor = lowered(floor, crest_after=1., trough_after=3.-(start-goal))
    assert start_f-by_floor < .4*(start-goal)
