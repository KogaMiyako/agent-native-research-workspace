#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dispatch.sh"

validate_layout

for server in "${SERVERS[@]}"; do
    echo
    echo "===== $server ====="
    python3 "$REMOTE" query --server "$server" --repo "$REPO_NAME" --experiment "$EXPERIMENT_ID"
done
