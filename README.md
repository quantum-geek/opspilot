# OpsPilot

AI-powered incident response and operations platform.

## Structure

```
OpsPilot/
├── apps/
│   ├── web/          # Next.js 15 + TypeScript frontend
│   ├── api/          # FastAPI backend
│   └── mcp-server/   # Model Context Protocol server (tools for AI agents)
├── data/
│   ├── incidents/    # Incident records (JSON)
│   ├── runbooks/     # Runbooks (Markdown + YAML frontmatter)
│   ├── services/     # Service catalog (YAML)
│   └── postmortems/  # Post-mortem documents
├── docs/
│   └── architecture/ # Architecture decision records
├── scripts/          # Utility scripts
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Quick Start

### Docker (any OS)

```bash
cp .env.example .env        # Linux / macOS / Git Bash
# edit .env and add your ANTHROPIC_API_KEY

make build
make up
```

### Local development — Unix / macOS / Git Bash

```bash
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY

make install
make dev-api      # terminal 1
make dev-mcp      # terminal 2
make dev-web      # terminal 3
```

### Local development — Windows (PowerShell)

## Local Development

### Prerequisites
- Node.js and npm installed
- Python 3.11+ installed
- PowerShell on Windows
- `.env` file created from `.env.example`

Create `.env` once from the repo root:

```powershell
Copy-Item .env.example .env
# open .env and add your ANTHROPIC_API_KEY

# Install dependencies
cd apps\web; npm install; cd ..\..
cd apps\api; pip install -r requirements.txt; cd ..\..
cd apps\mcp-server; pip install -r requirements.txt; cd ..\..

# Start each service in a separate terminal
# Terminal 1 — API
cd apps\api; uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — MCP server
cd apps\mcp-server; python main.py

# Terminal 3 — Web
cd apps\web; npm run dev
```

## Services

| Service    | Local URL                   |
|------------|-----------------------------|
| Web        | http://localhost:3000       |
| API        | http://localhost:8000       |
| API docs   | http://localhost:8000/docs  |
| MCP server | http://localhost:8001       |

## Roadmap

- **Week 1** — Monorepo scaffold, seed data ✅
- **Week 2** — Incident ingestion API + data models
- **Week 3** — MCP tools wired to AI agent
- **Week 4** — Frontend incident dashboard
