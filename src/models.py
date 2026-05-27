from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


FIELD_ORDER = [
    "event_id",
    "event_time",
    "site_id",
    "site_name",
    "industry_type",
    "region",
    "site_type",
    "asset_id",
    "asset_type",
    "plc_id",
    "sensor_package_id",
    "waste_stream",
    "process_area",
    "ch4_pct",
    "co2_pct",
    "o2_pct",
    "balance_gas_pct",
    "h2s_ppm",
    "temperature_c",
    "static_pressure_kpa",
    "gas_flow_nm3_h",
    "plc_status",
    "format_type",
    "simulated_scenario",
    "expected_severity",
]

NUMERIC_FIELDS = [
    "ch4_pct",
    "co2_pct",
    "o2_pct",
    "balance_gas_pct",
    "h2s_ppm",
    "temperature_c",
    "static_pressure_kpa",
    "gas_flow_nm3_h",
]

REQUIRED_FIELDS = FIELD_ORDER.copy()


@dataclass(frozen=True)
class AssetConfig:
    site_id: str
    site_name: str
    industry_type: str
    region: str
    site_type: str
    asset_id: str
    asset_type: str
    plc_id: str
    sensor_package_id: str
    waste_stream: str
    process_area: str

    @classmethod
    def from_site_asset(cls, site: dict[str, Any], asset: dict[str, Any]) -> "AssetConfig":
        return cls(
            site_id=str(site["site_id"]),
            site_name=str(site["site_name"]),
            industry_type=str(site["industry_type"]),
            region=str(site["region"]),
            site_type=str(site["site_type"]),
            asset_id=str(asset["asset_id"]),
            asset_type=str(asset["asset_type"]),
            plc_id=str(asset["plc_id"]),
            sensor_package_id=str(asset["sensor_package_id"]),
            waste_stream=str(asset["waste_stream"]),
            process_area=str(asset["process_area"]),
        )


@dataclass(frozen=True)
class TelemetryEvent:
    event_id: str
    event_time: str
    site_id: str
    site_name: str
    industry_type: str
    region: str
    site_type: str
    asset_id: str
    asset_type: str
    plc_id: str
    sensor_package_id: str
    waste_stream: str
    process_area: str
    ch4_pct: float
    co2_pct: float
    o2_pct: float
    balance_gas_pct: float
    h2s_ppm: int
    temperature_c: float
    static_pressure_kpa: float
    gas_flow_nm3_h: float
    plc_status: str
    format_type: str
    simulated_scenario: str
    expected_severity: str

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return {field: raw[field] for field in FIELD_ORDER}
