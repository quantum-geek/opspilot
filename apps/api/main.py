import json
import logging
import os
import pathlib
import re
from datetime import datetime

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="OpsPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolves to OpsPilot/data/ locally; docker-compose mounts it at /data
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
AUDIT_DIR = DATA_DIR / "audit"


# ---------------------------------------------------------------------------
# Audit trail helpers
# ---------------------------------------------------------------------------

def _append_audit_event(incident_id: str, artifact_type: str, source: str, action: str) -> dict:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"{incident_id}.json"
    events: list = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else []
    event = {
        "incident_id": incident_id,
        "artifact_type": artifact_type,
        "source": source,
        "action": action,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    events.append(event)
    audit_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    return event


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
# LLM incident analysis
# ---------------------------------------------------------------------------

def _llm_incident_analysis(
    incident: dict,
    catalog_yaml: str,
    runbook_text: str,
) -> dict:
    """Call Claude to produce likely_cause, recommended_steps, recommended_runbook,
    escalation_targets, and reasoning_summary.

    Raises on any failure so callers can fall back to deterministic logic.
    """
    import anthropic  # lazy import — only needed when LLM path is taken

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    prompt = (
        "You are an expert SRE performing incident analysis. "
        "Analyze the incident below and return a JSON object.\n\n"
        f"INCIDENT:\n{json.dumps(incident, indent=2)}\n\n"
        f"SERVICE CATALOG (relevant excerpt):\n{catalog_yaml}\n\n"
        f"RUNBOOK:\n{runbook_text}\n\n"
        "Return a JSON object with exactly these five keys:\n"
        '  "likely_cause"        — one concise sentence stating the root cause\n'
        '  "recommended_steps"   — JSON array of 2-4 ordered mitigation steps (strings)\n'
        '  "recommended_runbook" — runbook id string, or null if none applies\n'
        '  "escalation_targets"  — JSON array of team/role strings to escalate to\n'
        '  "reasoning_summary"   — 2-3 sentence explanation of the analysis\n\n'
        "Output only the JSON object, no markdown fences or extra text."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    for key in ("likely_cause", "recommended_steps", "recommended_runbook", "escalation_targets", "reasoning_summary"):
        if key not in result:
            raise KeyError(f"LLM response missing key: {key}")
    if not isinstance(result["recommended_steps"], list):
        raise TypeError("recommended_steps must be a list")
    if not isinstance(result["escalation_targets"], list):
        raise TypeError("escalation_targets must be a list")
    return result


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

    # Attempt LLM-backed analysis; silently fall back on any failure
    analysis_source = "fallback"
    runbook_text = ""
    for rb_id in catalog_runbook_ids:
        rb_path = runbooks_dir / f"{rb_id}.md"
        if rb_path.exists():
            runbook_text = rb_path.read_text(encoding="utf-8")
            break

    try:
        llm = _llm_incident_analysis(
            incident=incident,
            catalog_yaml=catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else "",
            runbook_text=runbook_text,
        )
        likely_cause = llm["likely_cause"]
        recommended_steps = llm["recommended_steps"]
        recommended_runbook = llm["recommended_runbook"]
        escalation_targets = llm["escalation_targets"]
        reasoning_summary = llm["reasoning_summary"]
        analysis_source = "llm"
    except Exception as exc:
        logger.warning("LLM incident analysis failed, using fallback: %s", exc)

    _append_audit_event(incident["id"], "analysis", analysis_source, "generated")
    return {
        "incident_id": incident["id"],
        "likely_cause": likely_cause,
        "recommended_steps": recommended_steps,
        "recommended_runbook": recommended_runbook,
        "escalation_targets": escalation_targets,
        "reasoning_summary": reasoning_summary,
        "analysis_source": analysis_source,
    }


# ---------------------------------------------------------------------------
# LLM stakeholder update
# ---------------------------------------------------------------------------

def _llm_draft_stakeholder_update(
    incident: dict,
    catalog_yaml: str,
    runbook_text: str,
    duration_minutes: int | None,
    audience: str,
) -> dict:
    """Call Claude to draft update_text, impact_summary, and next_steps.

    Raises on any failure so callers can fall back to deterministic logic.
    """
    import anthropic  # lazy import — only needed when LLM path is taken

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    duration_line = f"Duration: {duration_minutes} minutes" if duration_minutes is not None else "Duration: ongoing"

    prompt = (
        "You are an incident communications specialist. "
        "Draft a stakeholder update for the incident below.\n\n"
        f"INCIDENT:\n{json.dumps(incident, indent=2)}\n\n"
        f"SERVICE CATALOG (relevant excerpt):\n{catalog_yaml}\n\n"
        f"RUNBOOK:\n{runbook_text}\n\n"
        f"{duration_line}\n\n"
        f"AUDIENCE: {audience}\n\n"
        "Return a JSON object with exactly these three keys:\n"
        '  "update_text"    — 2-3 sentence prose update appropriate for the audience\n'
        '  "impact_summary" — one sentence describing the business impact\n'
        '  "next_steps"     — JSON array of 2-4 concise action items (strings)\n\n'
        "Output only the JSON object, no markdown fences or extra text."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if the model adds them anyway
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    # Validate expected keys are present
    for key in ("update_text", "impact_summary", "next_steps"):
        if key not in result:
            raise KeyError(f"LLM response missing key: {key}")
    if not isinstance(result["next_steps"], list):
        raise TypeError("next_steps must be a list")
    return result


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

    # Attempt LLM-backed drafting; silently fall back on any failure
    draft_source = "fallback"
    runbook_text = ""
    for rb_id in catalog_runbook_ids:
        rb_path = runbooks_dir / f"{rb_id}.md"
        if rb_path.exists():
            runbook_text = rb_path.read_text(encoding="utf-8")
            break

    try:
        llm = _llm_draft_stakeholder_update(
            incident=incident,
            catalog_yaml=catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else "",
            runbook_text=runbook_text,
            duration_minutes=duration_minutes,
            audience=audience,
        )
        update_text = llm["update_text"]
        impact_summary = llm["impact_summary"]
        next_steps = llm["next_steps"]
        draft_source = "llm"
    except Exception as exc:
        logger.warning("LLM stakeholder update failed, using fallback: %s", exc)

    _append_audit_event(incident["id"], "stakeholder_update", draft_source, "generated")
    return {
        "incident_id": incident["id"],
        "audience": audience,
        "subject": subject,
        "update_text": update_text,
        "status": status,
        "impact_summary": impact_summary,
        "next_steps": next_steps,
        "draft_source": draft_source,
    }


# ---------------------------------------------------------------------------
# Postmortem draft helpers
# ---------------------------------------------------------------------------

def _deterministic_postmortem_draft(
    incident: dict,
    duration_minutes: int | None,
    follow_ups: list[str],
) -> dict:
    affected = incident.get("affected_services", [])
    svc_list = ", ".join(affected) if affected else "unknown services"

    impact = f"Affected services: {svc_list}."
    if duration_minutes is not None:
        impact += f" Total downtime: {duration_minutes} minutes."

    timeline: list[str] = []
    if incident.get("created_at"):
        timeline.append(f"{incident['created_at']} — Incident detected.")
    if incident.get("resolved_at"):
        timeline.append(f"{incident['resolved_at']} — Incident resolved.")

    return {
        "title": f"Post-Mortem: {incident.get('title', 'Incident')}",
        "summary": incident.get("summary", ""),
        "impact": impact,
        "timeline": timeline,
        "root_cause": incident.get("root_cause") or "Unknown — further investigation required.",
        "resolution": incident.get("resolution") or "No resolution recorded.",
        "follow_ups": follow_ups,
    }


def _llm_postmortem_draft(
    incident: dict,
    catalog_yaml: str,
    runbook_text: str,
    duration_minutes: int | None,
) -> dict:
    """Call Claude to produce a structured postmortem draft.

    Raises on any failure so callers can fall back to deterministic logic.
    """
    import anthropic  # lazy import

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    duration_line = (
        f"Duration: {duration_minutes} minutes" if duration_minutes is not None else "Duration: ongoing"
    )

    prompt = (
        "You are an SRE writing a post-mortem document. "
        "Use the incident data below to produce a structured post-mortem draft.\n\n"
        f"INCIDENT:\n{json.dumps(incident, indent=2)}\n\n"
        f"SERVICE CATALOG (relevant excerpt):\n{catalog_yaml}\n\n"
        f"RUNBOOK:\n{runbook_text}\n\n"
        f"{duration_line}\n\n"
        "Return a JSON object with exactly these six keys:\n"
        '  "title"      — post-mortem document title (string)\n'
        '  "summary"    — 2-3 sentence executive summary (string)\n'
        '  "impact"     — one sentence describing customer / business impact (string)\n'
        '  "timeline"   — ordered list of key events as strings, e.g. "2026-04-20T14:32Z — Incident detected"\n'
        '  "root_cause" — concise root cause statement (string)\n'
        '  "resolution" — what was done to resolve the incident (string)\n'
        '  "follow_ups" — JSON array of 2-5 action items to prevent recurrence (strings)\n\n'
        "Output only the JSON object, no markdown fences or extra text."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=768,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    for key in ("title", "summary", "impact", "timeline", "root_cause", "resolution", "follow_ups"):
        if key not in result:
            raise KeyError(f"LLM response missing key: {key}")
    if not isinstance(result["timeline"], list):
        raise TypeError("timeline must be a list")
    if not isinstance(result["follow_ups"], list):
        raise TypeError("follow_ups must be a list")
    return result


@app.get("/incidents/{incident_id}/postmortem-draft")
def incident_postmortem_draft(incident_id: str):
    incident_path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not incident_path.exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    incident = json.loads(incident_path.read_text(encoding="utf-8"))
    affected = incident.get("affected_services", [])

    # Duration
    duration_minutes: int | None = None
    if incident.get("created_at") and incident.get("resolved_at"):
        t0 = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(incident["resolved_at"].replace("Z", "+00:00"))
        duration_minutes = int((t1 - t0).total_seconds() / 60)

    # Catalog + runbook lookup
    catalog_path = DATA_DIR / "services" / "catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    matched_services = [s for s in catalog.get("services", []) if s["id"] in affected]
    catalog_runbook_ids: list[str] = []
    for svc in matched_services:
        catalog_runbook_ids.extend(svc.get("runbooks", []))
    catalog_runbook_ids = list(dict.fromkeys(catalog_runbook_ids))

    runbooks_dir = DATA_DIR / "runbooks"
    runbook_text = ""
    follow_ups: list[str] = []
    for rb_id in catalog_runbook_ids:
        rb_path = runbooks_dir / f"{rb_id}.md"
        if not rb_path.exists():
            continue
        content = rb_path.read_text(encoding="utf-8")
        runbook_text = content
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
            follow_ups = _parse_post_incident_steps(rb_parts[2])
            break

    if not follow_ups:
        follow_ups = _derive_next_steps(incident.get("labels", []), incident.get("status", ""))

    # Build deterministic draft as baseline
    draft = _deterministic_postmortem_draft(incident, duration_minutes, follow_ups)
    draft_source = "fallback"

    # Attempt LLM draft; silently fall back on any failure
    try:
        llm = _llm_postmortem_draft(
            incident=incident,
            catalog_yaml=catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else "",
            runbook_text=runbook_text,
            duration_minutes=duration_minutes,
        )
        draft = llm
        draft_source = "llm"
    except Exception as exc:
        logger.warning("LLM postmortem draft failed, using fallback: %s", exc)

    _append_audit_event(incident["id"], "postmortem_draft", draft_source, "generated")
    return {
        "incident_id": incident["id"],
        "draft_source": draft_source,
        **draft,
    }


# ---------------------------------------------------------------------------
# Audit endpoints
# ---------------------------------------------------------------------------

def _require_incident(incident_id: str) -> None:
    if not (DATA_DIR / "incidents" / f"{incident_id}.json").exists():
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")


@app.get("/incidents/{incident_id}/audit")
def incident_audit(incident_id: str):
    _require_incident(incident_id)
    audit_path = AUDIT_DIR / f"{incident_id}.json"
    events = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else []
    return {"incident_id": incident_id, "events": events}


@app.post("/incidents/{incident_id}/stakeholder-update/approve")
def approve_stakeholder_update(incident_id: str):
    _require_incident(incident_id)
    event = _append_audit_event(incident_id, "stakeholder_update", "human", "approved")
    return {"ok": True, "event": event}


@app.post("/incidents/{incident_id}/stakeholder-update/reject")
def reject_stakeholder_update(incident_id: str):
    _require_incident(incident_id)
    event = _append_audit_event(incident_id, "stakeholder_update", "human", "rejected")
    return {"ok": True, "event": event}


@app.post("/incidents/{incident_id}/postmortem-draft/approve")
def approve_postmortem_draft(incident_id: str):
    _require_incident(incident_id)
    event = _append_audit_event(incident_id, "postmortem_draft", "human", "approved")
    return {"ok": True, "event": event}


@app.post("/incidents/{incident_id}/postmortem-draft/reject")
def reject_postmortem_draft(incident_id: str):
    _require_incident(incident_id)
    event = _append_audit_event(incident_id, "postmortem_draft", "human", "rejected")
    return {"ok": True, "event": event}
