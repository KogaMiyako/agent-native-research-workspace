#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


RUN_ID_PATTERN = re.compile(r"R\d{3}")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_command(parser, command):
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("An execution command must be provided after '--'.")
    return command


def parse_args():
    parser = argparse.ArgumentParser(
        description="Register or execute one concrete Run of a research Experiment."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    register = subparsers.add_parser(
        "register",
        help="Create one pending Run without executing it.",
    )
    register.add_argument("--experiment", required=True)
    register.add_argument("--run-id", required=True, help="Explicit ID such as R001.")
    register.add_argument("--name", required=True, help="Short condition name.")
    register.add_argument(
        "--config",
        action="append",
        default=[],
        help="Configuration file or directory to snapshot. May be repeated.",
    )
    register.add_argument(
        "--gpus",
        type=int,
        default=0,
        help="Advisory GPU requirement recorded in run.json.",
    )
    register.add_argument(
        "--min-gpu-memory-mb",
        type=int,
        default=0,
        help="Advisory per-GPU memory requirement recorded in run.json.",
    )
    register.add_argument(
        "--cpus",
        type=int,
        default=0,
        help="Advisory CPU requirement recorded in run.json.",
    )
    register.add_argument(
        "--memory-gb",
        type=int,
        default=0,
        help="Advisory host-memory requirement recorded in run.json.",
    )
    register.add_argument("command", nargs=argparse.REMAINDER)

    execute = subparsers.add_parser(
        "execute",
        help="Execute one previously registered pending Run.",
    )
    execute.add_argument("--experiment", required=True)
    execute.add_argument("--run-id", required=True)

    validate_assignment = subparsers.add_parser(
        "validate-assignment",
        help="Verify that all registered Runs are assigned exactly once.",
    )
    validate_assignment.add_argument("--experiment", required=True)
    validate_assignment.add_argument(
        "--run",
        action="append",
        required=True,
        help="Assigned Run ID. Repeat once per Run.",
    )

    mark_failed = subparsers.add_parser(
        "mark-failed",
        help="Explicitly close a pending or stale running Run as failed.",
    )
    mark_failed.add_argument("--experiment", required=True)
    mark_failed.add_argument("--run-id", required=True)
    mark_failed.add_argument("--reason", required=True)

    args = parser.parse_args()
    if args.action == "register":
        args.command = parse_command(register, args.command)
    return args


def resolve_workspace():
    # scripts/<repo>/runner/run.py
    script_path = Path(__file__).resolve()
    repo_name = script_path.parent.parent.name
    workspace_root = script_path.parents[3]
    repo_root = workspace_root / "repos" / repo_name
    return workspace_root, repo_name, repo_root


def read_expected_commit(experiment_md):
    if not experiment_md.exists():
        raise RuntimeError(f"Experiment document not found: {experiment_md}")

    text = experiment_md.read_text(encoding="utf-8")
    pattern = r"\*\*Git\s*(?:commit|提交)\s*[:：]\*\*\s*`([^`]+)`"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise RuntimeError(
            f"Git commit not found in {experiment_md}. Expected either:\n"
            "- **Git commit:** `abc1234`\n"
            "- **Git 提交：** `abc1234`"
        )

    commit = match.group(1).strip()
    if not commit or "<" in commit or ">" in commit:
        raise RuntimeError(f"Git commit in {experiment_md} has not been filled in.")
    return commit


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def verify_git(repo_root, expected_commit):
    if not repo_root.is_dir():
        raise RuntimeError(f"Repository does not exist: {repo_root}")

    head = git(repo_root, "rev-parse", "HEAD")
    expected = git(repo_root, "rev-parse", expected_commit)
    if head != expected:
        raise RuntimeError(
            "Git commit mismatch.\n"
            f"Experiment expects: {expected}\n"
            f"Repository HEAD:    {head}"
        )

    dirty = git(repo_root, "status", "--porcelain")
    if dirty:
        raise RuntimeError(
            "Repository contains uncommitted changes.\n"
            "Commit or clean the repository before registering or executing a Run."
        )
    return head


def normalize_run_id(raw_run_id):
    run_id = raw_run_id.upper()
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RuntimeError("Run ID must use the form R###, for example R001.")
    return run_id


def safe_condition_name(raw_name):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip("-")
    if not name:
        raise RuntimeError("Run condition name becomes empty after normalization.")
    return name


def normalize_workspace_path(raw_path, workspace_root):
    path = Path(raw_path)
    if not path.is_absolute():
        return raw_path
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()))
    except ValueError:
        return raw_path


