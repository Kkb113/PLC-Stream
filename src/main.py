from __future__ import annotations

import argparse
from pathlib import Path

from .generator import TelemetryGenerator, load_assets
from .plc_simulator import PLCSimulator
from .sinks import ConsoleSink, EventHubSink, FileSink, ServerSink


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ecotecco PLC stream simulator")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output payload format")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="Seconds between PLC cycles")
    parser.add_argument("--duration-seconds", type=float, default=None, help="Optional simulated duration")
    parser.add_argument(
        "--output",
        choices=["console", "file", "server", "eventhub"],
        default="console",
        help="Where generated events should be sent",
    )
    parser.add_argument("--site-count", type=int, default=3, help="Number of sites to simulate")
    parser.add_argument("--assets-per-site", type=int, default=2, help="Number of assets per site")
    parser.add_argument("--server-url", default=None, help="Server endpoint for POST output")
    parser.add_argument("--file-path", default=None, help="Optional output file path")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for repeatable output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.site_count < 1:
        parser.error("--site-count must be at least 1")
    if args.assets_per_site < 1:
        parser.error("--assets-per-site must be at least 1")
    if args.duration_seconds is not None and args.duration_seconds <= 0:
        parser.error("--duration-seconds must be greater than 0 when provided")
    if args.output == "eventhub" and args.format != "json":
        parser.error("--output eventhub sends JSON events and requires --format json")

    format_type = args.format.upper()
    assets = load_assets(site_count=args.site_count, assets_per_site=args.assets_per_site)
    generator = TelemetryGenerator(format_type=format_type, seed=args.seed)

    try:
        with _build_sink(args.output, format_type, args.server_url, args.file_path) as sink:
            realtime = not (args.output in {"file", "eventhub"} and args.duration_seconds is not None)
            simulator = PLCSimulator(
                assets=assets,
                generator=generator,
                sink=sink,
                interval_seconds=args.interval_seconds,
                duration_seconds=args.duration_seconds,
                realtime=realtime,
            )
            emitted = simulator.run()
    except RuntimeError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    if args.output == "file":
        print(f"Generated {emitted} {format_type} events.")
    elif args.output == "eventhub":
        print(f"Sent {emitted} JSON events to Azure Event Hub.")
    return 0


def _build_sink(output: str, format_type: str, server_url: str | None, file_path: str | None):
    if output == "console":
        return ConsoleSink(format_type)
    if output == "file":
        return FileSink(format_type, Path(file_path) if file_path else None)
    if output == "eventhub":
        return EventHubSink()

    if server_url is None:
        endpoint = "ingest/json" if format_type == "JSON" else "ingest/csv"
        server_url = f"http://localhost:8000/{endpoint}"
    return ServerSink(server_url=server_url, format_type=format_type)


if __name__ == "__main__":
    raise SystemExit(main())
