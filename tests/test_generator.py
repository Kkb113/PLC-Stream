import csv
import json

from src.generator import TelemetryGenerator, load_assets, load_threshold_rules
from src.sinks import FileSink
from src.validators import is_within_normal_ranges


def test_normal_rows_stay_within_normal_ranges():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    rules = load_threshold_rules()
    generator = TelemetryGenerator(seed=10)

    normal_events = [
        generator.generate_event(asset, forced_severity="Normal").to_dict()
        for _ in range(100)
    ]

    assert all(is_within_normal_ranges(event, rules) for event in normal_events)


def test_warning_and_critical_rows_are_generated_with_expected_ratio():
    assets = load_assets(site_count=3, assets_per_site=2)
    generator = TelemetryGenerator(seed=42)
    counts = {"Normal": 0, "Warning": 0, "Critical": 0}

    for index in range(1000):
        event = generator.generate_event(assets[index % len(assets)]).to_dict()
        counts[event["expected_severity"]] += 1

    assert counts["Warning"] > 0
    assert counts["Critical"] > 0
    assert 0.85 <= counts["Normal"] / 1000 <= 0.90
    assert 0.08 <= counts["Warning"] / 1000 <= 0.10
    assert 0.01 <= counts["Critical"] / 1000 <= 0.03


def test_gas_composition_is_realistic_for_all_generated_rows():
    assets = load_assets(site_count=3, assets_per_site=2)
    generator = TelemetryGenerator(seed=99)

    for index in range(1000):
        event = generator.generate_event(assets[index % len(assets)]).to_dict()
        measured_total = event["ch4_pct"] + event["co2_pct"] + event["o2_pct"]

        assert measured_total <= 100.5
        assert event["balance_gas_pct"] >= 0
        assert abs(event["balance_gas_pct"] - (100 - measured_total)) <= 0.6


def test_h2s_ppm_is_always_populated_as_an_integer():
    assets = load_assets(site_count=3, assets_per_site=2)
    generator = TelemetryGenerator(seed=21)

    for index in range(500):
        event = generator.generate_event(assets[index % len(assets)]).to_dict()

        assert event["h2s_ppm"] != ""
        assert event["h2s_ppm"] is not None
        assert isinstance(event["h2s_ppm"], int)


def test_json_and_csv_file_outputs_work(tmp_path):
    asset = load_assets(site_count=1, assets_per_site=1)[0]

    json_path = tmp_path / "events.jsonl"
    json_generator = TelemetryGenerator(format_type="JSON", seed=2)
    with FileSink("JSON", json_path) as sink:
        for _ in range(3):
            sink.write(json_generator.generate_event(asset, forced_severity="Normal"))

    json_lines = json_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(json_lines) == 3
    first_json_event = json.loads(json_lines[0])
    assert first_json_event["format_type"] == "JSON"
    assert first_json_event["industry_type"] == "Biogas"
    assert first_json_event["region"] == "North"
    assert first_json_event["site_type"] == "Biogas Facility"

    csv_path = tmp_path / "events.csv"
    csv_generator = TelemetryGenerator(format_type="CSV", seed=2)
    with FileSink("CSV", csv_path) as sink:
        for _ in range(3):
            sink.write(csv_generator.generate_event(asset, forced_severity="Normal"))

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 3
    assert rows[0]["format_type"] == "CSV"
    assert "industry_type" in rows[0]
    assert "region" in rows[0]
    assert "site_type" in rows[0]
    assert rows[0]["industry_type"] == "Biogas"
    assert rows[0]["region"] == "North"
    assert rows[0]["site_type"] == "Biogas Facility"