def normalize_command(command, workspace_root):
    return [normalize_workspace_path(arg, workspace_root) for arg in command]


def path_digest(path):
    path = Path(path)
    digest = hashlib.sha256()

    def update_file(file_path, relative_name):
        digest.update(b"file\0")
        digest.update(str(relative_name).encode("utf-8"))
        digest.update(b"\0")
        digest.update(oct(file_path.stat().st_mode & 0o777).encode("ascii"))
        digest.update(b"\0")
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

    if path.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode("utf-8"))
    elif path.is_file():
        update_file(path, path.name)
    elif path.is_dir():
        for item in sorted(path.rglob("*"), key=lambda value: value.as_posix()):
            relative = item.relative_to(path)
            if "__pycache__" in relative.parts or item.suffix in {".pyc", ".pyo"}:
                continue
            if item.is_symlink():
                digest.update(b"symlink\0")
                digest.update(relative.as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(os.readlink(item).encode("utf-8"))
            elif item.is_file():
                update_file(item, relative.as_posix())
    else:
        raise RuntimeError(f"Cannot hash missing or unsupported path: {path}")

    return digest.hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_snapshot(workspace_root):
    runner_dir = Path(__file__).resolve().parent
    return {
        "path": normalize_workspace_path(str(runner_dir), workspace_root),
        "snapshot": "config/_execution/runner",
        "sha256": path_digest(runner_dir),
    }


def command_for_execution(command, workspace_root):
    resolved = list(command)
    for index, arg in enumerate(resolved):
        path = Path(arg)
        if path.is_absolute() or "/" not in arg:
            continue
        candidate = workspace_root / path
        if candidate.exists():
            resolved[index] = str(candidate)
    return resolved


def display_command(command):
    return subprocess.list2cmdline(command)


def resolve_config_sources(config_paths, workspace_root):
    sources = []
    destination_names = set()
    for raw_path in config_paths:
        source = Path(raw_path)
        if not source.is_absolute():
            source = workspace_root / source
        source = source.resolve()
        if not source.exists():
            raise RuntimeError(f"Config does not exist: {source}")
        if source.name == "_execution":
            raise RuntimeError(
                "Config name '_execution' is reserved for internal Run snapshots."
            )
        if source.name in destination_names:
            raise RuntimeError(
                f"Multiple config sources use the same name: {source.name}"
            )
        destination_names.add(source.name)
        sources.append(source)
    return sources


def describe_config_sources(sources, workspace_root):
    return [
        {
            "source": normalize_workspace_path(str(source), workspace_root),
            "snapshot": f"config/{source.name}",
            "sha256": path_digest(source),
        }
        for source in sources
    ]


def snapshot_configs(sources, config_dir, descriptions):
    config_dir.mkdir(parents=True, exist_ok=True)
    for source, description in zip(sources, descriptions):
        destination = config_dir / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        if path_digest(destination) != description["sha256"]:
            raise RuntimeError(f"Config snapshot changed while copying: {source}")


def snapshot_runner(recorded_runner, config_dir, workspace_root):
    source = resolve_recorded_path(recorded_runner["path"], workspace_root)
    destination = config_dir.parent / recorded_runner["snapshot"]
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    if path_digest(destination) != recorded_runner["sha256"]:
        raise RuntimeError("Runner snapshot changed while copying.")


def resolve_recorded_path(raw_path, workspace_root):
    path = Path(raw_path)
    return path if path.is_absolute() else workspace_root / path


def verify_execution_snapshot(metadata, workspace_root, run_dir):
    recorded_runner = metadata.get("runner_snapshot")
    if not isinstance(recorded_runner, dict):
        raise RuntimeError("runner_snapshot is missing from run.json.")
    runner_path = resolve_recorded_path(recorded_runner.get("path", ""), workspace_root)
    if path_digest(runner_path) != recorded_runner.get("sha256"):
        raise RuntimeError(
            "Runner or adapter changed after Run registration. "
            "Register a new Run with the current execution interface."
        )
    stored_runner = run_dir / recorded_runner.get("snapshot", "")
    if path_digest(stored_runner) != recorded_runner.get("sha256"):
        raise RuntimeError(f"Stored runner snapshot has changed: {stored_runner}")

    recorded_dispatch = metadata.get("dispatch_snapshot")
    if recorded_dispatch is not None:
        if not isinstance(recorded_dispatch, dict):
            raise RuntimeError("dispatch_snapshot must be an object or null.")
        stored_dispatch = run_dir / recorded_dispatch.get("snapshot", "")
        if file_sha256(stored_dispatch) != recorded_dispatch.get("sha256"):
            raise RuntimeError(
                f"Stored server-script snapshot has changed: {stored_dispatch}"
            )

    snapshots = metadata.get("config_snapshots", [])
    if not isinstance(snapshots, list):
        raise RuntimeError("config_snapshots must be a list in run.json.")
    for snapshot in snapshots:
        source = resolve_recorded_path(snapshot.get("source", ""), workspace_root)
        stored = run_dir / snapshot.get("snapshot", "")
        expected = snapshot.get("sha256")
        if path_digest(stored) != expected:
            raise RuntimeError(f"Stored config snapshot has changed: {stored}")
        if path_digest(source) != expected:
            raise RuntimeError(
                f"Config source changed after Run registration: {source}. "
                "Register a new Run or restore the recorded config."
            )


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")
    tmp.replace(path)


def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path}: {exc}") from exc


