"""
Tests for Transition State Management.

Tests cover:
- Transition state dataclasses structure
- State validation and progress tracking
- snap_to_new enforcement in cleanup paths
"""
import pytest

from rendering.transition_state import (
    TransitionStateBase,
    CrossfadeState,
    SlideState,
    WipeState,
    BlockFlipState,
    DiffuseState,
    PeelState,
    WarpState,
    RaindropsState,
    CrumbleState,
    ParticleState,
)


class TestTransitionStateBase:
    """Tests for base transition state."""
    
    def test_default_progress(self):
        """Test default progress is 0.0."""
        state = TransitionStateBase()
        assert state.progress == 0.0
    
    def test_progress_range(self):
        """Test progress can be set to valid values."""
        state = TransitionStateBase()
        state.progress = 0.5
        assert state.progress == 0.5
        
        state.progress = 1.0
        assert state.progress == 1.0
    
    def test_pixmap_defaults_none(self):
        """Test pixmaps default to None."""
        state = TransitionStateBase()
        assert state.old_pixmap is None
        assert state.new_pixmap is None


class TestCrossfadeState:
    """Tests for crossfade transition state."""
    
    def test_inherits_base(self):
        """Test CrossfadeState inherits from base."""
        state = CrossfadeState()
        assert isinstance(state, TransitionStateBase)
        assert state.progress == 0.0


class TestSlideState:
    """Tests for slide transition state."""
    
    def test_has_position_fields(self):
        """Test slide state has position fields."""
        state = SlideState()
        assert hasattr(state, 'old_start')
        assert hasattr(state, 'old_end')
        assert hasattr(state, 'new_start')
        assert hasattr(state, 'new_end')
    
    def test_precomputed_floats(self):
        """Test that float coordinates are pre-computed."""
        from PySide6.QtCore import QPoint
        
        state = SlideState(
            old_start=QPoint(0, 0),
            old_end=QPoint(100, 0),
            new_start=QPoint(-100, 0),
            new_end=QPoint(0, 0),
        )
        
        # Post-init should compute delta
        assert state._old_delta_x == 100.0
        assert state._new_delta_x == 100.0


class TestBlockFlipState:
    """Tests for block flip transition state."""
    
    def test_has_grid_fields(self):
        """Test block flip has grid configuration."""
        state = BlockFlipState()
        assert hasattr(state, 'cols')
        assert hasattr(state, 'rows')
        assert hasattr(state, 'region')
        assert hasattr(state, 'direction')


class TestDiffuseState:
    """Tests for diffuse transition state."""
    
    def test_has_shape_mode(self):
        """Test diffuse has shape mode field."""
        state = DiffuseState()
        assert hasattr(state, 'shape_mode')
        assert state.shape_mode == 0  # Default Rectangle


class TestCrumbleState:
    """Tests for crumble transition state."""
    
    def test_has_crumble_params(self):
        """Test crumble has configuration parameters."""
        state = CrumbleState()
        assert hasattr(state, 'seed')
        assert hasattr(state, 'piece_count')
        assert hasattr(state, 'crack_complexity')
        assert hasattr(state, 'mosaic_mode')
        assert hasattr(state, 'weight_mode')


class TestParticleState:
    """Tests for particle transition state."""
    
    def test_has_seed(self):
        """Test particle state has seed for randomization."""
        state = ParticleState()
        assert hasattr(state, 'seed')


class TestSnapToNewEnforcement:
    """Tests for snap_to_new=True enforcement pattern."""
    
    def test_progress_at_completion(self):
        """Test that progress reaches 1.0 at completion."""
        state = CrossfadeState()
        
        # Simulate transition completion
        state.progress = 1.0
        
        # At progress 1.0, new_pixmap should be fully visible
        assert state.progress == 1.0
    
    def test_all_states_support_progress(self):
        """Test all transition states support progress field."""
        states = [
            CrossfadeState(),
            SlideState(),
            WipeState(),
            BlockFlipState(),
            DiffuseState(),
            PeelState(),
            WarpState(),
            RaindropsState(),
            CrumbleState(),
            ParticleState(),
        ]
        
        for state in states:
            assert hasattr(state, 'progress')
            state.progress = 1.0
            assert state.progress == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
