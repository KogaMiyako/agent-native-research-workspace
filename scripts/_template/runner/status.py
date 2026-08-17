#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


STATUS_ORDER = {
    "running": 0,
    "pending": 1,
    "failed": 2,
    "done": 3,
    "unknown": 4,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect the execution status of Runs."
    )

    parser.add_argument(
        "experiment",
        nargs="?",
        help="Experiment directory name, e.g. E003-param-topk.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all Experiments under this repository.",
    )

    parser.add_argument(
        "--failed",
        action="store_true",
        help="Show only failed Runs.",
    )

    parser.add_argument(
        "--running",
        action="store_true",
        help="Show only running Runs.",
    )

    return parser.parse_args()


def resolve_workspace():
    # scripts/<repo>/runner/status.py
    script_path = Path(__file__).resolve()

    repo_name = script_path.parent.parent.name
    workspace_root = script_path.parents[3]

    runs_root = workspace_root / "runs" / repo_name

    return workspace_root, repo_name, runs_root


def load_run(run_dir):
    run_json = run_dir / "run.json"

    if not run_json.exists():
        return {
            "run_id": run_dir.name,
            "status": "unknown",
            "host": "",
            "device": "",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "failure_reason": "",
        }

    try:
        with run_json.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            "run_id": run_dir.name,
            "status": "unknown",
            "host": "",
            "device": "",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "failure_reason": "",
        }

    return {
        "run_id": data.get("run_name", data.get("run_id", run_dir.name)),
        "status": data.get("status", "unknown"),
        "host": data.get("host", ""),
        "device": data.get("device", ""),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "exit_code": data.get("exit_code"),
        "failure_reason": data.get("failure_reason", ""),
    }


def get_runs(experiment_dir):
    runs = []

    if not experiment_dir.exists():
        return runs

    for path in sorted(experiment_dir.iterdir()):
        if not path.is_dir():
            continue

        if not path.name.startswith("R"):
            continue

        runs.append(load_run(path))

    return runs


def filter_runs(runs, args):
    if args.failed:
        return [run for run in runs if run["status"] == "failed"]

    if args.running:
        return [run for run in runs if run["status"] == "running"]

    return runs


def format_value(value):
    if value is None:
        return "-"
    if value == "":
        return "-"
    return str(value)


def print_runs(experiment_name, runs, args):
    runs = filter_runs(runs, args)

    print(f"\nExperiment: {experiment_name}")

    if not runs:
        print("  No Runs found.")
        return

    headers = [
        "Run",
        "Status",
        "Host",
        "Device",
        "Exit",
        "Started",
        "Finished",
        "Reason",
    ]

    rows = []

    for run in runs:
        rows.append([
            run["run_id"],
            run["status"].upper(),
            format_value(run["host"]),
            format_value(run["device"]),
            format_value(run["exit_code"]),
            format_value(run["started_at"]),
            format_value(run["finished_at"]),
            format_value(run["failure_reason"]),
        ])

    widths = []

    for index, header in enumerate(headers):
        widths.append(
            max(
                len(header),
                max(len(str(row[index])) for row in rows),
            )
        )

    header_line = "  ".join(
        header.ljust(widths[index])
        for index, header in enumerate(headers)
    )

    print(header_line)
    print("-" * len(header_line))

    for row in rows:
        print(
            "  ".join(
                str(value).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )

    counts = {}

    for run in runs:
        status = run["status"]
        counts[status] = counts.get(status, 0) + 1

    summary_order = [
        "done",
        "running",
        "failed",
        "pending",
        "unknown",
    ]

    summary = []

    for status in summary_order:
        count = counts.get(status, 0)
        if count:
            summary.append(f"{status}={count}")

    print()
    print(f"Runs: {len(runs)}  " + "  ".join(summary))


def experiment_summary(experiment_dir):
    runs = get_runs(experiment_dir)

    counts = {
        "done": 0,
        "running": 0,
        "failed": 0,
        "pending": 0,
        "unknown": 0,
    }

    for run in runs:
        status = run["status"]

        if status not in counts:
            status = "unknown"

        counts[status] += 1

    total = len(runs)

    if counts["running"]:
        overall = "RUNNING"
    elif counts["failed"]:
        overall = "FAILED"
    elif total > 0 and counts["done"] == total:
        overall = "DONE"
    elif counts["pending"]:
        overall = "PENDING"
    elif total == 0:
        overall = "EMPTY"
    else:
        overall = "INCOMPLETE"

    return {
        "experiment": experiment_dir.name,
        "status": overall,
        "total": total,
        **counts,
    }


def print_all(runs_root):
    if not runs_root.exists():
        print(f"No run directory found: {runs_root}")
        return

    experiments = [
        path
        for path in sorted(runs_root.iterdir())
        if path.is_dir()
    ]

    if not experiments:
        print("No Experiments found.")
        return

    rows = []

    for experiment_dir in experiments:
        summary = experiment_summary(experiment_dir)

        rows.append([
            summary["experiment"],
            summary["status"],
            summary["total"],
            summary["done"],
            summary["running"],
            summary["failed"],
            summary["pending"],
        ])

    headers = [
        "Experiment",
        "Status",
        "Runs",
        "Done",
        "Running",
        "Failed",
        "Pending",
    ]

    widths = []

    for index, header in enumerate(headers):
        widths.append(
            max(
                len(header),
                max(len(str(row[index])) for row in rows),
            )
        )

    header_line = "  ".join(
        header.ljust(widths[index])
        for index, header in enumerate(headers)
    )

    print(header_line)
    print("-" * len(header_line))

    for row in rows:
        print(
            "  ".join(
                str(value).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )


def main():
    args = parse_args()

    _, repo_name, runs_root = resolve_workspace()

    if repo_name == "_template":
        raise SystemExit(
            "Copy the runner template to scripts/<repo>/runner/ before using it."
        )

    print(f"Repository: {repo_name}")

    if args.all:
        print_all(runs_root)
        return

    if not args.experiment:
        raise SystemExit(
            "Specify an Experiment, or use --all.\n"
            "Example:\n"
            "  status.py E003-param-topk\n"
            "  status.py --all"
        )

    experiment_dir = runs_root / args.experiment

    if not experiment_dir.exists():
        raise SystemExit(
            f"Experiment run directory does not exist:\n"
            f"  {experiment_dir}"
        )

    runs = get_runs(experiment_dir)
    print_runs(args.experiment, runs, args)


if __name__ == "__main__":
    main()
