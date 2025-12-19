"""Tests for particle transition and shader program."""
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import uuid


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_pixmap(qapp):
    """Create test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.red)
    return pixmap


@pytest.fixture
def test_pixmap2(qapp):
    """Create second test pixmap."""
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.blue)
    return pixmap


class TestParticleProgram:
    """Tests for ParticleProgram shader class."""

    def test_particle_program_import(self):
        """Test that ParticleProgram can be imported."""
        from rendering.gl_programs.particle_program import ParticleProgram
        assert ParticleProgram is not None

    def test_particle_program_instantiation(self):
        """Test ParticleProgram can be instantiated."""
        from rendering.gl_programs.particle_program import ParticleProgram
        program = ParticleProgram()
        assert program is not None
        assert program.name == "Particle"

    def test_particle_program_has_vertex_source(self):
        """Test ParticleProgram has vertex shader source."""
        from rendering.gl_programs.particle_program import ParticleProgram
        program = ParticleProgram()
        assert program.vertex_source is not None
        assert len(program.vertex_source) > 0
        assert "#version" in program.vertex_source

    def test_particle_program_has_fragment_source(self):
        """Test ParticleProgram has fragment shader source."""
        from rendering.gl_programs.particle_program import ParticleProgram
        program = ParticleProgram()
        assert program.fragment_source is not None
        assert len(program.fragment_source) > 100
        assert "#version" in program.fragment_source
        assert "void main()" in program.fragment_source

    def test_particle_program_uniform_names(self):
        """Test ParticleProgram defines expected uniforms."""
        from rendering.gl_programs.particle_program import ParticleProgram
        program = ParticleProgram()
        source = program.fragment_source
        
        expected_uniforms = [
            "u_progress", "u_resolution", "u_seed", "u_mode",
            "u_direction", "u_particle_radius", "u_swirl_turns",
            "u_use_3d", "u_texture_map", "u_wobble", "u_swirl_order",
        ]
        
        for uniform in expected_uniforms:
            assert uniform in source, f"Uniform {uniform} not found in shader"


class TestParticleState:
    """Tests for ParticleState dataclass."""

    def test_particle_state_import(self):
        """Test that ParticleState can be imported."""
        from rendering.transition_state import ParticleState
        assert ParticleState is not None

    def test_particle_state_creation(self):
        """Test ParticleState can be created with defaults."""
        from rendering.transition_state import ParticleState
        state = ParticleState()
        assert state is not None
        assert state.progress == 0.0
        assert state.mode == 0
        assert state.direction == 0

    def test_particle_state_with_values(self, test_pixmap, test_pixmap2):
        """Test ParticleState with custom values."""
        from rendering.transition_state import ParticleState
        state = ParticleState(
            old_pixmap=test_pixmap,
            new_pixmap=test_pixmap2,
            progress=0.5,
            mode=1,
            direction=2,
            particle_radius=32.0,
            swirl_turns=3.0,
            swirl_order=2,
        )
        assert state.progress == 0.5
        assert state.mode == 1
        assert state.direction == 2
        assert state.particle_radius == 32.0
        assert state.swirl_turns == 3.0
        assert state.swirl_order == 2


class TestParticleTransition:
    """Tests for GLCompositorParticleTransition."""

    def test_particle_transition_import(self):
        """Test that particle transition can be imported."""
        from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
        assert GLCompositorParticleTransition is not None

    def test_particle_transition_creation(self):
        """Test particle transition can be created."""
        from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
        
        mock_compositor = MagicMock()
        transition = GLCompositorParticleTransition(
            compositor=mock_compositor,
            duration_ms=1000,
        )
        assert transition is not None
        assert transition.get_duration() == 1000

    def test_particle_transition_modes(self):
        """Test particle transition supports different modes."""
        from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
        
        mock_compositor = MagicMock()
        
        for mode in [0, 1, 2]:  # Directional, Swirl, Converge
            transition = GLCompositorParticleTransition(
                compositor=mock_compositor,
                duration_ms=500,
                mode=mode,
            )
            assert transition._mode == mode

    def test_particle_transition_directions(self):
        """Test particle transition supports different directions."""
        from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
        
        mock_compositor = MagicMock()
        
        for direction in range(10):  # 0-9 directions including random
            transition = GLCompositorParticleTransition(
                compositor=mock_compositor,
                duration_ms=500,
                direction=direction,
            )
            assert transition._direction == direction

    def test_particle_transition_swirl_orders(self):
        """Test particle transition supports different swirl orders."""
        from transitions.gl_compositor_particle_transition import GLCompositorParticleTransition
        
        mock_compositor = MagicMock()
        
        for order in [0, 1, 2]:  # Typical, Center Outward, Edges Inward
            transition = GLCompositorParticleTransition(
                compositor=mock_compositor,
                duration_ms=500,
                mode=1,  # Swirl mode
                swirl_order=order,
            )
            assert transition._swirl_order == order


class TestTransitionFactory:
    """Tests for particle transition creation via factory."""

    def test_factory_import(self):
        """Test TransitionFactory can be imported."""
        from rendering.transition_factory import TransitionFactory
        assert TransitionFactory is not None


class TestSettingsDefaults:
    """Tests for particle settings defaults."""

    def test_settings_manager_has_particle_defaults(self):
        """Test SettingsManager includes particle defaults."""
        from core.settings.settings_manager import SettingsManager
        
        manager = SettingsManager(organization="Test", application=f"ParticleTest_{uuid.uuid4().hex}")

        transitions = manager.get('transitions', {})
        assert 'particle' in transitions, "Particle settings missing from defaults"
        particle = transitions['particle']
        assert particle.get('mode') == 'Converge'
        assert particle.get('swirl_order') == 2  # Edges Inward
        assert particle.get('particle_radius') == 24
        assert particle.get('use_3d_shading') is True
        assert particle.get('texture_mapping') is True

    def test_settings_manager_has_particle_in_pool(self):
        """Test SettingsManager includes Particle in transition pool."""
        from core.settings.settings_manager import SettingsManager
        
        manager = SettingsManager(organization="Test", application=f"ParticlePoolTest_{uuid.uuid4().hex}")

        transitions = manager.get('transitions', {})
        pool = transitions.get('pool', {})
        assert 'Particle' in pool, "Particle missing from transition pool"
        assert pool['Particle'] is True
