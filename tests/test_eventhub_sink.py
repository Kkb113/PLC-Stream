import json

import pytest

from src.generator import TelemetryGenerator, load_assets
from src.sinks import EventHubSink


class FakeEventData:
    def __init__(self, body: str) -> None:
        self.body = body


class FakeBatch:
    def __init__(self) -> None:
        self.events = []

    def add(self, event_data: FakeEventData) -> None:
        self.events.append(event_data)


class FakeProducer:
    def __init__(self) -> None:
        self.sent_batches = []
        self.closed = False

    def create_batch(self) -> FakeBatch:
        return FakeBatch()

    def send_batch(self, batch: FakeBatch) -> None:
        self.sent_batches.append(batch)

    def close(self) -> None:
        self.closed = True


def test_eventhub_sink_serializes_and_sends_json_event():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    event = TelemetryGenerator(seed=123).generate_event(asset, forced_severity="Normal")
    fake_producer = FakeProducer()
    captured_kwargs = {}

    def fake_factory(**kwargs):
        captured_kwargs.update(kwargs)
        return fake_producer

    sink = EventHubSink(
        env={
            "AZURE_EVENTHUB_CONNECTION_STRING": "Endpoint=sb://example.servicebus.windows.net/;SharedAccessKeyName=send;SharedAccessKey=secret",
            "AZURE_EVENTHUB_NAME": "ehub-ecotecco-plc-telemetry",
        },
        producer_factory=fake_factory,
        event_data_cls=FakeEventData,
        load_env_file=False,
    )

    sink.write(event)
    sink.close()

    sent_body = fake_producer.sent_batches[0].events[0].body
    payload = json.loads(sent_body)

    assert payload["event_id"] == event.event_id
    assert payload["format_type"] == "JSON"
    assert payload["industry_type"] == "Biogas"
    assert payload["region"] == "North"
    assert payload["site_type"] == "Biogas Facility"
    assert captured_kwargs["eventhub_name"] == "ehub-ecotecco-plc-telemetry"
    assert fake_producer.closed is True


def test_eventhub_sink_missing_environment_variables_gives_clear_error():
    with pytest.raises(RuntimeError) as error:
        EventHubSink(env={}, load_env_file=False)

    message = str(error.value)
    assert "AZURE_EVENTHUB_CONNECTION_STRING" in message
    assert "AZURE_EVENTHUB_NAME" in message
    assert ".env" in message


def test_eventhub_sink_rejects_incomplete_connection_string():
    with pytest.raises(RuntimeError) as error:
        EventHubSink(
            env={
                "AZURE_EVENTHUB_CONNECTION_STRING": "SharedAccessKeyName=send;SharedAccessKey=secret",
                "AZURE_EVENTHUB_NAME": "ehub-ecotecco-plc-telemetry",
            },
            producer_factory=lambda **kwargs: FakeProducer(),
            event_data_cls=FakeEventData,
            load_env_file=False,
        )

    assert "full Azure Event Hub connection string" in str(error.value)
    assert "Endpoint=sb://" in str(error.value)
