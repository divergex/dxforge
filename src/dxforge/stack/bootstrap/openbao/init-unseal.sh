#!/bin/sh
# Idempotent OpenBao bootstrap:
#   - first run: initializes storage, writes root token + unseal keys to
#     ./secrets, unseals.
#   - every run (incl. first): ensures transit keys, policies, and re-issues
#     scoped tokens (tokens capture their policy set at creation).
set -e

export BAO_ADDR="http://openbao:8200"

apk add --no-cache jq curl >/dev/null 2>&1 || true

echo "[openbao-bootstrap] Waiting for OpenBao API..."
until curl -s "$BAO_ADDR/v1/sys/health" >/dev/null 2>&1; do
  sleep 2
done

if [ -f /secrets/openbao_root_token.txt ]; then
  echo "[openbao-bootstrap] Existing init found — unsealing only."
  for i in 1 2 3; do
    bao operator unseal "$(cat /secrets/openbao_unseal_key_${i}.txt)"
  done
else
  echo "[openbao-bootstrap] First run — initializing OpenBao..."
  INIT_OUTPUT=$(bao operator init -key-shares=5 -key-threshold=3 -format=json)

  echo "$INIT_OUTPUT" | jq -r '.root_token' > /secrets/openbao_root_token.txt
  i=1
  for key in $(echo "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[]'); do
    echo "$key" > "/secrets/openbao_unseal_key_${i}.txt"
    i=$((i + 1))
  done
  chmod 600 /secrets/openbao_*.txt

  echo "[openbao-bootstrap] Unsealing..."
  for i in 1 2 3; do
    bao operator unseal "$(cat /secrets/openbao_unseal_key_${i}.txt)"
  done
fi

export BAO_TOKEN
BAO_TOKEN=$(cat /secrets/openbao_root_token.txt)

echo "[openbao-bootstrap] Ensuring transit engine and keys..."
bao secrets enable transit 2>/dev/null || true
bao write -f transit/keys/tenant-code 2>/dev/null || true
bao read transit/keys/git-credentials >/dev/null 2>&1 || bao write -f transit/keys/git-credentials

echo "[openbao-bootstrap] Writing policies..."
cat <<'EOF' | bao policy write app-server-policy -
# Can mint artifact DEKs (tenant-code) and credential DEKs (git-credentials).
# Can decrypt ONLY credential DEKs, never artifact DEKs (FR-G7).
path "transit/datakey/plaintext/tenant-code" {
  capabilities = ["update"]
}
path "transit/datakey/plaintext/git-credentials" {
  capabilities = ["update"]
}
path "transit/decrypt/git-credentials" {
  capabilities = ["update"]
}
EOF

cat <<'EOF' | bao policy write worker-policy -
# Can unwrap artifact DEKs at execution time, but not mint keys.
path "transit/decrypt/tenant-code" {
  capabilities = ["update"]
}
EOF

echo "[openbao-bootstrap] Issuing scoped tokens..."
bao token create -policy=app-server-policy -field=token -orphan -ttl=768h \
  > /secrets/openbao_app_server_token.txt
bao token create -policy=worker-policy -field=token -orphan -ttl=768h \
  > /secrets/openbao_worker_token.txt
chmod 600 /secrets/openbao_*token.txt
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

echo "[openbao-bootstrap] Done. Root token + unseal keys are in ./secrets."
