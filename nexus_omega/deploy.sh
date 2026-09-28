#!/usr/bin/env bash
set -e

echo "=== [1/4] INITIALIZING ENVIRONMENT AND DEPENDENCY CHECKS ==="
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting."; exit 1; }
command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required. Aborting."; exit 1; }

COMPOSE="docker compose"
if ! docker compose version >/dev/null 2>&1; then
    COMPOSE="docker-compose"
fi

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
    fi
fi

echo "=== [2/4] STARTING INFRASTRUCTURE SERVICES (POSTGRES + REDIS) ==="
$COMPOSE up -d apex-postgres apex-redis
echo "Waiting for PostgreSQL and pgvector engine..."
sleep 5

echo "=== [3/4] SCAFFOLDING DATABASE SCHEMA AND EXTENSIONS ==="
docker exec -i apex-postgres psql -U postgres -d nexus_omega < init_db.sql || true

echo "=== [4/4] STARTING UNRESTRICTED AUTONOMOUS AGENT DAEMON ==="
$COMPOSE up -d --build apex-agent

echo "================================================================="
echo "NEXUS-OMEGA (APEX-1) is running 24/7 in background."
echo "Dashboard: http://localhost:8000"
echo "Tail logs using: $COMPOSE logs -f apex-agent"
echo "================================================================="
