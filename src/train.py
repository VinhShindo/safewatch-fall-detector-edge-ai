#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
========
Điểm vào (entry point) để chạy toàn bộ pipeline SafeWatch từ dòng lệnh.

Cách dùng:
    1. Đặt file dữ liệu cá nhân của bạn tại:
           /content/data_records.zip
       (hoặc chỉnh lại config.QMI_ZIP_PATH cho phù hợp với máy bạn).

    2. Chạy:
           python main.py

Pipeline sẽ tự động:
    - Clone repo WEDA-FALL, giải nén dữ liệu QMI            (Cell 3)
    - Đọc & tiền xử lý dữ liệu, cắt cửa sổ, sinh feature     (Cell 4-12)
    - Xây dựng, pretrain trên WEDA, fine-tune trên QMI       (Cell 13-19)
    - Xuất model INT8 TFLite + toàn bộ mã nguồn C/C++/Arduino
      cho ESP32-S3, đóng gói thành 1 file ZIP                (Cell 21-26)

Toàn bộ kết quả trung gian và cuối cùng được lưu tại
`safewatch_pipeline.config.OUTPUT_DIR`
(mặc định: /content/safewatch_5hz_output).
"""

from safewatch_pipeline.pipeline import run_full_pipeline

if __name__ == "__main__":
    run_full_pipeline()
