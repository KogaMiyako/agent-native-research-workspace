#!/usr/bin/env bash

set -euo pipefail


# ----------------------------------------------------------------------
# Workspace interface provided by runner/run.py
# ----------------------------------------------------------------------

: "${WORKSPACE_ROOT:?WORKSPACE_ROOT is not set}"
: "${REPO_ROOT:?REPO_ROOT is not set}"
: "${EXPERIMENT_ID:?EXPERIMENT_ID is not set}"
: "${RUN_ID:?RUN_ID is not set}"
: "${RUN_NAME:?RUN_NAME is not set}"
: "${RUN_DIR:?RUN_DIR is not set}"
: "${RUN_OUTPUT_DIR:?RUN_OUTPUT_DIR is not set}"
: "${RUN_CONFIG_DIR:?RUN_CONFIG_DIR is not set}"


# ----------------------------------------------------------------------
# Repository adapter
#
# Adapt this section when integrating a new repository.
#
# Responsibilities:
#   1. Enter the correct repository directory.
#   2. Prepare the repository execution environment if necessary.
#   3. Translate Experiment arguments into the repository's native CLI.
#   4. Ensure persistent outputs are written or collected under
#      RUN_OUTPUT_DIR.
#   5. Read registered config snapshots from RUN_CONFIG_DIR when configs are
#      required, and save any final resolved config there as well.
#
# Do not place Experiment-specific loops or research logic here.
# ----------------------------------------------------------------------

cd "$REPO_ROOT"


# Example structure only:
#
# exec python train.py \
#     --output_dir "$RUN_OUTPUT_DIR" \
#     "$@"


# Replace this command with the repository's real entry point.
echo "adapter.sh has not yet been configured for this repository." >&2
exit 1
