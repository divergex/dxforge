#!/bin/bash
SCRIPT_PATH="$(readlink -f "$0")"

SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
TARGET_DIR="$(dirname "$SCRIPT_DIR")"

echo "Removing SELinux context rules for parent directory"
echo "Target directory: $TARGET_DIR"

sudo semanage fcontext -d "${TARGET_DIR}/.*\.sh"
sudo semanage fcontext -d "${TARGET_DIR}/log(/.*)?"

sudo restorecon -Rv "${TARGET_DIR}"

echo "SELinux context rules removed for $TARGET_DIR"
