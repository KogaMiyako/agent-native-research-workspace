#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_SCRIPT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNNER="$REPO_SCRIPT_DIR/runner/run.py"
REPO_NAME="$(basename "$REPO_SCRIPT_DIR")"
EXPERIMENT_ID="$(basename "$SCRIPT_DIR")"
ADAPTER="scripts/$REPO_NAME/runner/adapter.sh"

CONFIGS=(
    # "repos/<repo>/configs/<config>"
)

config_args=()
for config in "${CONFIGS[@]}"; do
    config_args+=(--config "$config")
done

register_run() {
    local run_id="$1"
    local name="$2"
    local gpus="$3"
    local min_gpu_memory_mb="$4"
    shift 4

    local command=(
        python3 "$RUNNER" register
        --experiment "$EXPERIMENT_ID"
        --run-id "$run_id"
        --name "$name"
        --gpus "$gpus"
        --min-gpu-memory-mb "$min_gpu_memory_mb"
    )
    command+=("${config_args[@]}" -- "$ADAPTER" "$@")
    "${command[@]}"
}

# 为每个具体条件注册一个 Run。Run ID 必须在派发前固定。
#
# register_run R001 "dataset-a-seed1" 1 20000 --dataset dataset-a --seed 1
#
# register_run R002 "dataset-a-seed2" 1 20000 --dataset dataset-a --seed 2

echo "尚未为 $EXPERIMENT_ID 配置 Run。" >&2
exit 1
