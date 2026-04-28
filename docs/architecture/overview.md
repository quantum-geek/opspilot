# Architecture overview

OpsPilot is a three-tier application: a Next.js web UI, a FastAPI backend, and an optional MCP server that exposes the same data as structured tools for AI agents.

## Components

### Web UI (`apps/web`)

Next.js 15 + TypeScript. Renders the incident dashboard and all AI-generated artifacts (analysis, stakeholder update, postmortem). Calls the API over HTTP. No database access of its own.

### API (`apps/api`)

FastAPI (Python). The system's single source of truth for all operations:

- Reads incident records, runbooks, and the service catalog from `data/`
- Calls Claude (via the Anthropic SDK) to generate analysis, stakeholder updates, and postmortem drafts
- Falls back to deterministic logic when no API key is set or the LLM call fails
- Records every generated artifact and every human approval/rejection to `data/audit/`
- Exposes a `/docs` Swagger UI for manual exploration

### MCP server (`apps/mcp-server`)

A [Model Context Protocol](https://modelcontextprotocol.io) server built with `fastmcp`. Exposes the same incident, runbook, and service catalog data as MCP tools and resources so that AI agents (Claude Desktop, MCP Inspector, custom agents) can query OpsPilot directly without going through the HTTP API.

Tools exposed:
- `list_incidents` — all incidents
- `get_incident(incident_id)` — single incident by ID
- `get_runbook(name)` — runbook contents by filename
- `list_services` — full service catalog

Run it with `mcp dev .\main.py` to open it in the MCP Inspector for interactive exploration.

### Seeded data (`data/`)

Flat files checked into the repo. No external database is required.

| Path | Contents |
|------|----------|
| `data/incidents/` | One JSON file per incident (e.g. `INC-001.json`) |
| `data/runbooks/` | Markdown files with YAML frontmatter (`id`, `service`, `incident`) |
| `data/services/catalog.yaml` | Service catalog — name, team, and runbook references |
| `data/postmortems/` | Completed postmortem documents (initially empty) |
| `data/audit/` | Per-incident audit trail JSON files (auto-created by the API) |

### LLM layer

The API uses `claude-haiku-4-5-20251001` for all LLM calls (analysis, stakeholder update, postmortem). Each call is wrapped in a try/except: if the call fails for any reason (missing key, network error, malformed response), the API returns the deterministic fallback result and logs a warning. The `draft_source` / `analysis_source` field in every response tells you whether the output came from the LLM (`"llm"`) or the fallback (`"fallback"`).

## Request flow

```
Browser → Web UI (Next.js :3000)
              │
              ▼
         API (FastAPI :8000)
              │
        ┌─────┴──────┐
        │             │
   data/ files    Anthropic API
   (incidents,    (Claude Haiku)
    runbooks,
    catalog,
    audit)

AI agent → MCP Inspector (:5173)
              │
              ▼
         MCP server (:stdio / :8001)
              │
              ▼
          data/ files
```
