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
