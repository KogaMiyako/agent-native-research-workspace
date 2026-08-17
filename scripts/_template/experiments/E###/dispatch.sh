#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
REPO_SCRIPT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

REMOTE="$WORKSPACE_ROOT/scripts/remote/remote.py"
RUNNER="$REPO_SCRIPT_DIR/runner/run.py"
REPO_NAME="$(basename "$REPO_SCRIPT_DIR")"
EXPERIMENT_ID="$(basename "$SCRIPT_DIR")"

# Agent 在检查资源后填写这两个等长数组。Run 分配只写在服务器脚本的 GPU_QUEUES 中。
SERVERS=(
    # "server-a"
)

SERVER_SCRIPTS=(
    # "server-a.sh"
)

# 工作区相对路径；远程检查时确认这些数据集入口存在。
DATASETS=(
    # "datasets/<dataset>/data"
)

validate_layout() {
    if (( ${#SERVERS[@]} == 0 )); then
        echo "尚未配置服务器分配。" >&2
        return 1
    fi

    if (( ${#SERVERS[@]} != ${#SERVER_SCRIPTS[@]} )); then
        echo "SERVERS 和 SERVER_SCRIPTS 长度必须一致。" >&2
        return 1
    fi

    declare -A seen_servers=()
    declare -A seen_scripts=()
    local index server script run_output
    for index in "${!SERVERS[@]}"; do
        server="${SERVERS[$index]}"
        script="$SCRIPT_DIR/servers/${SERVER_SCRIPTS[$index]}"
        if [[ -n "${seen_servers[$server]:-}" ]]; then
            echo "服务器重复：$server" >&2
            return 1
        fi
        if [[ -n "${seen_scripts[$script]:-}" ]]; then
            echo "服务器脚本重复：$script" >&2
            return 1
        fi
        if [[ ! -f "$script" ]]; then
            echo "服务器脚本不存在：$script" >&2
            return 1
        fi
        seen_servers[$server]=1
        seen_scripts[$script]=1
        if ! run_output="$(bash "$script" --list-runs)"; then
            echo "无法读取服务器脚本中的 Run：$script" >&2
            return 1
        fi
        if [[ -z "$run_output" ]]; then
            echo "服务器脚本没有分配 Run：$script" >&2
            return 1
        fi
    done
}

validate_assignment() {
    validate_layout
    local index run_id
    local all_runs=()
    for index in "${!SERVERS[@]}"; do
        while IFS= read -r run_id; do
            all_runs+=(--run "$run_id")
        done < <(runs_for_index "$index")
    done
    python3 "$RUNNER" validate-assignment \
        --experiment "$EXPERIMENT_ID" \
        "${all_runs[@]}"
}

runs_for_index() {
    local index="$1"
    bash "$SCRIPT_DIR/servers/${SERVER_SCRIPTS[$index]}" --list-runs
}

main() {
    validate_assignment

    local dataset_args=()
    local dataset
    for dataset in "${DATASETS[@]}"; do
        dataset_args+=(--dataset "$dataset")
    done

    local index
    for index in "${!SERVERS[@]}"; do
        check_command=(
            python3 "$REMOTE" check
            --server "${SERVERS[$index]}"
            --repo "$REPO_NAME"
            --experiment "$EXPERIMENT_ID"
        )
        check_command+=("${dataset_args[@]}")
        "${check_command[@]}"
    done

    local runs
    local run_args
    for index in "${!SERVERS[@]}"; do
        mapfile -t runs < <(runs_for_index "$index")
        run_args=()
        local run_id
        for run_id in "${runs[@]}"; do
            run_args+=(--run "$run_id")
        done

        prepare_command=(
            python3 "$REMOTE" prepare
            --server "${SERVERS[$index]}"
            --repo "$REPO_NAME"
            --experiment "$EXPERIMENT_ID"
            --script "$SCRIPT_DIR/servers/${SERVER_SCRIPTS[$index]}"
        )
        prepare_command+=("${run_args[@]}")
        "${prepare_command[@]}"

        python3 "$REMOTE" launch --server "${SERVERS[$index]}" --repo "$REPO_NAME" --experiment "$EXPERIMENT_ID" --script-name "${SERVER_SCRIPTS[$index]}"
    done
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
