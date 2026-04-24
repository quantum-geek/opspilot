import json
import pathlib
import re
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

    incident = json.loads(incident_path.read_text(encoding="utf-8"))

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
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
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


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _extract_mitigation_steps(runbook_body: str) -> list[str]:
    """Pull step titles from the Mitigation section of a runbook."""
    match = re.search(r"## Mitigation\n(.*?)(?=\n## |\Z)", runbook_body, re.DOTALL)
    if match:
        options = re.findall(r"### (.+)", match.group(1))
        if options:
            return [o.strip() for o in options]
    # Fall back to bold numbered items anywhere in the doc
    return re.findall(r"^\d+\.\s+\*\*(.+?)\*\*", runbook_body, re.MULTILINE)


def _derive_steps_from_labels(labels: list[str]) -> list[str]:
    steps: list[str] = []
    if "rollback" in labels:
        steps.append("Roll back the most recent deployment to the last known-good version")
    if "database" in labels:
        steps.append("Check database connection pool utilization and active query count")
    if "latency" in labels:
        steps.append("Confirm p99 latency spike in monitoring and identify the slow component")
    if not steps:
        steps.append("Investigate recent deployments and configuration changes")
        steps.append("Review service logs for errors or anomalies")
    return steps


@app.get("/incidents/{incident_id}/analysis")
def incident_analysis(incident_id: str):
    incident_path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not incident_path.exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    affected = incident.get("affected_services", [])

    # Load service catalog
    catalog_path = DATA_DIR / "services" / "catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    matched_services = [s for s in catalog.get("services", []) if s["id"] in affected]

    # Teams owning affected services (preserves order, deduplicates)
    teams = list(dict.fromkeys(s["team"] for s in matched_services if s.get("team")))

    # Runbook IDs listed in the catalog for affected services
    catalog_runbook_ids: list[str] = []
    for svc in matched_services:
        catalog_runbook_ids.extend(svc.get("runbooks", []))
    catalog_runbook_ids = list(dict.fromkeys(catalog_runbook_ids))

    # Try to find a runbook file that matches this incident or one of its services
    runbooks_dir = DATA_DIR / "runbooks"
    recommended_runbook: str | None = None
    recommended_steps: list[str] = []

    for rb_id in catalog_runbook_ids:
        rb_path = runbooks_dir / f"{rb_id}.md"
        if not rb_path.exists():
            continue
        content = rb_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            continue
        if meta.get("incident") == incident_id or meta.get("service") in affected:
            recommended_runbook = meta.get("id", rb_id)
            recommended_steps = _extract_mitigation_steps(parts[2])
            break

    if not recommended_steps:
        recommended_steps = _derive_steps_from_labels(incident.get("labels", []))

    # Escalation targets: service-owning teams + incident responders
    escalation_targets = list(dict.fromkeys(teams + incident.get("responders", [])))

    likely_cause = incident.get("root_cause") or "Unknown — further investigation required"

    reasoning_summary = (
        f"This {incident.get('severity', 'unknown')} incident affected "
        f"{len(affected)} service(s) ({', '.join(affected)}) "
        f"and is currently {incident.get('status', 'unknown')}. "
    )
    if recommended_runbook:
        reasoning_summary += f"Runbook {recommended_runbook} directly covers this scenario. "
    reasoning_summary += f"Root cause: {likely_cause.rstrip('.')}."

    return {
        "incident_id": incident["id"],
        "likely_cause": likely_cause,
        "recommended_steps": recommended_steps,
        "recommended_runbook": recommended_runbook,
        "escalation_targets": escalation_targets,
        "reasoning_summary": reasoning_summary,
    }


# ---------------------------------------------------------------------------
# Stakeholder update helpers
# ---------------------------------------------------------------------------

