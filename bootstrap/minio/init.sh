#!/bin/sh
#   - creates the tenant-code bucket
#   - creates two scoped, least-privilege service accounts
#     (app-server: read/write; worker: read-only)
#   - root credentials should only used here
set -e

MINIO_ROOT_USER=$(cat /run/secrets/minio_root_user)
MINIO_ROOT_PASSWORD=$(cat /run/secrets/minio_root_password)
export MC_HOST_local="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000"

echo "[minio-bootstrap] Waiting for MinIO..."
until mc ls local >/dev/null 2>&1; do
  sleep 2
done

# this container runs as root.
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

if [ -f /secrets/minio_app_server_key.txt ]; then
  echo "[minio-bootstrap] skipping (already bootstrapped)."
  exit 0
fi

echo "[minio-bootstrap] creating bucket..."
mc mb --ignore-existing local/tenant-code

gen_secret() {
  head -c 32 /dev/urandom | base64 | tr -d '=+/\n' | cut -c1-32
}

APP_SECRET=$(gen_secret)
WORKER_SECRET=$(gen_secret)

echo "[minio-bootstrap] creating scoped service accounts..."
mc admin user add local app-server-key "$APP_SECRET"
mc admin user add local worker-key "$WORKER_SECRET"

mc admin policy create local app-server-policy /scripts/policies/app-server.json
mc admin policy create local worker-policy /scripts/policies/worker.json
mc admin policy attach local app-server-policy --user=app-server-key
mc admin policy attach local worker-policy --user=worker-key

echo "app-server-key" > /secrets/minio_app_server_key.txt
echo "$APP_SECRET" > /secrets/minio_app_server_secret.txt
echo "worker-key" > /secrets/minio_worker_key.txt
echo "$WORKER_SECRET" > /secrets/minio_worker_secret.txt
chmod 600 /secrets/minio_*key.txt /secrets/minio_*secret.txt
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

echo "[minio-bootstrap] Done. keep root credentials offline."
