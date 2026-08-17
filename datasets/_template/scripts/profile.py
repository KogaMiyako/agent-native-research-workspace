"""
Dataset profiling template.

This script updates ../metadata.json with reproducible dataset statistics.

Without dataset-specific changes, this template only updates common statistics
and preserves the modality fields already present in metadata.json.

When adapting this template:
- implement only the collectors relevant to the current dataset;
- make collectors honor mode and sample_size when sampled profiling is used;
- preserve useful dataset-specific fields already present in metadata.json;
- prefer exact profiling when practical;
- use sampled profiling for expensive datasets when necessary;
- keep dataset interpretation and usage rules in DATASET.md, not here.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASET_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = DATASET_DIR / "data"
DEFAULT_METADATA_PATH = DATASET_DIR / "metadata.json"


def directory_size_bytes(path: Path) -> int:
    """Return total size of regular files under path."""
    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass

    return total


def collect_common_statistics(data_root: Path) -> dict[str, Any]:
    """
    Collect statistics that are meaningful across modalities.

    Extend this function when the logical sample count, missing-data
    statistics, or target statistics can be obtained reliably.
    """
    return {
        "total_samples": None,
        "disk_size_bytes": directory_size_bytes(data_root),
        "missing": {},
        "target": {},
    }


def collect_split_statistics(
    data_root: Path,
    mode: str,
    sample_size: int | None,
) -> dict[str, Any]:
    """
    Collect machine-readable split statistics.

    Example output:

    {
        "train": {"num_samples": 1000},
        "validation": {"num_samples": 200},
        "test": {"num_samples": 300}
    }

    Implement according to the split documented in DATASET.md.
    """
    return {}


def profile_time_series(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """Collect time-series-specific statistics after dataset adaptation."""
    return {}


def profile_image(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """Collect image-specific statistics after dataset adaptation."""
    return {}


def profile_video(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """Collect video-specific statistics after dataset adaptation."""
    return {}


def profile_audio(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """Collect audio-specific statistics after dataset adaptation."""
    return {}


def profile_text(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """Collect text-specific statistics after dataset adaptation."""
    return {}


def profile_multimodal(
    data_root: Path, mode: str, sample_size: int | None
) -> dict[str, Any]:
    """
    Collect multimodal statistics.

    Reuse modality-specific profiling functions when appropriate.
    """
    return {}


PROFILERS = {
    "time_series": profile_time_series,
    "image": profile_image,
    "video": profile_video,
    "audio": profile_audio,
    "text": profile_text,
    "multimodal": profile_multimodal,
}


def load_metadata(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_metadata(path: Path, metadata: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_metadata(
    metadata: dict[str, Any],
    data_root: Path,
    mode: str,
    sample_size: int | None,
) -> dict[str, Any]:

    modality = metadata.get("modality")

    if modality not in PROFILERS:
        raise ValueError(f"Unsupported modality: {modality!r}")

    common = collect_common_statistics(data_root)
    modality_stats = PROFILERS[modality](data_root, mode, sample_size)

    statistics = metadata.setdefault("statistics", {})
    statistics.update(common)
    existing_modality = statistics.setdefault("modality", {})
    existing_modality.update(modality_stats)

    split_stats = collect_split_statistics(data_root, mode, sample_size)
    if split_stats:
        metadata["splits"] = split_stats

    metadata["profile"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/profile.py",
        "mode": mode,
        "sample_size": sample_size if mode == "sampled" else None,
    }

    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile a managed dataset.")

    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Canonical dataset data directory.",
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA_PATH,
        help="metadata.json to update.",
    )

    parser.add_argument(
        "--mode",
        choices=["exact", "sampled"],
        default="exact",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Number of samples used when --mode sampled.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.data_root.exists():
        raise FileNotFoundError(f"Dataset path not found: {args.data_root}")

    if args.mode == "sampled" and args.sample_size is None:
        raise ValueError("--sample-size is required when --mode sampled")
    if args.sample_size is not None and args.sample_size <= 0:
        raise ValueError("--sample-size must be greater than zero")
    if args.mode == "exact" and args.sample_size is not None:
        raise ValueError("--sample-size is only valid when --mode sampled")

    metadata = load_metadata(args.metadata)

    metadata = build_metadata(
        metadata=metadata,
        data_root=args.data_root,
        mode=args.mode,
        sample_size=args.sample_size,
    )

    save_metadata(args.metadata, metadata)

    print(f"Updated metadata: {args.metadata}")


if __name__ == "__main__":
    main()
