"""Small Windows Qt integration gates. Run focused, never ask for the chunked suite."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from rendering.runtime_input import RuntimeInputOwner
from core.settings.visualizer_mode_settings import require_mode_settings
from ui.tabs.media.spec_mode_builder import _build_visual_control
from PySide6.QtWidgets import QWidget, QVBoxLayout


def _key(kind, key, shift=False, repeat=False):
    return QKeyEvent(kind, key,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        '', repeat)


def test_framed_flight_keys_are_independent_of_freeform_orbit_and_global_exit(qt_app):
    owner = RuntimeInputOwner(interaction_mode_provider=lambda: True)
    flight, orbit, exits, finished = [], [], [], []
    owner.view_framed_flight_rates_changed.connect(lambda *v: flight.append(v))
    owner.view_orbit_rates_changed.connect(lambda *v: orbit.append(v))
    owner.exit_requested.connect(lambda: exits.append(True))
    owner.view_orbit_finished.connect(lambda: finished.append(True))
    owner.set_view_orbit_enabled(True)
    owner.set_framed_flight_enabled(True)
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W))
    assert flight[-1] == (0., 0., 0., 1.)
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_Shift, True))
    assert flight[-1] == (0., 1., 0., 0.)
    assert owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_Shift))
    assert flight[-1] == (0., 0., 0., 1.)
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_Q))
    assert flight[-1] == (1., 0., 0., 1.)
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_Q, repeat=True))
    assert flight[-1] == (1., 0., 0., 1.)
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_Q))
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_W))
    assert flight[-1] == (0., 0., 0., 0.)
    assert len(finished) == 1 and not exits and not orbit
    owner.set_framed_flight_enabled(False)
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_W))
    assert orbit[-1] == (0., 1.)
    owner.handle_key_release(_key(QEvent.Type.KeyRelease, Qt.Key.Key_W))
    assert owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_Q)) is False
    assert not exits
    owner.handle_key_press(_key(QEvent.Type.KeyPress, Qt.Key.Key_Escape))
    assert exits == [True]
    owner.cleanup()
    owner.deleteLater()


def test_settings_volume_controls_construct_with_initialized_label(qt_app):
    tab = QWidget()
    tab._save_settings = lambda: None
    lay = QVBoxLayout(tab)
    spec = require_mode_settings('extruded_bubble')
    for key in ('extruded_bubble_camera_position', 'extruded_bubble_stream_direction'):
        control = spec.control(key)
        default = ([0., 0., 0.] if key.endswith('camera_position') else
                   [0., -1., 0., 0., 1., 0.])
        row = _build_visual_control(tab, lay, control, default)
        assert row is not None
        assert getattr(tab, key).value() is not None
        assert getattr(tab, key + '_label').text() == control.text(getattr(tab, key).value())
    tab.deleteLater()


def test_shift_wasd_orbits_only_while_unshifted_wasd_travels(qt_app):
    """The EB-only flight input must switch held-key roles without a stuck axis."""
    owner = RuntimeInputOwner(interaction_mode_provider=lambda: True)
    rates, orbit, exits = [], [], []
    owner.view_framed_flight_rates_changed.connect(lambda *v: rates.append(v))
    owner.view_orbit_rates_changed.connect(lambda *v: orbit.append(v))
    owner.exit_requested.connect(lambda: exits.append(True))
    owner.set_view_orbit_enabled(True)
    owner.set_framed_flight_enabled(True)
    press = QEvent.Type.KeyPress
    release = QEvent.Type.KeyRelease
    try:
        assert owner.handle_key_press(_key(press, Qt.Key.Key_A))
        assert rates[-1] == (0., 0., -1., 0.)  # strafe left
        assert owner.handle_key_press(_key(press, Qt.Key.Key_Shift, True))
        assert rates[-1] == (1., 0., 0., 0.)   # same held A becomes yaw left
        assert owner.handle_key_press(_key(press, Qt.Key.Key_Q, True))
        assert rates[-1] == (2., 0., 0., 0.)   # Q stacks with Shift+A
        assert owner.handle_key_release(_key(release, Qt.Key.Key_Q, True))
        assert rates[-1] == (1., 0., 0., 0.)
        assert owner.handle_key_release(_key(release, Qt.Key.Key_Shift))
        assert rates[-1] == (0., 0., -1., 0.)  # role returns to strafe
        assert owner.handle_key_release(_key(release, Qt.Key.Key_A))
        assert rates[-1] == (0., 0., 0., 0.)

        assert owner.handle_key_press(_key(press, Qt.Key.Key_D, True))
        assert rates[-1] == (-1., 0., 0., 0.) # Shift+D yaws right
        assert owner.handle_key_press(_key(press, Qt.Key.Key_W, True))
        assert rates[-1] == (-1., 1., 0., 0.) # Shift+W pitches up, not travels
        assert owner.handle_key_press(_key(press, Qt.Key.Key_D, True, repeat=True))
        assert rates[-1] == (-1., 1., 0., 0.) # no autorepeat accumulation
        assert owner.handle_key_release(_key(release, Qt.Key.Key_D, True))
        assert rates[-1] == (0., 1., 0., 0.)
        assert owner.handle_key_release(_key(release, Qt.Key.Key_W, True))
        assert rates[-1] == (0., 0., 0., 0.)

        # Freeform mode retains WASD orbit, and the remapped Q is never exit.
        owner.set_framed_flight_enabled(False)
        assert owner.handle_key_press(_key(press, Qt.Key.Key_A, True))
        assert orbit[-1] == (1., 0.)
        owner.handle_key_release(_key(release, Qt.Key.Key_A, True))
        assert not owner.handle_key_press(_key(press, Qt.Key.Key_Q))
        assert not exits
    finally:
        owner.cleanup()
        owner.deleteLater()


def test_every_eb_visual_control_constructs_with_label_and_admitted_value(qt_app):
    """Production control construction, not mere source inspection, catches `describe`."""
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import VISUAL_CONTROLS

    tab = QWidget()
    tab._save_settings = lambda: None
    tab._force_visualizer_preset_to_custom = lambda: None
    layout = QVBoxLayout(tab)
    spec = require_mode_settings('extruded_bubble')
    defaults = require_canonical_default('widgets.spotify_visualizer')
    try:
        controls = [c for c in spec.controls if isinstance(c, VISUAL_CONTROLS)]
        assert len(controls) >= 14
        for control in controls:
            widget_row = _build_visual_control(tab, layout, control, defaults[control.key])
            widget = getattr(tab, control.key)
            label = getattr(tab, f'{control.key}_label')
            assert widget_row is not None
            assert label.text() == control.text(widget.value()), control.key
    finally:
        tab.deleteLater()
