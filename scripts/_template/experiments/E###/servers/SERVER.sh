#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_SCRIPT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_SCRIPT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

EXPERIMENT_ID="$(basename "$EXPERIMENT_SCRIPT_DIR")"
RUNNER="$REPO_SCRIPT_DIR/runner/run.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Agent 根据派发前检查到的资源填写 GPU 队列。
# 格式为 "<gpu>:<run> <run> ..."；同一 GPU 内顺序执行，不同 GPU 并行。
GPU_QUEUES=(
    # "0:R001 R004"
    # "1:R002 R005"
)

run_one() {
    local run_id="$1"

    echo "[START] $run_id"
    if "$PYTHON_BIN" "$RUNNER" execute --experiment "$EXPERIMENT_ID" --run-id "$run_id"; then
        echo "[DONE] $run_id"
    else
        echo "[FAILED] $run_id" >&2
    fi
}

gpu_worker() {
    local gpu="$1"
    shift

    export CUDA_VISIBLE_DEVICES="$gpu"

    local run_id
    for run_id in "$@"; do
        run_one "$run_id"
    done
}

validate_queues() {
    if (( ${#GPU_QUEUES[@]} == 0 )); then
        echo "尚未为本服务器配置 GPU Run 队列。" >&2
        return 1
    fi

    declare -A seen_gpus=()
    declare -A seen_runs=()
    local entry gpu run_text run_id
    local runs=()
    for entry in "${GPU_QUEUES[@]}"; do
        if [[ "$entry" != *:* ]]; then
            echo "无效 GPU 队列：$entry" >&2
            return 1
        fi
        gpu="${entry%%:*}"
        run_text="${entry#*:}"
        if [[ ! "$gpu" =~ ^[0-9]+$ ]] || [[ -n "${seen_gpus[$gpu]:-}" ]]; then
            echo "GPU 编号无效或重复：$gpu" >&2
            return 1
        fi
        seen_gpus[$gpu]=1
        read -r -a runs <<< "$run_text"
        if (( ${#runs[@]} == 0 )); then
            echo "GPU $gpu 没有分配 Run。" >&2
            return 1
        fi
        for run_id in "${runs[@]}"; do
            if [[ ! "$run_id" =~ ^R[0-9]{3}$ ]] || [[ -n "${seen_runs[$run_id]:-}" ]]; then
                echo "Run ID 无效或重复：$run_id" >&2
                return 1
            fi
            seen_runs[$run_id]=1
        done
    done
}

list_runs() {
    validate_queues || return 1
    local entry run_text run_id
    local runs=()
    for entry in "${GPU_QUEUES[@]}"; do
        run_text="${entry#*:}"
        read -r -a runs <<< "$run_text"
        for run_id in "${runs[@]}"; do
            printf '%s\n' "$run_id"
        done
    done
}

main() {
    if [[ "${1:-}" == "--list-runs" ]]; then
        list_runs
        return
    fi

    validate_queues || return 1
    local entry gpu run_text
    local runs=()
    for entry in "${GPU_QUEUES[@]}"; do
        gpu="${entry%%:*}"
        run_text="${entry#*:}"
        read -r -a runs <<< "$run_text"
        gpu_worker "$gpu" "${runs[@]}" &
    done
    wait
}

main "$@"
