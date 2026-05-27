from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from .models import FIELD_ORDER, TelemetryEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_JSONL_PATH = DATA_DIR / "generated_stream.jsonl"
DEFAULT_CSV_PATH = DATA_DIR / "generated_stream.csv"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


class BaseSink:
    def write(self, event: TelemetryEvent) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "BaseSink":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class ConsoleSink(BaseSink):
    def __init__(self, format_type: str) -> None:
        self.format_type = format_type.upper()
        self._csv_writer: csv.DictWriter[str] | None = None

    def write(self, event: TelemetryEvent) -> None:
        payload = event.to_dict()
        if self.format_type == "JSON":
            print(json.dumps(payload), flush=True)
            return

        if self._csv_writer is None:
            self._csv_writer = csv.DictWriter(sys.stdout, fieldnames=FIELD_ORDER, lineterminator="\n")
            self._csv_writer.writeheader()
        self._csv_writer.writerow(payload)
        sys.stdout.flush()


class FileSink(BaseSink):
    def __init__(self, format_type: str, file_path: Path | str | None = None) -> None:
        self.format_type = format_type.upper()
        default_path = DEFAULT_JSONL_PATH if self.format_type == "JSON" else DEFAULT_CSV_PATH
        self.file_path = Path(file_path or default_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO = self.file_path.open("w", encoding="utf-8", newline="")
        self._csv_writer: csv.DictWriter[str] | None = None

        if self.format_type == "CSV":
            self._csv_writer = csv.DictWriter(self._file, fieldnames=FIELD_ORDER, lineterminator="\n")
            self._csv_writer.writeheader()

    def write(self, event: TelemetryEvent) -> None:
        payload = event.to_dict()
        if self.format_type == "JSON":
            self._file.write(json.dumps(payload) + "\n")
        else:
            assert self._csv_writer is not None
            self._csv_writer.writerow(payload)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class ServerSink(BaseSink):
    def __init__(self, server_url: str, format_type: str = "JSON", timeout_seconds: float = 5.0) -> None:
        self.server_url = server_url
        self.format_type = format_type.upper()
        self.timeout_seconds = timeout_seconds

    def write(self, event: TelemetryEvent) -> None:
        payload = event.to_dict()
        if self.format_type == "JSON":
            body = json.dumps(payload).encode("utf-8")
            content_type = "application/json"
        else:
            body = event_to_csv_text(payload).encode("utf-8")
            content_type = "text/csv"

        request = urllib.request.Request(
            self.server_url,
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Unable to post event {event.event_id} to {self.server_url}: {exc}") from exc


class EventHubSink(BaseSink):
    def __init__(
        self,
        connection_string: str | None = None,
        eventhub_name: str | None = None,
        env: Mapping[str, str] | None = None,
        producer_factory: Callable[..., Any] | None = None,
        event_data_cls: Callable[[str], Any] | None = None,
        load_env_file: bool = True,
    ) -> None:
        if load_env_file:
            _load_dotenv_file()

        env_source = env if env is not None else os.environ
        self.connection_string = _clean_env_value(
            connection_string or env_source.get("AZURE_EVENTHUB_CONNECTION_STRING")
        )
        self.eventhub_name = _clean_env_value(eventhub_name or env_source.get("AZURE_EVENTHUB_NAME"))

        missing = [
            name
            for name, value in (
                ("AZURE_EVENTHUB_CONNECTION_STRING", self.connection_string),
                ("AZURE_EVENTHUB_NAME", self.eventhub_name),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing Azure Event Hub configuration: "
                + ", ".join(missing)
                + ". Create a .env file from .env.example or set these environment variables."
            )

        _validate_eventhub_connection_string(self.connection_string)

        if producer_factory is None or event_data_cls is None:
            eventhub_producer_client, event_data = _load_eventhub_sdk()
            producer_factory = producer_factory or eventhub_producer_client.from_connection_string
            event_data_cls = event_data_cls or event_data

        self._event_data_cls = event_data_cls
        self._producer = producer_factory(
            conn_str=self.connection_string,
            eventhub_name=self.eventhub_name,
        )

    @staticmethod
    def serialize_event(event: TelemetryEvent) -> str:
        return json.dumps(event.to_dict())

    def write(self, event: TelemetryEvent) -> None:
        payload = self.serialize_event(event)
        try:
            batch = self._producer.create_batch()
            batch.add(self._event_data_cls(payload))
            self._producer.send_batch(batch)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to send event {event.event_id} to Azure Event Hub {self.eventhub_name}: {exc}"
            ) from exc

    def close(self) -> None:
        self._producer.close()


def event_to_csv_text(event: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELD_ORDER, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: event[field] for field in FIELD_ORDER})
    return buffer.getvalue()


def csv_text_to_events(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    events = []
    for row in reader:
        events.append(_coerce_csv_row(row))
    return events


def _coerce_csv_row(row: dict[str, str]) -> dict[str, Any]:
    coerced: dict[str, Any] = dict(row)
    int_fields = {"h2s_ppm"}
    float_fields = {
        "ch4_pct",
        "co2_pct",
        "o2_pct",
        "balance_gas_pct",
        "temperature_c",
        "static_pressure_kpa",
        "gas_flow_nm3_h",
    }

    for field in int_fields:
        if field in coerced and coerced[field] != "":
            coerced[field] = int(float(coerced[field]))
    for field in float_fields:
        if field in coerced and coerced[field] != "":
            coerced[field] = float(coerced[field])
    return coerced


def _load_dotenv_file() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(DEFAULT_ENV_PATH, override=True)


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


def _validate_eventhub_connection_string(connection_string: str | None) -> None:
    if connection_string is None:
        return

    required_parts = ("Endpoint=sb://", "SharedAccessKeyName=", "SharedAccessKey=")
    missing_parts = [part for part in required_parts if part not in connection_string]
    if missing_parts:
        raise RuntimeError(
            "AZURE_EVENTHUB_CONNECTION_STRING does not look like a full Azure Event Hub "
            "connection string. It should include Endpoint=sb://, SharedAccessKeyName=, "
            "and SharedAccessKey=. Copy the full Send connection string, not only the key "
            "or policy name."
        )


def _load_eventhub_sdk() -> tuple[Any, Any]:
    try:
        from azure.eventhub import EventData, EventHubProducerClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-eventhub is required for --output eventhub. Install dependencies with "
            "pip install -r requirements.txt."
        ) from exc

    return EventHubProducerClient, EventData