def find_registered_run(experiment_run_dir, run_id):
    if not experiment_run_dir.exists():
        return None
    matches = [
        path
        for path in experiment_run_dir.iterdir()
        if path.is_dir() and path.name.startswith(f"{run_id}-")
    ]
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple directories use {run_id} under {experiment_run_dir}."
        )
    return matches[0] if matches else None


def experiment_paths(workspace_root, repo_name, experiment):
    experiment_dir = workspace_root / "experiments" / repo_name / experiment
    experiment_md = experiment_dir / "EXPERIMENT.md"
    experiment_run_dir = workspace_root / "runs" / repo_name / experiment
    return experiment_md, experiment_run_dir


def immutable_definition(metadata):
    return {
        "run_id": metadata.get("run_id"),
        "run_name": metadata.get("run_name"),
        "experiment": metadata.get("experiment"),
        "git_commit": metadata.get("git_commit"),
        "command_argv": metadata.get("command_argv"),
        "config_sources": metadata.get("config_sources", []),
        "config_snapshots": metadata.get("config_snapshots", []),
        "runner_snapshot": metadata.get("runner_snapshot"),
        "resources_requested": metadata.get("resources_requested", {}),
    }


def register_run(args, workspace_root, repo_name, repo_root):
    run_id = normalize_run_id(args.run_id)
    condition = safe_condition_name(args.name)
    run_name = f"{run_id}-{condition}"
    resource_values = {
        "gpus": args.gpus,
        "min_gpu_memory_mb": args.min_gpu_memory_mb,
        "cpus": args.cpus,
        "memory_gb": args.memory_gb,
    }
    invalid_resources = [
        name for name, value in resource_values.items() if value < 0
    ]
    if invalid_resources:
        raise RuntimeError(
            "Resource requests cannot be negative: "
            + ", ".join(invalid_resources)
        )
    experiment_md, experiment_run_dir = experiment_paths(
        workspace_root, repo_name, args.experiment
    )

    expected_commit = read_expected_commit(experiment_md)
    actual_commit = verify_git(repo_root, expected_commit)
    config_sources = resolve_config_sources(args.config, workspace_root)
    config_snapshots = describe_config_sources(config_sources, workspace_root)
    command_argv = normalize_command(args.command, workspace_root)

    metadata = {
        "schema_version": 2,
        "run_id": run_id,
        "run_name": run_name,
        "experiment": args.experiment,
        "git_commit": actual_commit,
        "status": "pending",
        "command": display_command(command_argv),
        "command_argv": command_argv,
        "config_sources": [
            normalize_workspace_path(str(path), workspace_root)
            for path in config_sources
        ],
        "config_snapshots": config_snapshots,
        "runner_snapshot": runner_snapshot(workspace_root),
        "dispatch_snapshot": None,
        "resources_requested": resource_values,
        "host": "",
        "device": "",
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "failure_reason": None,
        "reconciled_at": None,
    }

    existing = find_registered_run(experiment_run_dir, run_id)
    if existing is not None:
        existing_metadata = read_json(existing / "run.json")
        if existing.name != run_name:
            raise RuntimeError(
                f"{run_id} is already registered as {existing.name}, not {run_name}."
            )
        if immutable_definition(existing_metadata) != immutable_definition(metadata):
            raise RuntimeError(
                f"{existing} already exists with a different Run definition."
            )
        print(f"[REGISTERED] {args.experiment}/{existing.name}")
        return 0

    experiment_run_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{run_name}.registering-",
            dir=experiment_run_dir,
        )
    )
    try:
        snapshot_configs(config_sources, temp_dir / "config", config_snapshots)
        snapshot_runner(metadata["runner_snapshot"], temp_dir / "config", workspace_root)
        (temp_dir / "output").mkdir()
        write_json(temp_dir / "run.json", metadata)
        temp_dir.replace(experiment_run_dir / run_name)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    print(f"[PENDING] {args.experiment}/{run_name}")
    return 0


