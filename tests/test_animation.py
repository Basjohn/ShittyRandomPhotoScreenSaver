"""Tests for the centralized animation framework."""
import time
import pytest
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from core.animation import (
    AnimationManager, EasingCurve,
    PropertyAnimationConfig,
)


@pytest.fixture
def animation_manager(qt_app):
    """Create an AnimationManager instance for testing."""
    manager = AnimationManager(fps=60)
    yield manager
    manager.cancel_all()
    manager.stop()


@pytest.fixture
def test_widget(qt_app):
    """Create a test widget with opacity effect."""
    widget = QWidget()
    opacity_effect = QGraphicsOpacityEffect()
    widget.setGraphicsEffect(opacity_effect)
    opacity_effect.setOpacity(0.0)
    return widget, opacity_effect


def test_animation_manager_initialization(animation_manager):
    """Test AnimationManager initializes correctly."""
    assert animation_manager is not None
    assert animation_manager.fps == 60
    assert animation_manager.get_active_count() == 0


def test_property_animation(animation_manager, test_widget):
    """Test basic property animation."""
    widget, opacity_effect = test_widget
    
    # Track completion
    completed = []
    
    def on_complete():
        completed.append(True)
    
    # Animate opacity from 0.0 to 1.0
    anim_id = animation_manager.animate_property(
        target=opacity_effect,
        property_name='opacity',
        start_value=0.0,
        end_value=1.0,
        duration=0.2,  # 200ms
        easing=EasingCurve.LINEAR,
        on_complete=on_complete
    )
    
    assert anim_id is not None
    assert animation_manager.is_running(anim_id)
    assert animation_manager.get_active_count() == 1
    
    # Wait for animation to complete
    time.sleep(0.3)
    
    # Process events to ensure completion callback fires
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    
    # Animation should be complete
    assert not animation_manager.is_running(anim_id)
    assert opacity_effect.opacity() > 0.8  # Should be close to 1.0


def test_custom_animation(animation_manager, qt_app):
    """Test custom animation with update callback."""
    progress_values = []
    completed = []
    
    def update_callback(progress):
        progress_values.append(progress)
    
    def on_complete():
        completed.append(True)
    
    anim_id = animation_manager.animate_custom(
        duration=0.1,
        update_callback=update_callback,
        easing=EasingCurve.LINEAR,
        on_complete=on_complete
    )
    
    assert animation_manager.is_running(anim_id)
    
    # Process events and wait for animation
    from PySide6.QtCore import QCoreApplication
    for _ in range(20):  # Process events multiple times
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Should have received multiple progress updates
    assert len(progress_values) > 0
    # Progress should go from 0 to 1
    assert progress_values[0] >= 0.0
    assert max(progress_values) >= 0.9


def test_animation_pause_resume(animation_manager, test_widget):
    """Test pausing and resuming animations."""
    widget, opacity_effect = test_widget
    from PySide6.QtCore import QCoreApplication
    
    anim_id = animation_manager.animate_property(
        target=opacity_effect,
        property_name='opacity',
        start_value=0.0,
        end_value=1.0,
        duration=0.5,
        easing=EasingCurve.LINEAR
    )
    
    # Let it run a bit
    for _ in range(10):
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Pause
    assert animation_manager.pause_animation(anim_id)
    progress_at_pause = animation_manager.get_progress(anim_id)
    
    # Wait while paused
    for _ in range(10):
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Progress should not have advanced much
    progress_after_pause = animation_manager.get_progress(anim_id)
    assert abs(progress_at_pause - progress_after_pause) < 0.15  # Should be similar
    
    # Resume
    assert animation_manager.resume_animation(anim_id)
    for _ in range(10):
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Progress should have advanced
    progress_after_resume = animation_manager.get_progress(anim_id)
    assert progress_after_resume > progress_at_pause


def test_animation_cancel(animation_manager, test_widget):
    """Test canceling animations."""
    widget, opacity_effect = test_widget
    
    cancelled = []
    
    def on_cancel():
        cancelled.append(True)
    
    config = PropertyAnimationConfig(
        duration=1.0,
        easing=EasingCurve.LINEAR,
        on_cancel=on_cancel,
        target=opacity_effect,
        property_name='opacity',
        start_value=0.0,
        end_value=1.0
    )
    
    from core.animation.animator import PropertyAnimator
    import uuid
    anim_id = str(uuid.uuid4())
    animator = PropertyAnimator(anim_id, config)
    animation_manager._add_animation(anim_id, animator)
    animator.start()
    
    # Cancel
    assert animation_manager.cancel_animation(anim_id)
    assert not animation_manager.is_running(anim_id)
    
    # Process events
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    
    # Callback should have fired
    assert len(cancelled) == 1


def test_easing_curves(animation_manager):
    """Test different easing curves."""
    from core.animation.easing import (
        linear, quad_in, quad_out, sine_in, sine_out,
        elastic_out, bounce_out, back_out
    )
    
    # Test linear
    assert linear(0.0) == 0.0
    assert linear(0.5) == 0.5
    assert linear(1.0) == 1.0
    
    # Test quad_in (accelerating)
    assert quad_in(0.0) == 0.0
    assert quad_in(0.5) < 0.5  # Slower at start
    assert quad_in(1.0) == 1.0
    
    # Test quad_out (decelerating)
    assert quad_out(0.0) == 0.0
    assert quad_out(0.5) > 0.5  # Faster at start
    assert quad_out(1.0) == 1.0
    
    # Test sine curves
    assert 0.0 <= sine_in(0.5) <= 1.0
    assert 0.0 <= sine_out(0.5) <= 1.0
    
    # Test special curves (elastic, bounce, back)
    # These can overshoot but should end at 1.0
    assert abs(elastic_out(1.0) - 1.0) < 0.01
    assert abs(bounce_out(1.0) - 1.0) < 0.01
    assert abs(back_out(1.0) - 1.0) < 0.01


