# -*- coding: utf-8 -*-
"""Validate the repository-local datasets used by the training pipeline."""

from pathlib import Path

from utils.config import QMI_DATA_DIR, WEDA_5HZ_DIR


def prepare_all_data(
    qmi_dir: Path = QMI_DATA_DIR,
    weda_5hz_dir: Path = WEDA_5HZ_DIR,
):
    """Return prepared QMI and WEDA paths without downloading or extracting data."""
    qmi_csv_files = sorted(qmi_dir.rglob("*.csv")) if qmi_dir.exists() else []
    weda_accel_files = (
        sorted(weda_5hz_dir.rglob("*_accel.csv"))
        if weda_5hz_dir.exists()
        else []
    )

    if not qmi_csv_files:
        raise FileNotFoundError(f"Không tìm thấy CSV QMI trong: {qmi_dir}")
    if not weda_accel_files:
        raise FileNotFoundError(
            f"Không tìm thấy CSV accelerometer WEDA 5 Hz trong: {weda_5hz_dir}"
        )

    print("===== DATASET ĐÃ CHUẨN BỊ =====")
    print("Thư mục QMI:", qmi_dir)
    print("Thư mục WEDA 5 Hz:", weda_5hz_dir)
    print("Số file CSV QMI:", len(qmi_csv_files))
    print("Số file accelerometer WEDA:", len(weda_accel_files))

    return {
        "qmi_extract_dir": qmi_dir,
        "weda_5hz_dir": weda_5hz_dir,
    }


if __name__ == "__main__":
    prepare_all_data()
