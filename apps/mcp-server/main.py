import json
import os
import pathlib
from mcp.server.fastmcp import FastMCP

DATA_DIR = pathlib.Path(__file__).parent.parent.parent / "data"

mcp = FastMCP("opspilot-mcp", port=int(os.getenv("MCP_PORT", "8001")))


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("opspilot://incidents/all")
def incidents_resource() -> str:
    """All incident records serialised as JSON."""
    incidents_dir = DATA_DIR / "incidents"
    results = [json.loads(f.read_text()) for f in incidents_dir.glob("*.json")]
    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_incidents() -> list[dict]:
    """Return all incidents from the data store."""
    incidents_dir = DATA_DIR / "incidents"
    return [json.loads(f.read_text()) for f in incidents_dir.glob("*.json")]


@mcp.tool()
def get_incident(incident_id: str) -> dict | str:
    """Return a single incident by ID (e.g. 'INC-001')."""
    path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not path.exists():
        return f"Incident '{incident_id}' not found."
    return json.loads(path.read_text())


@mcp.tool()
def get_runbook(name: str) -> str:
    """Return the contents of a runbook by filename (without .md extension)."""
    path = DATA_DIR / "runbooks" / f"{name}.md"
    if not path.exists():
        return f"Runbook '{name}' not found."
    return path.read_text()


@mcp.tool()
def list_services() -> dict:
    """Return the service catalog."""
    import yaml  # type: ignore
    path = DATA_DIR / "services" / "catalog.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def triage_incident(incident_id: str) -> str:
    """
    Build a structured triage prompt for an on-call engineer given an incident ID.
    Returns a ready-to-use prompt string with incident context pre-filled.
    """
    path = DATA_DIR / "incidents" / f"{incident_id}.json"
    if not path.exists():
        return f"Incident '{incident_id}' not found in the data store."
    inc = json.loads(path.read_text())
    return (
        f"You are an on-call SRE responding to a production incident.\n\n"
        f"## Incident: {inc['id']} — {inc['title']}\n"
        f"- **Severity**: {inc['severity']}\n"
        f"- **Status**: {inc['status']}\n"
        f"- **Affected services**: {', '.join(inc['affected_services'])}\n"
        f"- **Summary**: {inc['summary']}\n\n"
        f"Using the available runbooks and service catalog, recommend:\n"
        f"1. Immediate mitigation steps.\n"
        f"2. Which runbook to follow.\n"
        f"3. Who to page if the issue is not resolved within 15 minutes."
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()
