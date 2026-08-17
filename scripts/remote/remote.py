#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


CHECK_SCRIPT = r"""
set -eu

workspace="$1"
repo="$2"
expected_commit="$3"
python_executable="$4"
shift 4

test -d "$workspace"
test -d "$workspace/repos/$repo"

actual_commit="$(git -C "$workspace/repos/$repo" rev-parse HEAD)"
expected_commit="$(git -C "$workspace/repos/$repo" rev-parse "$expected_commit")"
test "$actual_commit" = "$expected_commit"
test -z "$(git -C "$workspace/repos/$repo" status --porcelain)"

for dataset_path in "$@"; do
    test -e "$workspace/$dataset_path"
done

"$python_executable" --version
df -h "$workspace"

if command -v nvidia-smi >/dev/null 2>&1 \
    && nvidia-smi --query-gpu=index,name,memory.total,memory.free,utilization.gpu --format=csv,noheader,nounits; then
    :
else
    printf '%s\n' 'nvidia-smi unavailable; checking CUDA through PyTorch.' >&2
    "$python_executable" - <<'PY'
try:
    import torch
except Exception as exc:
    raise SystemExit(f"Cannot import PyTorch for CUDA fallback check: {exc}")

if not torch.cuda.is_available():
    raise SystemExit("Neither nvidia-smi nor PyTorch reports usable CUDA devices.")

device_count = torch.cuda.device_count()
if device_count <= 0:
    raise SystemExit("PyTorch reports CUDA available but exposes no CUDA devices.")

for index in range(device_count):
    properties = torch.cuda.get_device_properties(index)
    total_mb = properties.total_memory // (1024 * 1024)
    try:
        with torch.cuda.device(index):
            free_bytes, _ = torch.cuda.mem_get_info()
        free_mb = free_bytes // (1024 * 1024)
        free_text = f", free_memory_mb={free_mb}"
    except Exception:
        free_text = ", free_memory_mb=unknown"
    print(
        f"{index}, {properties.name}, total_memory_mb={total_mb}{free_text}, "
        "source=torch"
    )
PY
fi
"""


MKDIR_SCRIPT = r"""
set -eu
for path in "$@"; do
    mkdir -p "$path"
done
"""


LAUNCH_SCRIPT = r"""
set -eu
script="$1"
python_executable="$2"
expected_sha256="$3"
actual_sha256="$(sha256sum "$script" | awk '{print $1}')"
test "$actual_sha256" = "$expected_sha256"
bash -n "$script"
nohup env PYTHON_BIN="$python_executable" bash "$script" >/dev/null 2>&1 </dev/null &
pid="$!"
sleep 1
state="$(ps -o stat= -p "$pid" 2>/dev/null || true)"
if test -z "$state" || printf '%s' "$state" | grep -q '^Z'; then
    set +e
    wait "$pid"
    code="$?"
    set -e
    if test "$code" -ne 0; then
        printf 'server script exited during launch with code %s\n' "$code" >&2
        exit "$code"
    fi
fi
printf '%s\n' "$pid"
"""


READ_RUN_SCRIPT = r"""
set -eu
run_dir="$1"
if test -f "$run_dir/run.json"; then
    cat "$run_dir/run.json"
fi
"""


def workspace_root():
    return Path(__file__).resolve().parents[2]


