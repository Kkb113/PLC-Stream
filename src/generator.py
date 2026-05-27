from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AssetConfig, TelemetryEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITES_PATH = PROJECT_ROOT / "config" / "sites.json"
DEFAULT_THRESHOLDS_PATH = PROJECT_ROOT / "config" / "threshold_rules.json"

SITE_ROUTING = {
    "SITE-001": {
        "industry_type": "Biogas",
        "region": "North",
        "site_type": "Biogas Facility",
    },
    "SITE-002": {
        "industry_type": "Wastewater",
        "region": "West",
        "site_type": "Wastewater Treatment Plant",
    },
    "SITE-003": {
        "industry_type": "LandfillGas",
        "region": "South",
        "site_type": "Landfill Gas Field",
    },
}

WARNING_SCENARIOS = [
    "O2_INGRESS_WARNING",
    "H2S_HIGH_WARNING",
    "METHANE_QUALITY_DROP_WARNING",
    "PRESSURE_FLOW_BLOCKAGE_WARNING",
    "TEMPERATURE_DRIFT_WARNING",
    "PLC_STALE_WARNING",
]

CRITICAL_SCENARIOS = [
    "O2_INGRESS_AND_H2S_SPIKE",
    "H2S_CRITICAL_SPIKE",
    "METHANE_CRITICAL_DROP",
    "PRESSURE_FLOW_BLOCKAGE_CRITICAL",
    "TEMPERATURE_CRITICAL",
    "PLC_OFFLINE_CRITICAL",
]


