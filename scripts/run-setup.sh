#!/bin/sh
set -e

LAST_STEP=""

step() {
  LAST_STEP="$1"
  echo ""
  echo "==> [$(date +%H:%M:%S)] $2"
}

on_error() {
  status=$?
  echo ""
  echo "!!! dxforge setup failed at: ${LAST_STEP:-startup} (exit $status)"
  echo "!!! Recent logs:"
  docker compose logs --tail=40 2>/dev/null | tail -40 || true
  exit $status
}
trap on_error ERR

step "docker" "Checking Docker daemon..."
docker info >/dev/null 2>&1 || {
  echo "!!! Docker daemon is not running. Start it and re-run 'make setup'."
  exit 1
}

step "secrets" "Generating root secrets (./secrets, existing files are not overwritten)..."
./scripts/gen-root-secrets.sh

step "services" "Starting Postgres, MinIO, OpenBao and registry (first image pull may take a while)..."
docker compose up -d postgres minio openbao registry
docker compose ps

# TODO: maybe programatic? don't know... 
step "openbao" "Bootstrapping OpenBao: init/unseal, transit engine, policies, scoped tokens..."
docker compose run --rm openbao-bootstrap

step "minio" "Bootstrapping MinIO: tenant-code bucket + ingest/execution service accounts..."
docker compose run --rm minio-bootstrap

step "registry" "Bootstrapping registry auth (htpasswd)..."
docker compose run --rm registry-bootstrap

step "migrate" "Running database migrations (alembic upgrade head)..."
docker compose run --rm db-migrate

echo ""
echo "dxforge is up."
echo "   Credentials are in ./secrets"
docker compose ps