def test_animation_with_delay(animation_manager, qt_app):
    """Test animation with delay."""
    started = []
    progress_values = []
    from PySide6.QtCore import QCoreApplication
    
    def on_start():
        started.append(time.time())
    
    def update_callback(progress):
        progress_values.append(progress)
    
    animation_manager.animate_custom(
        duration=0.1,
        update_callback=update_callback,
        on_start=on_start,
        delay=0.1  # 100ms delay
    )
    
    # Animation should be running but in delay period
    for _ in range(5):
        QCoreApplication.processEvents()
        time.sleep(0.01)  # 50ms total - still in delay
    
    # Wait past delay and into animation
    for _ in range(20):
        QCoreApplication.processEvents()
        time.sleep(0.01)  # Total 250ms - past delay and animation
    
    # Should have progress now
    assert len(progress_values) > 0


def test_multiple_animations(animation_manager, test_widget):
    """Test running multiple animations simultaneously."""
    widget, opacity_effect = test_widget
    from PySide6.QtCore import QCoreApplication
    
    # Create second widget
    widget2 = QWidget()
    opacity2 = QGraphicsOpacityEffect()
    widget2.setGraphicsEffect(opacity2)
    opacity2.setOpacity(0.0)
    
    # Start two animations
    anim1 = animation_manager.animate_property(
        target=opacity_effect,
        property_name='opacity',
        start_value=0.0,
        end_value=1.0,
        duration=0.2,
        easing=EasingCurve.LINEAR
    )
    
    anim2 = animation_manager.animate_property(
        target=opacity2,
        property_name='opacity',
        start_value=1.0,
        end_value=0.0,
        duration=0.2,
        easing=EasingCurve.LINEAR
    )
    
    assert animation_manager.get_active_count() == 2
    assert animation_manager.is_running(anim1)
    assert animation_manager.is_running(anim2)
    
    # Wait for completion with event processing
    for _ in range(40):
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Both should be complete
    assert animation_manager.get_active_count() == 0


def test_cancel_all_animations(animation_manager, test_widget):
    """Test canceling all animations at once."""
    widget, opacity_effect = test_widget
    
    # Start multiple animations
    for i in range(5):
        animation_manager.animate_property(
            target=opacity_effect,
            property_name='opacity',
            start_value=0.0,
            end_value=1.0,
            duration=1.0,
            easing=EasingCurve.LINEAR
        )
    
    assert animation_manager.get_active_count() == 5
    
    # Cancel all
    animation_manager.cancel_all()
    
    assert animation_manager.get_active_count() == 0


def test_animation_manager_auto_stop(animation_manager, test_widget):
    """Test that manager stops when no animations are active."""
    widget, opacity_effect = test_widget
    from PySide6.QtCore import QCoreApplication
    
    # Start animation
    anim_id = animation_manager.animate_property(
        target=opacity_effect,
        property_name='opacity',
        start_value=0.0,
        end_value=1.0,
        duration=0.1,
        easing=EasingCurve.LINEAR
    )
    
    # Timer should be running and the animation marked as running
    assert animation_manager._timer.isActive()
    assert animation_manager.is_running(anim_id)
    
    # Wait for completion with event processing
    for _ in range(20):
        QCoreApplication.processEvents()
        time.sleep(0.01)
    
    # Should eventually stop
    assert animation_manager.get_active_count() == 0


def test_animation_manager_emits_perf_metrics(qt_app, caplog):
    from core.animation.animator import AnimationManager

    am = AnimationManager(fps=60)

    am._profile_start_ts = 0.0  # type: ignore[attr-defined]
    am._profile_last_ts = 1.0  # type: ignore[attr-defined]
    am._profile_frame_count = 60  # type: ignore[attr-defined]
    am._profile_min_dt = 1.0 / 120.0  # type: ignore[attr-defined]
    am._profile_max_dt = 1.0 / 20.0  # type: ignore[attr-defined]

    with caplog.at_level("INFO"):
        am._log_profile_summary()  # type: ignore[attr-defined]

    messages = [r.message for r in caplog.records]
    assert any("[PERF] [ANIM] AnimationManager metrics" in m for m in messages)


def test_animation_manager_set_target_fps_updates_timer_interval(qt_app):
    """Changing target FPS should update the underlying timer interval."""
    am = AnimationManager(fps=60)
    try:
        assert am.fps == 60
        before_interval = am._timer.interval()
        assert before_interval in (16, 17)

        am.set_target_fps(120)
        assert am.fps == 120
        after_interval = am._timer.interval()
        assert after_interval in (8, 9)

        anim_id = am.animate_custom(
            duration=0.05,
            easing=EasingCurve.LINEAR,
            update_callback=lambda progress: progress,
        )

        start = time.time()
        from PySide6.QtCore import QCoreApplication

        while am.get_active_count() > 0 and (time.time() - start) < 1.0:
            QCoreApplication.processEvents()
            time.sleep(0.005)

        assert am.get_active_count() == 0
        assert not am.is_running(anim_id)
    finally:
        am.cleanup()
