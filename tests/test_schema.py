from src.generator import TelemetryGenerator, load_assets
from src.models import REQUIRED_FIELDS
from src.validators import validate_event_schema

ROUTING_FIELDS = ["industry_type", "region", "site_type"]


def test_generated_event_has_required_schema_fields():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    event = TelemetryGenerator(seed=1).generate_event(asset, forced_severity="Normal").to_dict()

    assert list(event.keys()) == REQUIRED_FIELDS
    assert validate_event_schema(event) == []


def test_generated_event_has_routing_fields():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    event = TelemetryGenerator(seed=1).generate_event(asset, forced_severity="Normal").to_dict()

    for field in ROUTING_FIELDS:
        assert field in event
        assert event[field]


def test_site_routing_mapping_is_correct():
    assets = load_assets(site_count=3, assets_per_site=1)
    generator = TelemetryGenerator(seed=1)

    expected = {
        "SITE-001": ("Biogas", "North", "Biogas Facility"),
        "SITE-002": ("Wastewater", "West", "Wastewater Treatment Plant"),
        "SITE-003": ("LandfillGas", "South", "Landfill Gas Field"),
    }

    for asset in assets:
        event = generator.generate_event(asset, forced_severity="Normal").to_dict()
        industry_type, region, site_type = expected[event["site_id"]]
        assert event["industry_type"] == industry_type
        assert event["region"] == region
        assert event["site_type"] == site_type


def test_numeric_validation_rejects_invalid_values():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    event = TelemetryGenerator(seed=1).generate_event(asset, forced_severity="Normal").to_dict()
    event["o2_pct"] = "bad"

    errors = validate_event_schema(event)

    assert any("o2_pct must be numeric" in error for error in errors)
