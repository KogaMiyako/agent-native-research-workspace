#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dispatch.sh"

validate_layout

for index in "${!SERVERS[@]}"; do
    mapfile -t runs < <(runs_for_index "$index")
    run_args=()
    for run_id in "${runs[@]}"; do
        run_args+=(--run "$run_id")
    done

    collect_command=(
        python3 "$REMOTE" collect
        --server "${SERVERS[$index]}"
        --repo "$REPO_NAME"
        --experiment "$EXPERIMENT_ID"
    )
    collect_command+=("${run_args[@]}")
    "${collect_command[@]}"
done
