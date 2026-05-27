from src.streamlit_app import StreamlitRunConfig, run_eventhub_stream


def test_streamlit_duration_minutes_converts_to_seconds():
    config = StreamlitRunConfig(duration_minutes=3)

    assert config.duration_seconds == 180


def test_streamlit_defaults_match_eventhub_mvp_fleet():
    config = StreamlitRunConfig(duration_minutes=1)

    assert config.site_count == 3
    assert config.assets_per_site == 2
    assert config.interval_seconds == 5.0


def test_streamlit_estimated_event_count_matches_simulator_cycle_math():
    config = StreamlitRunConfig(duration_minutes=1, interval_seconds=7, site_count=3, assets_per_site=2)

    assert config.estimated_event_count == 54


def test_streamlit_run_uses_eventhub_sink_only(monkeypatch):
    created_sinks = []

    class FakeEventHubSink:
        def __init__(self) -> None:
            self.events = []
            created_sinks.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

        def write(self, event) -> None:
            self.events.append(event)

    monkeypatch.setattr("src.streamlit_app.EventHubSink", FakeEventHubSink)

    emitted = run_eventhub_stream(
        StreamlitRunConfig(duration_minutes=1, interval_seconds=60, site_count=1, assets_per_site=1)
    )

    assert emitted == 1
    assert len(created_sinks) == 1
    assert len(created_sinks[0].events) == 1
