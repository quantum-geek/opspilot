import json
import pathlib
from datetime import datetime

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OpsPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolves to OpsPilot/data/ locally; docker-compose mounts it at /data
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"


@app.get("/health")
def health():
    return {"status": "ok", "service": "opspilot-api"}


@app.get("/")
def root():
    return {"message": "OpsPilot API — Week 1 scaffold"}


@app.get("/incidents/{incident_id}/summary")
def incident_summary(incident_id: str):
    """
    Structured incident summary.

    Reads from the same data sources the MCP tools expose — incidents/,
    services/catalog.yaml, runbooks/ — and enriches with derived fields
    (duration, runbook list from the service catalog).
    """
    incident_path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not incident_path.exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    incident = json.loads(incident_path.read_text())

    # Compute duration if the incident is resolved
    duration_minutes: int | None = None
    if incident.get("created_at") and incident.get("resolved_at"):
        t0 = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(incident["resolved_at"].replace("Z", "+00:00"))
        duration_minutes = int((t1 - t0).total_seconds() / 60)

    # Collect runbooks listed in the service catalog for each affected service
    runbooks: list[str] = []
    catalog_path = DATA_DIR / "services" / "catalog.yaml"
    if catalog_path.exists():
        catalog = yaml.safe_load(catalog_path.read_text()) or {}
        for svc in catalog.get("services", []):
            if svc["id"] in incident.get("affected_services", []):
                runbooks.extend(svc.get("runbooks", []))
    runbooks = list(dict.fromkeys(runbooks))  # deduplicate, preserve order

    return {
        "incident_id": incident["id"],
        "title": incident["title"],
        "severity": incident["severity"],
        "status": incident["status"],
        "duration_minutes": duration_minutes,
        "affected_services": incident["affected_services"],
        "summary": incident["summary"],
        "root_cause": incident.get("root_cause"),
        "resolution": incident.get("resolution"),
        "runbooks": runbooks,
        "responders": incident.get("responders", []),
        "labels": incident.get("labels", []),
    }
