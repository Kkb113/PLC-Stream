from __future__ import annotations

import math
from typing import Any

from .models import NUMERIC_FIELDS, REQUIRED_FIELDS


def validate_event_schema(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in event]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    for field in NUMERIC_FIELDS:
        if field not in event:
            continue
        value = event[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{field} must be numeric")
            continue
        if not math.isfinite(float(value)):
            errors.append(f"{field} must be finite")

    errors.extend(_validate_numeric_bounds(event))
    errors.extend(_validate_gas_composition(event))
    return errors


def validate_event(event: dict[str, Any]) -> None:
    errors = validate_event_schema(event)
    if errors:
        raise ValueError("; ".join(errors))


def infer_threshold_severity(event: dict[str, Any], threshold_rules: dict[str, Any]) -> str:
    plc_status = str(event.get("plc_status", "Online"))
    if plc_status == "Offline":
        return "Critical"

    for field, rules in threshold_rules.items():
        value = _to_float(event.get(field))
        if value is not None and _crosses(value, rules.get("critical", {})):
            return "Critical"

    if plc_status == "Stale":
        return "Warning"

    for field, rules in threshold_rules.items():
        value = _to_float(event.get(field))
        if value is not None and _crosses(value, rules.get("warning", {})):
            return "Warning"

    return "Normal"


def is_within_normal_ranges(event: dict[str, Any], threshold_rules: dict[str, Any]) -> bool:
    for field, rules in threshold_rules.items():
        value = _to_float(event.get(field))
        if value is None:
            return False
        normal = rules.get("normal", {})
        min_value = normal.get("min")
        max_value = normal.get("max")
        if min_value is not None and value < float(min_value):
            return False
        if max_value is not None and value > float(max_value):
            return False
    return str(event.get("plc_status")) == "Online"


def _crosses(value: float, limits: dict[str, Any]) -> bool:
    below = limits.get("below")
    above = limits.get("above")
    if below is not None and value < float(below):
        return True
    if above is not None and value > float(above):
        return True
    return False


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validate_numeric_bounds(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    percent_fields = ("ch4_pct", "co2_pct", "o2_pct", "balance_gas_pct")
    for field in percent_fields:
        value = event.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < 0 or value > 100:
                errors.append(f"{field} must be between 0 and 100")

    non_negative_fields = ("h2s_ppm", "static_pressure_kpa", "gas_flow_nm3_h")
    for field in non_negative_fields:
        value = event.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < 0:
                errors.append(f"{field} must be non-negative")

    temp = event.get("temperature_c")
    if isinstance(temp, (int, float)) and not isinstance(temp, bool):
        if temp < -50 or temp > 120:
            errors.append("temperature_c must be between -50 and 120")

    return errors


def _validate_gas_composition(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ch4 = _to_float(event.get("ch4_pct"))
    co2 = _to_float(event.get("co2_pct"))
    o2 = _to_float(event.get("o2_pct"))
    balance = _to_float(event.get("balance_gas_pct"))

    if ch4 is None or co2 is None or o2 is None or balance is None:
        return errors

    measured_total = ch4 + co2 + o2
    if measured_total > 100.5:
        errors.append("ch4_pct + co2_pct + o2_pct must be less than or equal to 100.5")
    if balance < 0:
        errors.append("balance_gas_pct must be non-negative")

    expected_balance = 100.0 - measured_total
    if abs(balance - expected_balance) > 0.6:
        errors.append("balance_gas_pct must match 100 - (ch4_pct + co2_pct + o2_pct) within rounding tolerance")

    return errors
