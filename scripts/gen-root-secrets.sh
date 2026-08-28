#!/bin/sh
# Safe to re-run
set -e

mkdir -p secrets

gen() { head -c 24 /dev/urandom | base64 | tr -d '=+/\n'; }

if [ ! -f secrets/postgres_password.txt ]; then
  gen > secrets/postgres_password.txt
  echo "Generated secrets/postgres_password.txt"
fi

if [ ! -f secrets/minio_root_user.txt ]; then
  echo "forge-root" > secrets/minio_root_user.txt
  echo "Generated secrets/minio_root_user.txt"
fi

if [ ! -f secrets/minio_root_password.txt ]; then
  gen > secrets/minio_root_password.txt
  echo "Generated secrets/minio_root_password.txt"
fi

if [ ! -f secrets/postgres_app_user.txt ]; then
  echo "forge_app" > secrets/postgres_app_user.txt
  echo "Generated secrets/postgres_app_user.txt"
fi

if [ ! -f secrets/postgres_app_password.txt ]; then
  gen > secrets/postgres_app_password.txt
  echo "Generated secrets/postgres_app_password.txt"
fi

# chmod only what is owned
chmod 600 secrets/*.txt 2>/dev/null || true
echo "Root secrets in ./secrets"
