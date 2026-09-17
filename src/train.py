#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
========
Điểm vào (entry point) để chạy toàn bộ pipeline SafeWatch từ dòng lệnh.

Cách dùng:
    1. Đặt QMI và WEDA theo đường dẫn trong config.yaml.
    2. Chạy từ thư mục src với PYTHONPATH=.: python3 train.py

Pipeline sẽ tự động:
    - Kiểm tra dữ liệu QMI/WEDA đã chuẩn bị trong repository       (Cell 3)
    - Đọc & tiền xử lý dữ liệu, cắt cửa sổ, sinh feature     (Cell 4-12)
    - Xây dựng, pretrain trên WEDA, fine-tune trên QMI       (Cell 13-19)
    - Xuất model INT8 TFLite + toàn bộ mã nguồn C/C++/Arduino
      cho ESP32-S3, đóng gói thành 1 file ZIP                (Cell 21-26)

Toàn bộ kết quả trung gian và cuối cùng được lưu tại đường dẫn
`paths.output_root` trong src/config.yaml; mỗi lần chạy tạo một run folder riêng.
"""

from pipeline import run_full_pipeline

if __name__ == "__main__":
    run_full_pipeline()
