# Ecotecco PLC Stream Simulator

Part 1 of the Microsoft Fabric Real-Time Intelligence demo: a PLC-style telemetry simulator for gas and process monitoring in wet waste, biogas, wastewater, and landfill gas operations.

This project only covers the local simulator and receiver:

```text
Gas Sensors / Biogas Process
    -> PLC Device Simulator
    -> JSON or CSV event stream
    -> Local Server Receiver
    -> Future Azure Event Hub / Fabric RTI
```

Azure Event Hub, Fabric Eventstream, KQL, Data Activator, Power BI, and predictive maintenance are intentionally out of scope for this step.

## What It Generates

The simulator creates one telemetry event per PLC per interval. The default MVP fleet is:

- 3 sites
- 2 assets per site
- 1 PLC per asset
- 6 PLCs total
- 1 event every 5 seconds per PLC

Each event includes:

- CH4, CO2, O2, balance gas, H2S
- Temperature
- Static pressure
- Gas flow
- PLC status
- Fabric routing fields: `industry_type`, `region`, `site_type`
- Site, asset, PLC, and sensor package metadata
- `simulated_scenario` and `expected_severity` for local validation

The generator uses the configured demo anomaly mix:

- About 89% normal rows
- About 9% warning rows
- About 2% critical rows

These thresholds are demo thresholds, not safety limits.

## Setup

```powershell
cd C:\Users\karth\Downloads\RTI_PredictiveMaintenance\ecotecco-plc-stream
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run The Local Receiver

```powershell
uvicorn src.server:app --reload --port 8000
```

Health check:

```powershell
curl http://localhost:8000/health
```

Received JSON events are appended to:

```text
data/received_events.jsonl
```

## Generate JSON To Console

```powershell
python -m src.main --format json --output console --interval-seconds 5
```

Stop with `Ctrl+C`.

## Generate JSON To File

```powershell
python -m src.main --format json --output file --duration-seconds 300
```

Output:

```text
data/generated_stream.jsonl
```

For file output with a duration, the simulator generates the simulated time window quickly instead of waiting in real time.

## Send PLC Events To Server

Start the server first, then run:

```powershell
python -m src.main --format json --output server --server-url http://localhost:8000/ingest/json --interval-seconds 5
```

## Generate CSV

```powershell
python -m src.main --format csv --output file --duration-seconds 300
```

Output:

```text
data/generated_stream.csv
```

CSV events can also be posted to:

```text
http://localhost:8000/ingest/csv
```

## Send JSON To Azure Event Hub

Create a local `.env` file:

```text
AZURE_EVENTHUB_CONNECTION_STRING=<your-send-connection-string>
AZURE_EVENTHUB_NAME=ehub-ecotecco-plc-telemetry
```

`AZURE_EVENTHUB_CONNECTION_STRING` must be the full Send connection string. It should include `Endpoint=sb://`, `SharedAccessKeyName=`, and `SharedAccessKey=`.

Do not commit `.env`; it contains the Event Hub send secret.

Run:

```powershell
python -m src.main --format json --output eventhub --duration-seconds 60 --interval-seconds 5
```

Expected result: the simulator sends PLC-style gas telemetry events to Azure Event Hub.

## Streamlit Event Hub Sender

The Streamlit frontend sends only to Azure Event Hub. Create `.env` as shown above, then run:

```powershell
streamlit run streamlit_app.py
```

Use the duration field to choose how many minutes of PLC telemetry to send.

## Routing Fields For Fabric Eventstream

The simulator emits routing fields used later by Fabric Eventstream to route records into industry-specific Bronze tables:

- `industry_type`
- `region`
- `site_type`

Mapping:

- North Biogas Facility -> Biogas / North / Biogas Facility
- West Wastewater Works -> Wastewater / West / Wastewater Treatment Plant
- South Landfill Gas Field -> LandfillGas / South / Landfill Gas Field

This phase only updates the Python telemetry payload. Fabric Eventstream routing and KQL Bronze table changes will be handled in later phases.

## Useful CLI Options

```text
--format json|csv
--interval-seconds 5
--duration-seconds 300
--output console|file|server|eventhub
--site-count 3
--assets-per-site 2
--server-url http://localhost:8000/ingest/json
--seed 42
```

## Tests

```powershell
pytest
```

The tests verify:

- Required schema fields are present
- Fabric routing fields are present and mapped correctly
- Gas composition stays realistic
- Normal rows stay within normal demo ranges
- Warning and critical rows are generated
- The anomaly ratio is approximately correct
- JSONL and CSV file outputs work
- Event Hub JSON serialization and missing environment variable errors work
- Threshold inference returns expected demo severities

## Project Structure

```text
ecotecco-plc-stream/
  README.md
  requirements.txt
  config/
    sites.json
    threshold_rules.json
  samples/
    sample_normal_payload.json
    sample_alert_payload.json
  data/
    generated_stream.jsonl
    generated_stream.csv
  src/
    __init__.py
    main.py
    models.py
    generator.py
    plc_simulator.py
    server.py
    sinks.py
    validators.py
  tests/
    test_generator.py
    test_schema.py
    test_thresholds.py
```

## Extension Point For Step 2

`src/sinks.py` is the right place to add an Azure Event Hub sink later. The generator and simulator already work against a small sink interface, so Step 2 can add a new sink without rewriting the telemetry model.