def _parse_post_incident_steps(runbook_body: str) -> list[str]:
    """Extract bullet items from the Post-Incident section of a runbook."""
    match = re.search(r"## Post-Incident\n(.*?)(?=\n## |\Z)", runbook_body, re.DOTALL)
    if not match:
        return []
    items = re.findall(r"^-\s+(.+)", match.group(1), re.MULTILINE)
    return [re.sub(r"`([^`]+)`", r"\1", item).strip() for item in items]


def _derive_next_steps(labels: list[str], status: str) -> list[str]:
    steps: list[str] = []
    if status == "resolved":
        steps.append("Complete post-mortem within 24 hours")
    if "database" in labels:
        steps.append("Permanently increase database connection pool size via infrastructure-as-code")
    if "rollback" in labels:
        steps.append("Investigate and fix the root cause before re-deploying the rolled-back version")
    if not steps:
        steps.append("Review and document the incident timeline")
    return steps


@app.get("/incidents/{incident_id}/stakeholder-update")
def incident_stakeholder_update(incident_id: str):
    incident_path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not incident_path.exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    affected = incident.get("affected_services", [])
    severity = incident.get("severity", "unknown")
    status = incident.get("status", "unknown")
    title = incident.get("title", "Incident")

    # Duration
    duration_minutes: int | None = None
    if incident.get("created_at") and incident.get("resolved_at"):
        t0 = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(incident["resolved_at"].replace("Z", "+00:00"))
        duration_minutes = int((t1 - t0).total_seconds() / 60)

    # Audience by severity
    audience_map = {
        "P0": "Executive Leadership, Engineering Leadership, Customer Success, Product",
        "P1": "Engineering Leadership, Customer Success, Product",
        "P2": "Engineering Leadership, Customer Success",
    }
    audience = audience_map.get(severity, "Engineering Team")

    subject = f"{incident_id} [{severity}] {title} — {status.capitalize()}"

    # Prose update
    prose: list[str] = [f"{title} is currently {status}."]
    if incident.get("summary"):
        prose.append(incident["summary"])
    if incident.get("root_cause"):
        prose.append(f"Root cause: {incident['root_cause'].rstrip('.')}.")
    if incident.get("resolution"):
        prose.append(f"Resolution: {incident['resolution'].rstrip('.')}.")
    if duration_minutes is not None:
        prose.append(f"Total duration: {duration_minutes} minutes.")
    update_text = " ".join(prose)

    # Impact summary
    svc_list = ", ".join(affected) if affected else "unknown services"
    impact_summary = (incident.get("summary", "") + " " if incident.get("summary") else "")
    impact_summary += (
        f"Affected {svc_list} for {duration_minutes} minutes."
        if duration_minutes is not None
        else f"Affected {svc_list}."
    )

    # Next steps: prefer runbook Post-Incident section
    catalog_path = DATA_DIR / "services" / "catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    matched_services = [s for s in catalog.get("services", []) if s["id"] in affected]
    catalog_runbook_ids: list[str] = []
    for svc in matched_services:
        catalog_runbook_ids.extend(svc.get("runbooks", []))
    catalog_runbook_ids = list(dict.fromkeys(catalog_runbook_ids))

    next_steps: list[str] = []
    runbooks_dir = DATA_DIR / "runbooks"
    for rb_id in catalog_runbook_ids:
        rb_path = runbooks_dir / f"{rb_id}.md"
        if not rb_path.exists():
            continue
        content = rb_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        rb_parts = content.split("---", 2)
        if len(rb_parts) < 3:
            continue
        try:
            meta = yaml.safe_load(rb_parts[1]) or {}
        except yaml.YAMLError:
            continue
        if meta.get("incident") == incident_id or meta.get("service") in affected:
            next_steps = _parse_post_incident_steps(rb_parts[2])
            break

    if not next_steps:
        next_steps = _derive_next_steps(incident.get("labels", []), status)

    return {
        "incident_id": incident["id"],
        "audience": audience,
        "subject": subject,
        "update_text": update_text,
        "status": status,
        "impact_summary": impact_summary,
        "next_steps": next_steps,
    }