def default_config_path():
    return Path(__file__).resolve().parent / "servers.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simple SSH helpers for Experiment execution."
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Server configuration JSON.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--server", action="append", default=[])
    check.add_argument("--repo", required=True)
    check.add_argument("--experiment", required=True)
    check.add_argument("--dataset", action="append", default=[])

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--server", required=True)
    prepare.add_argument("--repo", required=True)
    prepare.add_argument("--experiment", required=True)
    prepare.add_argument("--script", required=True)
    prepare.add_argument("--run", action="append", default=[], required=True)

    launch = subparsers.add_parser("launch")
    launch.add_argument("--server", required=True)
    launch.add_argument("--repo", required=True)
    launch.add_argument("--experiment", required=True)
    launch.add_argument("--script-name", required=True)

    query = subparsers.add_parser("query")
    query.add_argument("--server", required=True)
    query.add_argument("--repo", required=True)
    query.add_argument("--experiment", required=True)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--server", required=True)
    collect.add_argument("--repo", required=True)
    collect.add_argument("--experiment", required=True)
    collect.add_argument("--run", action="append", default=[], required=True)

    mark_failed = subparsers.add_parser("mark-failed")
    mark_failed.add_argument("--server", required=True)
    mark_failed.add_argument("--repo", required=True)
    mark_failed.add_argument("--experiment", required=True)
    mark_failed.add_argument("--run", required=True)
    mark_failed.add_argument("--reason", required=True)

    return parser.parse_args()


def load_servers(config_path):
    path = Path(config_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load server configuration {path}: {exc}") from exc

    entries = data.get("servers")
    if not isinstance(entries, list):
        raise RuntimeError(f"{path} must contain a 'servers' list.")

    servers = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("Each server entry must be a JSON object.")
        name = entry.get("name")
        ssh_target = entry.get("ssh")
        remote_workspace = entry.get("workspace")
        if not name or not ssh_target or not remote_workspace:
            raise RuntimeError(
                "Each server requires non-empty name, ssh, and workspace fields."
            )
        if name in servers:
            raise RuntimeError(f"Duplicate server name: {name}")
        servers[name] = {
            **entry,
            "python": entry.get("python", "python3"),
        }
    return servers


def select_server(servers, name):
    try:
        return servers[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown server {name!r}.") from exc


def read_expected_commit(repo, experiment):
    path = (
        workspace_root()
        / "experiments"
        / repo
        / experiment
        / "EXPERIMENT.md"
    )
    if not path.exists():
        raise RuntimeError(f"Experiment document not found: {path}")
    text = path.read_text(encoding="utf-8")
    pattern = r"\*\*Git\s*(?:commit|提交)\s*[:：]\*\*\s*`([^`]+)`"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Git commit is missing from {path}.")
    commit = match.group(1).strip()
    if not commit or "<" in commit or ">" in commit:
        raise RuntimeError(f"Git commit has not been filled in: {path}")
    return commit


def ssh_script(server, script, arguments, capture=False):
    remote_command = shlex.join(["bash", "-s", "--", *map(str, arguments)])
    result = subprocess.run(
        ["ssh", server["ssh"], remote_command],
        input=script,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if result.returncode != 0:
        detail = ""
        if capture:
            detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"SSH command failed on {server['name']}"
            + (f": {detail}" if detail else "")
        )
    return result.stdout.strip() if capture else ""


def run_command(command):
    result = subprocess.run(command)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{shlex.join(map(str, command))}"
        )


def remote_path(server, *parts):
    return str(PurePosixPath(server["workspace"], *parts))


def find_run_dir(repo, experiment, run_id):
    root = workspace_root() / "runs" / repo / experiment
    matches = [path for path in root.glob(f"{run_id}-*") if path.is_dir()]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one registered directory for {run_id} under {root}."
        )
    return matches[0]


def read_json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path}: {exc}") from exc


