#!/usr/bin/env python3
"""Run EDA on the local QMI and WEDA-FALL datasets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
QMI_DIR = RAW_DIR / "QMI"
WEDA_DIR = RAW_DIR / "WEDA-FALL"
EDA_DIR = REPO_ROOT / "outputs" / "eda"


def _csv_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.csv")) if root.exists() else []


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a report table without requiring the optional tabulate package."""
    try:
        return frame.to_markdown(index=False)
    except (ImportError, ModuleNotFoundError):
        return "```text\n" + frame.to_string(index=False) + "\n```"


def _qmi_summary(files: list[Path]) -> pd.DataFrame:
    rows = []
    for path in files:
        frame = pd.read_csv(path)
        rows.append(
            {
                "file": path.name,
                "rows": len(frame),
                "sessions": frame["session_id"].nunique() if "session_id" in frame else None,
                "labels": ", ".join(sorted(frame["label"].dropna().astype(str).unique()))
                if "label" in frame
                else "",
            }
        )
    return pd.DataFrame(rows)


def _weda_summary(files: list[Path]) -> pd.DataFrame:
    rows = []
    for path in files:
        frame = pd.read_csv(path)
        rows.append(
            {
                "file": str(path),
                "rows": len(frame),
                "activity_folder": path.parent.name,
                "columns": ", ".join(map(str, frame.columns)),
            }
        )
    return pd.DataFrame(rows)


def run_eda(
    qmi_dir: Path = QMI_DIR,
    weda_dir: Path = WEDA_DIR,
    eda_dir: Path = EDA_DIR,
) -> Path:
    """Create CSV summaries, a report, and plots in outputs/eda."""
    eda_dir.mkdir(parents=True, exist_ok=True)
    qmi = _qmi_summary(_csv_files(qmi_dir))
    weda_5hz_dir = weda_dir / "dataset" / "5Hz"
    weda_source_dir = weda_5hz_dir if weda_5hz_dir.exists() else weda_dir
    weda = _weda_summary(
        [path for path in _csv_files(weda_source_dir) if path.name.endswith("_accel.csv")]
    )

    qmi.to_csv(eda_dir / "qmi_file_summary.csv", index=False)
    weda.to_csv(eda_dir / "weda_file_summary.csv", index=False)

    report_lines = [
        "# SafeWatch Dataset EDA Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Dataset layout",
        "",
        "The merged raw data keeps QMI and WEDA-FALL separate under `data/raw/merge` because their raw CSV schemas differ. This EDA focuses on WEDA-FALL 5 Hz accelerometer files, which are used by the training pipeline.",
        "",
        "## QMI",
        "",
        f"- CSV files: {len(qmi)}",
        f"- Total rows: {int(qmi['rows'].sum()) if not qmi.empty else 0}",
        f"- Total sessions: {sum(int(pd.read_csv(path)['session_id'].nunique()) for path in _csv_files(qmi_dir))}",
        "",
        "### QMI file summary",
        "",
        _markdown_table(qmi) if not qmi.empty else "No QMI files found.",
        "",
        "## WEDA-FALL",
        "",
        f"- CSV files: {len(weda)}",
        f"- Total rows: {int(weda['rows'].sum()) if not weda.empty else 0}",
        "",
        "### WEDA file summary",
        "",
        _markdown_table(weda.head(30)) if not weda.empty else "No WEDA CSV files found.",
        "",
        "## Interpretation",
        "",
        "WEDA-FALL is used for general pretraining and QMI is used for person/sensor-specific adaptation. Keep validation and test sessions separated by session or user to avoid window leakage.",
    ]
    report = "\n".join(report_lines) + "\n"
    (eda_dir / "report.md").write_text(report, encoding="utf-8")
    (eda_dir / "readme.md").write_text(report, encoding="utf-8")

    try:
        import matplotlib.pyplot as plt

        if not qmi.empty:
            labels = qmi["labels"].str.split(", ").explode().value_counts()
            labels.plot(kind="bar", title="QMI files by label")
            plt.tight_layout()
            plt.savefig(eda_dir / "qmi_labels.png", dpi=150)
            plt.close()

        if not weda.empty:
            weda["activity_folder"].value_counts().head(30).plot(
                kind="bar", title="WEDA files by activity folder"
            )
            plt.tight_layout()
            plt.savefig(eda_dir / "weda_activities.png", dpi=150)
            plt.close()
    except ImportError:
        print("matplotlib is unavailable; skipped EDA plots")

    print(f"EDA outputs written to {eda_dir}")
    return eda_dir / "report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmi-dir", type=Path, default=QMI_DIR)
    parser.add_argument("--weda-dir", type=Path, default=WEDA_DIR)
    parser.add_argument("--output-dir", type=Path, default=EDA_DIR)
    args = parser.parse_args()
    run_eda(args.qmi_dir, args.weda_dir, args.output_dir)


if __name__ == "__main__":
    main()
