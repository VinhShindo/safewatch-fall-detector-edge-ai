# -*- coding: utf-8 -*-
"""
prepare_data.py
================
Chuẩn bị dữ liệu QMI (person A) và WEDA-FALL.

Nguồn gốc trong notebook Colab: Cell 3
("CELL 3 — Upload dữ liệu QMI và tải WEDA-FALL")

LƯU Ý KHI CHUYỂN TỪ COLAB SANG SCRIPT LOCAL:
Notebook gốc dùng `google.colab.files.upload()` để người dùng chọn
file `data_records.zip` bằng tay trong trình duyệt. Trên máy local
không có cơ chế này, nên hàm dưới đây chỉ còn kiểm tra file đã tồn
tại tại QMI_ZIP_PATH; nếu chưa có, script sẽ báo lỗi rõ ràng để
người dùng copy file vào đúng đường dẫn (hoặc truyền qua tham số
`qmi_zip_path`). Toàn bộ phần còn lại (clone WEDA-FALL, giải nén,
kiểm tra kết quả) được giữ nguyên logic như Cell 3.
"""

import shutil
import subprocess
import zipfile
from pathlib import Path

from ..config import (
    CONTENT_DIR,
    QMI_EXTRACT_DIR,
    QMI_ZIP_PATH,
    WEDA_5HZ_DIR,
    WEDA_REPO_DIR,
)

WEDA_GIT_URL = "https://github.com/joaojtmarques/WEDA-FALL.git"


def _prompt_for_qmi_zip(qmi_zip_path: Path):
    """
    Thay thế cho `google.colab.files.upload()` trong Cell 3.
    Trên local, ta chỉ có thể yêu cầu người dùng đặt file đúng chỗ.
    """
    raise FileNotFoundError(
        "Không tìm thấy file: "
        f"{qmi_zip_path}\n"
        "Ở notebook gốc (Cell 3), bước này dùng "
        "google.colab.files.upload() để chọn file "
        "data_records.zip theo cách thủ công. Trên script local, "
        f"hãy copy/đặt file ZIP của bạn vào đúng đường dẫn: {qmi_zip_path}"
    )


def download_weda_fall(weda_repo_dir: Path = WEDA_REPO_DIR):
    """CLONE WEDA-FALL (Cell 3)."""
    if not weda_repo_dir.exists():
        print("\nĐang tải WEDA-FALL...")
        subprocess.run(
            ["git", "clone", "--depth", "1", WEDA_GIT_URL, str(weda_repo_dir)],
            check=True,
        )
    else:
        print("\nWEDA-FALL đã tồn tại.")


def locate_weda_5hz_dir(weda_repo_dir: Path = WEDA_REPO_DIR, weda_5hz_dir: Path = WEDA_5HZ_DIR):
    """KIỂM TRA THƯ MỤC WEDA 5 Hz (Cell 3)."""
    if weda_5hz_dir.exists():
        return weda_5hz_dir

    print("Không thấy đường dẫn mặc định:", weda_5hz_dir)
    print("\nCác thư mục có tên liên quan đến 5Hz:")

    possible_5hz_dirs = [
        path
        for path in weda_repo_dir.rglob("*")
        if (path.is_dir() and "5hz" in path.name.lower())
    ]

    for path in possible_5hz_dirs:
        print("-", path)

    if possible_5hz_dirs:
        weda_5hz_dir = possible_5hz_dirs[0]
        print("\nTự động sử dụng:", weda_5hz_dir)
        return weda_5hz_dir

    raise FileNotFoundError("Không tìm thấy thư mục dữ liệu WEDA 5 Hz.")


def extract_qmi_zip(
    qmi_zip_path: Path = QMI_ZIP_PATH,
    qmi_extract_dir: Path = QMI_EXTRACT_DIR,
):
    """GIẢI NÉN DỮ LIỆU QMI (Cell 3)."""
    if not qmi_zip_path.exists():
        _prompt_for_qmi_zip(qmi_zip_path)

    if qmi_extract_dir.exists():
        shutil.rmtree(qmi_extract_dir)

    qmi_extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(qmi_zip_path, mode="r") as zip_file:
        zip_file.extractall(qmi_extract_dir)

    return qmi_extract_dir


def prepare_all_data(
    content_dir: Path = CONTENT_DIR,
    qmi_zip_path: Path = QMI_ZIP_PATH,
    qmi_extract_dir: Path = QMI_EXTRACT_DIR,
    weda_repo_dir: Path = WEDA_REPO_DIR,
    weda_5hz_dir: Path = WEDA_5HZ_DIR,
):
    """
    Toàn bộ luồng chuẩn bị dữ liệu tương đương Cell 3:
    upload/kiểm tra ZIP QMI -> clone WEDA-FALL -> xác định thư mục
    5Hz -> giải nén QMI -> in kết quả kiểm tra.
    """
    if not qmi_zip_path.exists():
        _prompt_for_qmi_zip(qmi_zip_path)

    print("File QMI:", qmi_zip_path)

    download_weda_fall(weda_repo_dir)
    weda_5hz_dir = locate_weda_5hz_dir(weda_repo_dir, weda_5hz_dir)

    extract_qmi_zip(qmi_zip_path, qmi_extract_dir)

    qmi_csv_files = sorted(qmi_extract_dir.rglob("*.csv"))
    weda_accel_files = sorted(weda_5hz_dir.rglob("*_accel.csv"))

    print("\n===== KẾT QUẢ =====")
    print("Thư mục QMI:", qmi_extract_dir)
    print("Thư mục WEDA 5 Hz:", weda_5hz_dir)
    print("Số file CSV QMI:", len(qmi_csv_files))
    print("Số file accelerometer WEDA:", len(weda_accel_files))

    print("\nCác file QMI tìm thấy:")
    for path in qmi_csv_files:
        print("-", path.name)

    if len(qmi_csv_files) == 0:
        raise RuntimeError("Không tìm thấy file CSV trong data_records.zip.")

    if len(weda_accel_files) == 0:
        raise RuntimeError("Không tìm thấy file *_accel.csv trong WEDA 5 Hz.")

    print("\nCELL 3: HOÀN THÀNH")

    return {
        "qmi_extract_dir": qmi_extract_dir,
        "weda_5hz_dir": weda_5hz_dir,
    }


if __name__ == "__main__":
    prepare_all_data()
