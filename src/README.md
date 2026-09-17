# SafeWatch — Fall Detection Training & Edge Deployment Pipeline

Đây là bản **chuẩn hóa (refactor)** từ notebook Google Colab gốc
(`Untitled78.ipynb`) sang một package Python có cấu trúc module rõ
ràng, dùng để:

1. Nạp & tiền xử lý dữ liệu gia tốc từ 2 nguồn: **WEDA-FALL** (public
   dataset) và **QMI** (dữ liệu cá nhân, thu bằng cảm biến QMI8658).
2. Huấn luyện model CNN 1D nhẹ: **pretrain** trên WEDA, sau đó
   **fine-tune** 2 giai đoạn (progressive unfreezing) trên dữ liệu cá
   nhân.
3. Chọn ngưỡng quyết định (threshold) tối ưu.
4. Lượng tử hóa **Full INT8** sang TensorFlow Lite và xuất toàn bộ mã
   nguồn C/C++ + sketch Arduino để nạp vào **ESP32-S3** chạy
   TensorFlow Lite Micro.

> **Không thay đổi logic xử lý dữ liệu / huấn luyện / xuất model so
> với notebook gốc** — chỉ tách các cell thành module, thêm docstring
> chú thích rõ "Nguồn: Cell X" để dễ đối chiếu ngược lại notebook.

## Cấu trúc thư mục

```
safewatch_pipeline/
├── main.py                          # entry point (python main.py)
├── requirements.txt
└── safewatch_pipeline/
    ├── config.py                    # Cell 5A / 5.5 / 9.5 / 15.5 / 22.5
    ├── features.py                  # Cell 4, 5, 5A
    ├── audit.py                     # Cell 8
    ├── splitting.py                 # Cell 9
    ├── windowing.py                 # Cell 9.5 / 10
    ├── normalization.py             # Cell 11
    ├── augmentation.py              # Cell 12
    ├── model.py                     # Cell 13
    ├── train_pretrain.py            # Cell 14
    ├── evaluation.py                # Cell 15
    ├── finetune_prep.py             # Cell 15.5 / 16
    ├── finetune_train.py            # Cell 17 / 18
    ├── threshold_selection.py       # Cell 19
    ├── next_day_test.py             # Cell 20 (tùy chọn, mặc định tắt)
    ├── pipeline.py                  # điều phối toàn bộ (Cell 3 → 26)
    ├── data_loading/
    │   ├── prepare_data.py          # Cell 3 (tải/giải nén dữ liệu)
    │   ├── weda.py                  # Cell 5.5 (load_weda_sessions)
    │   └── qmi.py                   # Cell 7  (load_qmi_sessions)
    └── export/
        ├── tflite_export.py         # Cell 21 (lượng tử hóa INT8)
        ├── tflite_verify.py         # Cell 22 (kiểm tra model INT8)
        ├── cpp_export.py            # Cell 22.5 / 23 (header/config C++)
        ├── inference_cpp.py         # Cell 24 (TFLite Micro wrapper)
        ├── arduino_export.py        # Cell 25 (sketch .ino mẫu)
        └── package.py               # Cell 26 (README + đóng gói .zip)
```

## Cách chạy

### 1. Cài thư viện

```bash
pip install -r requirements.txt
```

### 2. Chuẩn bị dữ liệu

Notebook gốc (Cell 3) dùng `google.colab.files.upload()` để chọn file
`data_records.zip` bằng tay trong trình duyệt Colab. Trên máy local
không có cơ chế này, nên bạn cần tự đặt file vào đúng đường dẫn mà
`config.py` khai báo:

```
/content/data_records.zip
```

(Bạn có thể sửa `QMI_ZIP_PATH`, `CONTENT_DIR`, ... trong
`safewatch_pipeline/config.py` nếu muốn dùng đường dẫn khác trên máy
mình — đây là những đường dẫn giữ nguyên style `/content/...` như
notebook gốc, không bắt buộc phải theo Colab.)

Repo `WEDA-FALL` sẽ được tự động `git clone` (giống Cell 3), không cần
tải tay.

### 3. Chạy toàn bộ pipeline

```bash
python main.py
```

