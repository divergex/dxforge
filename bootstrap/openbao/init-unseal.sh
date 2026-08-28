#!/bin/sh
#   unseals using keys already on disk.
set -e

export BAO_ADDR="http://openbao:8200"

apk add --no-cache jq curl >/dev/null 2>&1 || true

echo "[openbao-bootstrap] Waiting for OpenBao API..."
until curl -s "$BAO_ADDR/v1/sys/health" >/dev/null 2>&1; do
  sleep 2
done

# this container runs as root.
chown -R "${APP_UID:-1000}:${APP_GID:-1000}" /secrets 2>/dev/null || true

if [ -f /secrets/openbao_root_token.txt ]; then
  echo "[openbao-bootstrap] existing init found, so unsealing only."
  for i in 1 2 3; do
    bao operator unseal "$(cat /secrets/openbao_unseal_key_${i}.txt)"
  done
  echo "[openbao-bootstrap] unsealed. Nothing else to do."
  exit 0
fi

echo "[openbao-bootstrap] First run! initializing OpenBao..."
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

export BAO_TOKEN
BAO_TOKEN=$(cat /secrets/openbao_root_token.txt)

echo "[openbao-bootstrap] Enabling transit engine..."
bao secrets enable transit
bao write -f transit/keys/tenant-code

echo "[openbao-bootstrap] Writing policies..."
cat <<'EOF' | bao policy write app-server-policy -
# Can request new data keys to encrypt job code & cannot decrypt.
path "transit/datakey/plaintext/tenant-code" {
  capabilities = ["update"]
}
EOF

cat <<'EOF' | bao policy write worker-policy -
# Can unwrap a job's DEK at execution time, but not mint new keys.
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

echo "[openbao-bootstrap] Done."
echo "[openbao-bootstrap] Root token + unseal keys are in ./secrets."
echo "[openbao-bootstrap] Back them up somewhere safe."
