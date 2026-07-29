from rendering.fade_coordinator import FadeCoordinator, FadeState


def test_fade_coordinator_starts_late_ready_request_immediately_after_compositor_ready():
    coord = FadeCoordinator(screen_index=1)
    coord.register_participant("clock")
    coord.register_participant("weather")

    started = []
    coord.request_fade("clock", lambda: started.append("clock"))

    assert started == []

    coord.signal_compositor_ready()

    assert started == ["clock"]
    assert coord.get_state() == FadeState.FADING

    coord.request_fade("weather", lambda: started.append("weather"))

    assert started == ["clock", "weather"]
    assert coord.get_state() == FadeState.FADING

    generation = coord.get_generation()
    coord.mark_fade_complete("clock", generation=generation)
    assert coord.get_state() == FadeState.FADING
    coord.mark_fade_complete("weather", generation=generation)
    assert coord.get_state() == FadeState.COMPLETE


def test_fade_coordinator_queues_until_compositor_ready():
    coord = FadeCoordinator(screen_index=0)
    coord.register_participant("media")

    started = []
    ready = coord.request_fade("media", lambda: started.append("media"))

    assert ready is False
    assert started == []
    assert coord.describe()["pending"] == ["media"]

    coord.signal_compositor_ready()

    assert started == ["media"]
    assert coord.describe()["pending"] == []


def test_compositor_ready_waits_for_final_startup_hold():
    coord = FadeCoordinator(screen_index=0)
    coord.register_participant("media")
    coord.add_startup_hold("critical_gl_startup")
    coord.add_startup_hold("other")

    started = []
    coord.request_fade("media", lambda: started.append("media"))
    coord.signal_compositor_ready()

    assert started == []
    assert coord.describe()["startup_holds"] == ["critical_gl_startup", "other"]

    coord.release_startup_hold("other")
    assert started == []

    coord.release_startup_hold("critical_gl_startup")
    assert started == ["media"]


def test_completion_callback_waits_for_real_animation_completion():
    coord = FadeCoordinator(screen_index=0)
    coord.register_participant("media")
    completed = []
    coord.add_completion_callback(lambda: completed.append("done"))

    coord.request_fade("media", lambda: None)
    coord.signal_compositor_ready()

    assert completed == []
    coord.mark_fade_complete("media", generation=coord.get_generation())
    assert completed == ["done"]


def test_unavailable_registered_participant_does_not_strand_completion():
    coord = FadeCoordinator(screen_index=0)
    coord.register_participant("clock")
    coord.register_participant("media")
    completed = []
    coord.add_completion_callback(lambda: completed.append("done"))

    coord.request_fade("clock", lambda: None)
    coord.signal_compositor_ready()
    coord.mark_fade_complete("clock", generation=coord.get_generation())

    assert coord.get_state() == FadeState.COMPLETE
    assert completed == ["done"]
    assert "media" not in coord.describe()["completed"]