def write_json_file(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")
    temporary.replace(path)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def immutable_run_definition(metadata):
    return {
        "run_id": metadata.get("run_id"),
        "run_name": metadata.get("run_name"),
        "experiment": metadata.get("experiment"),
        "git_commit": metadata.get("git_commit"),
        "command_argv": metadata.get("command_argv"),
        "config_sources": metadata.get("config_sources", []),
        "config_snapshots": metadata.get("config_snapshots", []),
        "runner_snapshot": metadata.get("runner_snapshot"),
        "dispatch_snapshot": metadata.get("dispatch_snapshot"),
        "resources_requested": metadata.get("resources_requested", {}),
    }


def rsync_to_server(source, server, destination):
    run_command(
        [
            "rsync",
            "-a",
            f"{str(source).rstrip('/')}/",
            f"{server['ssh']}:{str(destination).rstrip('/')}/",
        ]
    )


def rsync_to_server_exact(source, server, destination):
    run_command(
        [
            "rsync",
            "-a",
            "--delete",
            f"{str(source).rstrip('/')}/",
            f"{server['ssh']}:{str(destination).rstrip('/')}/",
        ]
    )


def rsync_file_to_server(source, server, destination):
    run_command(["rsync", "-a", str(source), f"{server['ssh']}:{destination}"])


def rsync_from_server(server, source, destination):
    Path(destination).mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "rsync",
            "-a",
            "--partial",
            f"{server['ssh']}:{str(source).rstrip('/')}/",
            f"{str(destination).rstrip('/')}/",
        ]
    )


def action_check(args, servers):
    names = args.server or list(servers)
    if not names:
        raise RuntimeError("No servers are configured.")
    expected_commit = read_expected_commit(args.repo, args.experiment)

    failed = []
    for name in names:
        server = select_server(servers, name)
        print(f"\n=== {name} ({server['ssh']}) ===", flush=True)
        try:
            ssh_script(
                server,
                CHECK_SCRIPT,
                [
                    server["workspace"],
                    args.repo,
                    expected_commit,
                    server["python"],
                    *args.dataset,
                ],
            )
        except RuntimeError as exc:
            failed.append(name)
            print(f"CHECK FAILED: {exc}", file=sys.stderr)
    if failed:
        raise RuntimeError(f"Server checks failed: {', '.join(failed)}")


def action_prepare(args, servers):
    server = select_server(servers, args.server)
    root = workspace_root()
    server_script = Path(args.script).resolve()
    if not server_script.is_file():
        raise RuntimeError(f"Server execution script not found: {server_script}")
    dispatch_snapshot = {
        "server": args.server,
        "script": server_script.name,
        "snapshot": f"config/_execution/server/{server_script.name}",
        "sha256": file_sha256(server_script),
    }

    remote_runner = remote_path(server, "scripts", args.repo, "runner")
    remote_experiment_doc = remote_path(
        server, "experiments", args.repo, args.experiment
    )
    remote_server_scripts = remote_path(
        server,
        "scripts",
        args.repo,
        "experiments",
        args.experiment,
        "servers",
    )
    remote_runs = remote_path(server, "runs", args.repo, args.experiment)

    ssh_script(
        server,
        MKDIR_SCRIPT,
        [
            remote_runner,
            remote_experiment_doc,
            remote_server_scripts,
            remote_runs,
        ],
    )

    rsync_to_server_exact(
        root / "scripts" / args.repo / "runner", server, remote_runner
    )
    rsync_file_to_server(
        root / "experiments" / args.repo / args.experiment / "EXPERIMENT.md",
        server,
        f"{remote_experiment_doc}/EXPERIMENT.md",
    )
    rsync_file_to_server(
        server_script,
        server,
        f"{remote_server_scripts}/{server_script.name}",
    )

    for run_id in args.run:
        run_dir = find_run_dir(args.repo, args.experiment, run_id)
        local_metadata = read_json_file(run_dir / "run.json")
        if local_metadata.get("status") != "pending":
            raise RuntimeError(
                f"Cannot dispatch {run_dir.name} from local status "
                f"{local_metadata.get('status')!r}; expected 'pending'."
            )
        existing_dispatch = local_metadata.get("dispatch_snapshot")
        if existing_dispatch is not None and existing_dispatch != dispatch_snapshot:
            raise RuntimeError(
                f"Dispatch definition changed for {run_dir.name}. "
                "Register a new Run instead of replacing its server script."
            )
        stored_script = run_dir / dispatch_snapshot["snapshot"]
        stored_script.parent.mkdir(parents=True, exist_ok=True)
        if stored_script.exists():
            if file_sha256(stored_script) != dispatch_snapshot["sha256"]:
                raise RuntimeError(
                    f"Stored server-script snapshot differs for {run_dir.name}."
                )
        else:
            shutil.copy2(server_script, stored_script)
        if file_sha256(stored_script) != dispatch_snapshot["sha256"]:
            raise RuntimeError(
                f"Server script changed while snapshotting {run_dir.name}."
            )
        local_metadata["dispatch_snapshot"] = dispatch_snapshot
        write_json_file(run_dir / "run.json", local_metadata)

        remote_run = f"{remote_runs}/{run_dir.name}"
        remote_text = ssh_script(
            server,
            READ_RUN_SCRIPT,
            [remote_run],
            capture=True,
        )
        if remote_text:
            try:
                remote_metadata = json.loads(remote_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Remote run.json is invalid for {args.server}:{run_dir.name}."
                ) from exc
            if immutable_run_definition(remote_metadata) != immutable_run_definition(
                local_metadata
            ):
                raise RuntimeError(
                    f"Remote Run definition differs for "
                    f"{args.server}:{run_dir.name}."
                )
            print(
                f"[REMOTE EXISTS] {args.server}: {run_dir.name} "
                f"status={remote_metadata.get('status', 'unknown')}"
            )
            continue

        rsync_to_server(run_dir, server, remote_run)

    print(f"[PREPARED] {args.server}: {', '.join(args.run)}")


