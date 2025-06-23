#!/bin/bash
# selinux_allow_parent.sh
SCRIPT_PATH="$(readlink -f "$0")"

SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
TARGET_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting SELinux context for parent directory of script:"
echo "Target directory: $TARGET_DIR"

sudo semanage fcontext -a -t bin_t "${TARGET_DIR}/.*\.sh"
sudo semanage fcontext -a -t var_log_t "${TARGET_DIR}/log(/.*)?"

sudo restorecon -Rv "${TARGET_DIR}"

echo "SELinux contexts updated for $TARGET_DIR"
