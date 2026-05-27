from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from .sinks import csv_text_to_events
from .validators import validate_event_schema


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RECEIVED_EVENTS_PATH = DATA_DIR / "received_events.jsonl"

app = FastAPI(title="Ecotecco PLC Stream Receiver", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ecotecco-plc-stream-receiver"}


@app.post("/ingest/json")
async def ingest_json(event: dict[str, Any]) -> dict[str, Any]:
    errors = validate_event_schema(event)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    _append_received_event(event)
    return {
        "status": "accepted",
        "event_id": event.get("event_id"),
        "received_at": _utc_now(),
    }


@app.post("/ingest/csv")
async def ingest_csv(request: Request) -> dict[str, Any]:
    csv_text = (await request.body()).decode("utf-8")
    events = csv_text_to_events(csv_text)
    if not events:
        raise HTTPException(status_code=400, detail="CSV payload did not contain any events")

    for event in events:
        errors = validate_event_schema(event)
        if errors:
            raise HTTPException(status_code=400, detail=errors)

    for event in events:
        _append_received_event(event)

    return {
        "status": "accepted",
        "event_count": len(events),
        "received_at": _utc_now(),
    }


def _append_received_event(event: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with RECEIVED_EVENTS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
