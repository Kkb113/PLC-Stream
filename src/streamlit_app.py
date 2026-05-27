from __future__ import annotations

import math
from dataclasses import dataclass

import streamlit as st

from .generator import TelemetryGenerator, load_assets
from .plc_simulator import PLCSimulator
from .sinks import EventHubSink


DEFAULT_INTERVAL_SECONDS = 5.0
DEFAULT_SITE_COUNT = 3
DEFAULT_ASSETS_PER_SITE = 2


@dataclass(frozen=True)
class StreamlitRunConfig:
    duration_minutes: int
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    site_count: int = DEFAULT_SITE_COUNT
    assets_per_site: int = DEFAULT_ASSETS_PER_SITE

    @property
    def duration_seconds(self) -> int:
        return self.duration_minutes * 60

    @property
    def estimated_event_count(self) -> int:
        cycles = max(1, math.ceil(self.duration_seconds / self.interval_seconds))
        return cycles * self.site_count * self.assets_per_site


def run_eventhub_stream(config: StreamlitRunConfig) -> int:
    assets = load_assets(site_count=config.site_count, assets_per_site=config.assets_per_site)
    generator = TelemetryGenerator(format_type="JSON")

    with EventHubSink() as sink:
        simulator = PLCSimulator(
            assets=assets,
            generator=generator,
            sink=sink,
            interval_seconds=config.interval_seconds,
            duration_seconds=config.duration_seconds,
            realtime=False,
        )
        return simulator.run()


def main() -> None:
    st.set_page_config(
        page_title="PLC Telemetry Stream",
        page_icon="",
        layout="centered",
    )

    st.title("PLC Telemetry Stream")
    st.caption("Destination: Azure Event Hub")

    duration_minutes = st.number_input(
        "Duration in minutes",
        min_value=1,
        max_value=240,
        value=1,
        step=1,
        help="The simulator sends the selected duration as a fast batch to Azure Event Hub.",
    )

    interval_seconds = st.number_input(
        "PLC interval in seconds",
        min_value=1.0,
        max_value=60.0,
        value=DEFAULT_INTERVAL_SECONDS,
        step=1.0,
    )

    preview_config = StreamlitRunConfig(
        duration_minutes=int(duration_minutes),
        interval_seconds=float(interval_seconds),
        site_count=DEFAULT_SITE_COUNT,
        assets_per_site=DEFAULT_ASSETS_PER_SITE,
    )

    st.metric("Estimated events", preview_config.estimated_event_count)
    st.info("Only Azure Event Hub is supported from this Streamlit app.")

    if st.button("Send to Event Hub", type="primary"):
        config = StreamlitRunConfig(
            duration_minutes=int(duration_minutes),
            interval_seconds=float(interval_seconds),
            site_count=DEFAULT_SITE_COUNT,
            assets_per_site=DEFAULT_ASSETS_PER_SITE,
        )

        with st.spinner("Sending telemetry to Azure Event Hub..."):
            try:
                emitted = run_eventhub_stream(config)
            except RuntimeError as exc:
                st.error(str(exc))
                return

        st.success(f"Sent {emitted} JSON telemetry events to Azure Event Hub.")


if __name__ == "__main__":
    main()
