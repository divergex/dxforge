#!/bin/sh
# generates a single htpasswd credential for pushing/pulling base execution images 
# (NOT tenant code, i.e., that should never touch the registry).
set -e

# this container runs as root.
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

if [ -f /auth/htpasswd ] && [ -f /secrets/registry_password.txt ]; then
  echo "[registry-bootstrap] htpasswd already exists — skipping."
  exit 0
fi

# stale htpasswd (e.g. image-seeded) without matching secrets
# must be replaced so the credential ends up in ./secrets only once.
rm -f /auth/htpasswd

PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -d '=+/\n')
htpasswd -Bbc /auth/htpasswd registry-user "$PASSWORD"

echo "registry-user" > /secrets/registry_user.txt
echo "$PASSWORD" > /secrets/registry_password.txt
chmod 600 /secrets/registry_*.txt
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

echo "[registry-bootstrap] Done. Credentials written to ./secrets/registry_*.txt"
