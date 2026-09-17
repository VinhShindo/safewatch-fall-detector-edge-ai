#!/usr/bin/env python3
"""Download WEDA-FALL and merge it with the local QMI dataset."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import pandas as pd

WEDA_URL = "https://github.com/joaojtmarques/WEDA-FALL.git"
REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
QMI_DIR = RAW_DIR / "QMI"
WEDA_DIR = RAW_DIR / "WEDA-FALL"
MERGE_DIR = RAW_DIR / "merge"


def download_weda(destination: Path = WEDA_DIR) -> Path:
    """Clone WEDA-FALL once and return its local path."""
    if destination.exists() and any(destination.iterdir()):
        print(f"WEDA-FALL already exists: {destination}")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    print(f"Downloading WEDA-FALL into {destination} ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", WEDA_URL, str(destination)],
        check=True,
    )
    return destination


def _csv_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.csv")) if root.exists() else []


def merge_datasets(
    qmi_dir: Path = QMI_DIR,
    weda_dir: Path = WEDA_DIR,
    merge_dir: Path = MERGE_DIR,
) -> pd.DataFrame:
    """Copy QMI and WEDA under one folder and write a source manifest."""
    qmi_files = _csv_files(qmi_dir)
    weda_files = _csv_files(weda_dir)
    if not qmi_files:
        raise FileNotFoundError(f"No QMI CSV files found in {qmi_dir}")
    if not weda_files:
        raise FileNotFoundError(f"No WEDA CSV files found in {weda_dir}")

    if merge_dir.exists():
        shutil.rmtree(merge_dir)
    merge_dir.mkdir(parents=True)

    rows: list[dict[str, object]] = []
    for source, source_root, files in (
        ("QMI", qmi_dir, qmi_files),
        ("WEDA", weda_dir, weda_files),
    ):
        target_root = merge_dir / source
        for source_file in files:
            relative_path = source_file.relative_to(source_root)
            target_file = target_root / relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            rows.append(
                {
                    "source": source,
                    "relative_path": str(relative_path),
                    "file_name": source_file.name,
                    "bytes": source_file.stat().st_size,
                }
            )

    manifest = pd.DataFrame(rows)
    manifest.to_csv(merge_dir / "manifest.csv", index=False)
    print(f"Merged layout written to {merge_dir}")
    print(f"QMI files: {len(qmi_files)} | WEDA CSV files: {len(weda_files)}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    if not args.skip_download:
        download_weda()
    merge_datasets()


if __name__ == "__main__":
    main()