class ExecutionInterrupted(Exception):
    def __init__(self, signum):
        super().__init__(f"Interrupted by signal {signum}")
        self.signum = signum


def execute_run(args, workspace_root, repo_name, repo_root):
    run_id = normalize_run_id(args.run_id)
    _, experiment_run_dir = experiment_paths(
        workspace_root, repo_name, args.experiment
    )
    run_dir = find_registered_run(experiment_run_dir, run_id)
    if run_dir is None:
        raise RuntimeError(
            f"{run_id} is not registered under {experiment_run_dir}. "
            "Run the Experiment register.sh first."
        )

    run_json_path = run_dir / "run.json"
    metadata = read_json(run_json_path)
    if metadata.get("experiment") != args.experiment:
        raise RuntimeError(f"Experiment mismatch in {run_json_path}.")
    if metadata.get("status") != "pending":
        raise RuntimeError(
            f"{run_dir.name} cannot execute from status "
            f"{metadata.get('status')!r}; expected 'pending'."
        )

    verify_execution_snapshot(metadata, workspace_root, run_dir)
    actual_commit = verify_git(repo_root, metadata.get("git_commit", ""))
    command_argv = metadata.get("command_argv")
    if not isinstance(command_argv, list) or not command_argv:
        raise RuntimeError(f"Registered command_argv is missing in {run_json_path}.")
    command_argv = command_for_execution(command_argv, workspace_root)

    config_dir = run_dir / "config"
    output_dir = run_dir / "output"
    config_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"

    device = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    metadata.update(
        {
            "git_commit": actual_commit,
            "status": "running",
            "host": socket.gethostname(),
            "device": device,
            "started_at": now(),
            "finished_at": None,
            "exit_code": None,
            "failure_reason": None,
            "reconciled_at": None,
        }
    )
    write_json(run_json_path, metadata)

    env = os.environ.copy()
    env.update(
        {
            "WORKSPACE_ROOT": str(workspace_root),
            "REPO_ROOT": str(repo_root),
            "EXPERIMENT_ID": args.experiment,
            "RUN_ID": metadata["run_id"],
            "RUN_NAME": run_dir.name,
            "RUN_DIR": str(run_dir),
            "RUN_OUTPUT_DIR": str(output_dir),
            "RUN_CONFIG_DIR": str(config_dir),
        }
    )

    print(f"[Run] {args.experiment}/{run_dir.name}")
    print(f"[Repo] {repo_name}")
    print(f"[Git] {actual_commit}")
    print(f"[Device] {device or '-'}")
    print(f"[Output] {run_dir}")
    print(f"[Command] {display_command(command_argv)}")

    process = None
    old_handlers = {}

    def handle_signal(signum, _frame):
        if process is not None and process.poll() is None:
            process.terminate()
        raise ExecutionInterrupted(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, handle_signal)

    exit_code = 1
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_file, \
             stderr_path.open("w", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(
                command_argv,
                cwd=workspace_root,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
            )
            exit_code = process.wait()
    except ExecutionInterrupted as exc:
        exit_code = 128 + exc.signum
        if process is not None and process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    except Exception as exc:
        with stderr_path.open("a", encoding="utf-8") as file:
            file.write(f"\nRunner error: {exc}\n")
        exit_code = 1
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    metadata["finished_at"] = now()
    metadata["exit_code"] = exit_code
    metadata["status"] = "done" if exit_code == 0 else "failed"
    metadata["failure_reason"] = (
        None if exit_code == 0 else f"Process exited with code {exit_code}."
    )
    write_json(run_json_path, metadata)

    print(
        f"[{metadata['status'].upper()}] "
        f"{args.experiment}/{run_dir.name} (exit={exit_code})"
    )
    return exit_code


def registered_runs(experiment_run_dir):
    registered = {}
    if not experiment_run_dir.exists():
        return registered
    for run_dir in sorted(experiment_run_dir.iterdir()):
        if not run_dir.is_dir() or not RUN_ID_PATTERN.match(run_dir.name):
            continue
        metadata = read_json(run_dir / "run.json")
        run_id = normalize_run_id(metadata.get("run_id", ""))
        if run_id in registered:
            raise RuntimeError(
                f"Multiple registered directories use {run_id} under "
                f"{experiment_run_dir}."
            )
        registered[run_id] = (run_dir, metadata)
    return registered


def validate_assignment(args, workspace_root, repo_name):
    _, experiment_run_dir = experiment_paths(
        workspace_root, repo_name, args.experiment
    )
    registered = registered_runs(experiment_run_dir)
    if not registered:
        raise RuntimeError(f"No registered Runs found under {experiment_run_dir}.")

    pending = {
        run_id
        for run_id, (_, metadata) in registered.items()
        if metadata.get("status") == "pending"
    }
    if not pending:
        raise RuntimeError(f"No pending Runs found under {experiment_run_dir}.")

    assigned = [normalize_run_id(run_id) for run_id in args.run]
    duplicates = sorted({run_id for run_id in assigned if assigned.count(run_id) > 1})
    missing = sorted(pending - set(assigned))
    unknown = sorted(set(assigned) - set(registered))
    non_pending = sorted(
        run_id
        for run_id in set(assigned) & set(registered)
        if registered[run_id][1].get("status") != "pending"
    )

    problems = []
    if duplicates:
        problems.append("assigned more than once: " + ", ".join(duplicates))
    if missing:
        problems.append("not assigned: " + ", ".join(missing))
    if unknown:
        problems.append("not registered: " + ", ".join(unknown))
    if non_pending:
        problems.append("local status is not pending: " + ", ".join(non_pending))
    if problems:
        raise RuntimeError("Invalid Run assignment; " + "; ".join(problems))

    print(f"[ASSIGNMENT OK] {args.experiment}: {len(assigned)} pending Runs")
    return 0


def mark_failed(args, workspace_root, repo_name):
    run_id = normalize_run_id(args.run_id)
    _, experiment_run_dir = experiment_paths(
        workspace_root, repo_name, args.experiment
    )
    run_dir = find_registered_run(experiment_run_dir, run_id)
    if run_dir is None:
        raise RuntimeError(f"{run_id} is not registered under {experiment_run_dir}.")

    run_json_path = run_dir / "run.json"
    metadata = read_json(run_json_path)
    current_status = metadata.get("status")
    if current_status not in {"pending", "running"}:
        raise RuntimeError(
            f"{run_dir.name} cannot be marked failed from status "
            f"{current_status!r}; expected 'pending' or 'running'."
        )

    reason = args.reason.strip()
    if not reason:
        raise RuntimeError("A non-empty failure reason is required.")
    timestamp = now()
    metadata.update(
        {
            "status": "failed",
            "finished_at": timestamp,
            "exit_code": None,
            "failure_reason": reason,
            "reconciled_at": timestamp,
        }
    )
    write_json(run_json_path, metadata)
    print(f"[FAILED] {args.experiment}/{run_dir.name}: {reason}")
    return 0


def main():
    args = parse_args()
    workspace_root, repo_name, repo_root = resolve_workspace()
    if repo_name == "_template":
        raise RuntimeError(
            "Copy the runner template to scripts/<repo>/runner/ before using it."
        )

    if args.action == "register":
        return register_run(args, workspace_root, repo_name, repo_root)
    if args.action == "execute":
        return execute_run(args, workspace_root, repo_name, repo_root)
    if args.action == "validate-assignment":
        return validate_assignment(args, workspace_root, repo_name)
    if args.action == "mark-failed":
        return mark_failed(args, workspace_root, repo_name)
    raise RuntimeError(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