class WeightedScenarioChooser:
    """Provides a stable 89/9/2 normal-warning-critical mix per 100 events."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._bucket: list[str] = []

    def next_severity(self) -> str:
        if not self._bucket:
            self._bucket = ["Normal"] * 89 + ["Warning"] * 9 + ["Critical"] * 2
            self._rng.shuffle(self._bucket)
        return self._bucket.pop()


class TelemetryGenerator:
    def __init__(
        self,
        format_type: str = "JSON",
        seed: int | None = None,
        start_event_number: int = 1,
    ) -> None:
        self.format_type = format_type.upper()
        self.rng = random.Random(seed)
        self.event_number = start_event_number
        self.scenario_chooser = WeightedScenarioChooser(self.rng)

    def generate_event(
        self,
        asset: AssetConfig,
        event_time: datetime | None = None,
        forced_severity: str | None = None,
        forced_scenario: str | None = None,
    ) -> TelemetryEvent:
        severity = forced_severity or self.scenario_chooser.next_severity()
        scenario = forced_scenario or self._choose_scenario(severity)
        values = self._normal_values()

        if severity == "Warning":
            self._apply_warning_scenario(values, scenario)
        elif severity == "Critical":
            self._apply_critical_scenario(values, scenario)

        composition = _rounded_composition(
            values["ch4_pct"],
            values["co2_pct"],
            values["o2_pct"],
        )

        event = TelemetryEvent(
            event_id=f"EVT-{self.event_number:06d}",
            event_time=_format_timestamp(event_time or datetime.now(timezone.utc)),
            site_id=asset.site_id,
            site_name=asset.site_name,
            industry_type=asset.industry_type,
            region=asset.region,
            site_type=asset.site_type,
            asset_id=asset.asset_id,
            asset_type=asset.asset_type,
            plc_id=asset.plc_id,
            sensor_package_id=asset.sensor_package_id,
            waste_stream=asset.waste_stream,
            process_area=asset.process_area,
            ch4_pct=composition["ch4_pct"],
            co2_pct=composition["co2_pct"],
            o2_pct=composition["o2_pct"],
            balance_gas_pct=composition["balance_gas_pct"],
            h2s_ppm=int(round(values["h2s_ppm"])),
            temperature_c=round(values["temperature_c"], 1),
            static_pressure_kpa=round(values["static_pressure_kpa"], 1),
            gas_flow_nm3_h=round(values["gas_flow_nm3_h"], 1),
            plc_status=values["plc_status"],
            format_type=self.format_type,
            simulated_scenario=scenario,
            expected_severity=severity,
        )
        self.event_number += 1
        return event

    def _choose_scenario(self, severity: str) -> str:
        if severity == "Normal":
            return "Normal"
        if severity == "Warning":
            return self.rng.choice(WARNING_SCENARIOS)
        return self.rng.choice(CRITICAL_SCENARIOS)

    def _normal_values(self) -> dict[str, Any]:
        values = {
            "h2s_ppm": self.rng.uniform(20, 280),
            "temperature_c": self.rng.uniform(32, 40),
            "static_pressure_kpa": self.rng.uniform(5, 20),
            "gas_flow_nm3_h": self.rng.uniform(40, 120),
            "plc_status": "Online",
        }
        self._set_composition(
            values,
            ch4_range=(50.0, 70.0),
            co2_range=(25.0, 45.0),
            o2_range=(0.1, 1.8),
            balance_range=(0.8, 14.0),
        )
        return values

    def _apply_warning_scenario(self, values: dict[str, Any], scenario: str) -> None:
        if scenario == "O2_INGRESS_WARNING":
            self._set_composition(
                values,
                ch4_range=(45.1, 58.0),
                co2_range=(30.0, 48.0),
                o2_range=(2.1, 4.9),
                balance_range=(1.0, 10.0),
            )
        elif scenario == "H2S_HIGH_WARNING":
            values["h2s_ppm"] = self.rng.uniform(520, 980)
        elif scenario == "METHANE_QUALITY_DROP_WARNING":
            self._set_composition(
                values,
                ch4_range=(40.5, 44.9),
                co2_range=(48.1, 54.9),
                o2_range=(0.1, 1.8),
                balance_range=(1.0, 10.0),
            )
        elif scenario == "PRESSURE_FLOW_BLOCKAGE_WARNING":
            values["static_pressure_kpa"] = self.rng.uniform(25.5, 34.9)
            values["gas_flow_nm3_h"] = self.rng.uniform(10.5, 24.8)
        elif scenario == "TEMPERATURE_DRIFT_WARNING":
            values["temperature_c"] = self._choose_between((26.0, 29.8), (42.2, 47.8))
        elif scenario == "PLC_STALE_WARNING":
            values["plc_status"] = "Stale"

    def _apply_critical_scenario(self, values: dict[str, Any], scenario: str) -> None:
        if scenario == "O2_INGRESS_AND_H2S_SPIKE":
            self._set_composition(
                values,
                ch4_range=(34.0, 39.5),
                co2_range=(55.5, 58.5),
                o2_range=(5.2, 8.5),
                balance_range=(1.0, 5.0),
            )
            values["h2s_ppm"] = self.rng.uniform(1050, 1600)
            values["temperature_c"] = self.rng.uniform(48.5, 54.0)
            values["static_pressure_kpa"] = self.rng.uniform(35.5, 45.0)
            values["gas_flow_nm3_h"] = self.rng.uniform(4.0, 9.5)
        elif scenario == "H2S_CRITICAL_SPIKE":
            values["h2s_ppm"] = self.rng.uniform(1005, 1800)
        elif scenario == "METHANE_CRITICAL_DROP":
            self._set_composition(
                values,
                ch4_range=(32.0, 39.5),
                co2_range=(55.5, 64.0),
                o2_range=(0.1, 1.8),
                balance_range=(2.0, 12.0),
            )
        elif scenario == "PRESSURE_FLOW_BLOCKAGE_CRITICAL":
            values["static_pressure_kpa"] = self.rng.uniform(35.5, 50.0)
            values["gas_flow_nm3_h"] = self.rng.uniform(3.0, 9.8)
        elif scenario == "TEMPERATURE_CRITICAL":
            values["temperature_c"] = self._choose_between((18.0, 24.5), (48.5, 56.0))
        elif scenario == "PLC_OFFLINE_CRITICAL":
            values["plc_status"] = "Offline"

    def _choose_between(self, left: tuple[float, float], right: tuple[float, float]) -> float:
        low, high = left if self.rng.random() < 0.5 else right
        return self.rng.uniform(low, high)

    def _set_composition(
        self,
        values: dict[str, Any],
        ch4_range: tuple[float, float],
        co2_range: tuple[float, float],
        o2_range: tuple[float, float],
        balance_range: tuple[float, float],
    ) -> None:
        for _ in range(200):
            o2_pct = self.rng.uniform(*o2_range)
            balance_gas_pct = self.rng.uniform(*balance_range)
            ch4_plus_co2 = 100.0 - o2_pct - balance_gas_pct
            ch4_min = max(ch4_range[0], ch4_plus_co2 - co2_range[1])
            ch4_max = min(ch4_range[1], ch4_plus_co2 - co2_range[0])

            if ch4_min <= ch4_max:
                ch4_pct = self.rng.uniform(ch4_min, ch4_max)
                values["ch4_pct"] = ch4_pct
                values["co2_pct"] = ch4_plus_co2 - ch4_pct
                values["o2_pct"] = o2_pct
                return

        raise ValueError("Unable to generate a realistic gas composition for configured ranges")


def load_threshold_rules(path: Path | str = DEFAULT_THRESHOLDS_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def load_assets(
    path: Path | str = DEFAULT_SITES_PATH,
    site_count: int = 3,
    assets_per_site: int = 2,
) -> list[AssetConfig]:
    with Path(path).open("r", encoding="utf-8") as file:
        config = json.load(file)

    sites = list(config.get("sites", []))
    selected_assets: list[AssetConfig] = []

    for site_index in range(site_count):
        site = sites[site_index] if site_index < len(sites) else _synthetic_site(site_index + 1)
        site = _with_routing_fields(site)
        configured_assets = list(site.get("assets", []))

        for asset_index in range(assets_per_site):
            asset = (
                configured_assets[asset_index]
                if asset_index < len(configured_assets)
                else _synthetic_asset(site_index + 1, asset_index + 1)
            )
            selected_assets.append(AssetConfig.from_site_asset(site, asset))

    return selected_assets


def _synthetic_site(site_number: int) -> dict[str, Any]:
    return _with_routing_fields({
        "site_id": f"SITE-{site_number:03d}",
        "site_name": f"Ecotecco Demo Site {site_number:03d}",
        "industry_type": "Demo",
        "region": "Demo",
        "site_type": "Demo Site",
        "assets": [],
    })


def _synthetic_asset(site_number: int, asset_number: int) -> dict[str, Any]:
    plc_number = ((site_number - 1) * 10) + asset_number
    return {
        "asset_id": f"ASSET-{site_number:03d}-{asset_number:02d}",
        "asset_type": "Gas Analyzer Unit",
        "plc_id": f"PLC-{plc_number:03d}",
        "sensor_package_id": f"GAS-ANALYZER-{plc_number:03d}",
        "waste_stream": "Mixed Organic Waste",
        "process_area": "Gas Monitoring",
    }


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _with_routing_fields(site: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(site)
    routing = SITE_ROUTING.get(str(enriched.get("site_id")), {})
    for field in ("industry_type", "region", "site_type"):
        enriched[field] = str(enriched.get(field) or routing.get(field) or "Unknown")
    return enriched


def _rounded_composition(ch4_pct: float, co2_pct: float, o2_pct: float) -> dict[str, float]:
    ch4_pct = round(ch4_pct, 1)
    co2_pct = round(co2_pct, 1)
    o2_pct = round(o2_pct, 1)
    balance_gas_pct = round(100.0 - (ch4_pct + co2_pct + o2_pct), 1)

    if balance_gas_pct < 0:
        co2_pct = round(co2_pct + balance_gas_pct, 1)
        balance_gas_pct = round(100.0 - (ch4_pct + co2_pct + o2_pct), 1)

    return {
        "ch4_pct": ch4_pct,
        "co2_pct": co2_pct,
        "o2_pct": o2_pct,
        "balance_gas_pct": max(0.0, balance_gas_pct),
    }