def action_launch(args, servers):
    server = select_server(servers, args.server)
    script = remote_path(
        server,
        "scripts",
        args.repo,
        "experiments",
        args.experiment,
        "servers",
        args.script_name,
    )
    local_script = (
        workspace_root()
        / "scripts"
        / args.repo
        / "experiments"
        / args.experiment
        / "servers"
        / args.script_name
    )
    if not local_script.is_file():
        raise RuntimeError(f"Local server execution script not found: {local_script}")
    script_sha256 = file_sha256(local_script)
    pid = ssh_script(
        server,
        LAUNCH_SCRIPT,
        [script, server["python"], script_sha256],
        capture=True,
    )
    print(f"[LAUNCHED] {args.server} pid={pid} script={args.script_name}")


def action_query(args, servers):
    server = select_server(servers, args.server)
    status_script = remote_path(server, "scripts", args.repo, "runner", "status.py")
    command = shlex.join([server["python"], status_script, args.experiment])
    result = subprocess.run(["ssh", server["ssh"], command])
    if result.returncode != 0:
        raise RuntimeError(f"Status query failed on {args.server}.")


def action_collect(args, servers):
    server = select_server(servers, args.server)
    for run_id in args.run:
        local_run = find_run_dir(args.repo, args.experiment, run_id)
        remote_run = remote_path(
            server,
            "runs",
            args.repo,
            args.experiment,
            local_run.name,
        )
        rsync_from_server(server, remote_run, local_run)
        print(f"[COLLECTED] {args.server}: {local_run.name}")


def action_mark_failed(args, servers):
    server = select_server(servers, args.server)
    runner = remote_path(server, "scripts", args.repo, "runner", "run.py")
    command = shlex.join(
        [
            server["python"],
            runner,
            "mark-failed",
            "--experiment",
            args.experiment,
            "--run-id",
            args.run,
            "--reason",
            args.reason,
        ]
    )
    result = subprocess.run(["ssh", server["ssh"], command])
    if result.returncode != 0:
        raise RuntimeError(f"Could not mark {args.run} failed on {args.server}.")


def main():
    args = parse_args()
    servers = load_servers(args.config)
    actions = {
        "check": action_check,
        "prepare": action_prepare,
        "launch": action_launch,
        "query": action_query,
        "collect": action_collect,
        "mark-failed": action_mark_failed,
    }
    actions[args.action](args, servers)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
