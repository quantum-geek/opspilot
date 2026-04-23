.PHONY: help install dev build up down logs clean

help:
	@echo "OpsPilot — available targets:"
	@echo "  install     Install all dependencies"
	@echo "  dev         Start all services in development mode"
	@echo "  build       Build Docker images"
	@echo "  up          Start services with Docker Compose"
	@echo "  down        Stop services"
	@echo "  logs        Tail Docker Compose logs"
	@echo "  clean       Remove build artifacts"

install:
	cd apps/web && npm install
	cd apps/api && pip install -r requirements.txt
	cd apps/mcp-server && pip install -r requirements.txt

dev-api:
	cd apps/api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-mcp:
	cd apps/mcp-server && python main.py

dev-web:
	cd apps/web && npm run dev

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	rm -rf apps/web/.next apps/web/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
