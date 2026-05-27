from src.generator import TelemetryGenerator, load_assets, load_threshold_rules
from src.validators import infer_threshold_severity


def test_threshold_inference_identifies_normal_warning_and_critical():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    rules = load_threshold_rules()
    generator = TelemetryGenerator(seed=5)

    normal = generator.generate_event(asset, forced_severity="Normal").to_dict()
    warning = generator.generate_event(
        asset,
        forced_severity="Warning",
        forced_scenario="H2S_HIGH_WARNING",
    ).to_dict()
    critical = generator.generate_event(
        asset,
        forced_severity="Critical",
        forced_scenario="O2_INGRESS_AND_H2S_SPIKE",
    ).to_dict()

    assert infer_threshold_severity(normal, rules) == "Normal"
    assert infer_threshold_severity(warning, rules) == "Warning"
    assert infer_threshold_severity(critical, rules) == "Critical"


def test_plc_status_contributes_to_local_threshold_inference():
    asset = load_assets(site_count=1, assets_per_site=1)[0]
    rules = load_threshold_rules()
    generator = TelemetryGenerator(seed=6)

    stale = generator.generate_event(
        asset,
        forced_severity="Warning",
        forced_scenario="PLC_STALE_WARNING",
    ).to_dict()
    offline = generator.generate_event(
        asset,
        forced_severity="Critical",
        forced_scenario="PLC_OFFLINE_CRITICAL",
    ).to_dict()

    assert infer_threshold_severity(stale, rules) == "Warning"
    assert infer_threshold_severity(offline, rules) == "Critical"