Lệnh này chạy tuần tự đúng như thứ tự Cell 3 → Cell 26 của notebook
gốc: chuẩn bị dữ liệu → nạp session → audit → chia tập → cắt cửa sổ →
chuẩn hóa → augment → build model → pretrain WEDA → fine-tune 2 giai
đoạn trên QMI → chọn threshold → export INT8 TFLite → verify → xuất
C/C++/Arduino → đóng gói ZIP.

Kết quả (model `.keras`, `.tflite`, các file `.h/.cc/.cpp`, sketch
`.ino`, README cho firmware, và file `.zip` đóng gói cuối cùng) đều
nằm trong thư mục cấu hình tại `config.OUTPUT_DIR`
(mặc định: `/content/safewatch_5hz_output`), và file ZIP tổng hợp tại
`config.PACKAGE_PATH`
(mặc định: `/content/safewatch_person_a_5hz_esp32_package.zip`).

### 4. Chạy từng bước riêng lẻ (nếu cần)

Mỗi module đều có thể import và gọi độc lập, tương tự chạy từng cell
trong Colab. Ví dụ chỉ muốn nạp dữ liệu và audit:

```python
from safewatch_pipeline.data_loading.prepare_data import prepare_all_data
from safewatch_pipeline.data_loading.weda import load_weda_sessions
from safewatch_pipeline.data_loading.qmi import load_qmi_sessions
from safewatch_pipeline.audit import summarize_sessions

paths = prepare_all_data()
weda_sessions = load_weda_sessions(paths["weda_5hz_dir"])
qmi_sessions = load_qmi_sessions(paths["qmi_extract_dir"])

summarize_sessions(weda_sessions, "WEDA")
summarize_sessions(qmi_sessions, "QMI PERSON A")
```

Xem `pipeline.py` để biết đúng thứ tự gọi các hàm giữa các module,
tương ứng với thứ tự cell gốc.

## Những điểm được điều chỉnh khi chuyển từ Colab sang script

Đây là các khác biệt **duy nhất** so với logic gốc (chỉ liên quan đến
môi trường chạy, không đụng đến thuật toán / công thức / kiến trúc
model):

1. **Cell 3** (`data_loading/prepare_data.py`): thay
   `google.colab.files.upload()` bằng việc kiểm tra file ZIP đã tồn
   tại sẵn tại đường dẫn cấu hình; nếu chưa có sẽ báo lỗi rõ ràng thay
   vì mở hộp thoại chọn file trong trình duyệt.
2. **Cell 20** (`next_day_test.py`): thay upload ZIP kiểm thử "ngày
   hôm sau" bằng tham số đường dẫn truyền vào hàm
   `run_next_day_test(...)`. Mặc định vẫn tắt (`RUN_NEXT_DAY_TEST =
   False`) giống notebook gốc.
3. **Cell 26** (`export/package.py`): hàm
   `files.download(...)` của Colab được bọc trong
   `maybe_download_in_colab(...)` — chỉ thực sự tải file khi script
   được chạy trong môi trường Colab, nếu chạy local thì chỉ in ra
   đường dẫn file ZIP đã tạo.
4. Các cell "khôi phục cấu hình" (Cell 5.5, Cell 9.5, Cell 15.5, Cell
   22.5) vốn dùng để notebook có thể chạy lại từng cell độc lập sau
   khi Colab reset runtime — trong script, các hằng số này được gom
   một lần vào `config.py`, không cần "khôi phục" thủ công nữa.
5. Cell 4 và Cell 5 trong notebook gốc là **hai cell trùng nội dung
   nhau** (có vẻ do copy nhầm khi soạn notebook); tương tự phần đầu
   Cell 6 lặp lại nguyên văn Cell 4 + Cell 5A. Bản refactor gộp các
   phần trùng lặp này lại thành một định nghĩa duy nhất trong
   `features.py`, tránh định nghĩa hàm 2 lần.

Ngoài các thay đổi có tính "hạ tầng" nêu trên, **toàn bộ công thức
tính feature, cách augment, kiến trúc model, learning rate, số epoch,
chiến lược progressive unfreezing, cách chọn threshold, cấu hình
lượng tử hóa INT8, và mã C/C++/Arduino sinh ra đều được giữ nguyên
100%** so với notebook gốc.
