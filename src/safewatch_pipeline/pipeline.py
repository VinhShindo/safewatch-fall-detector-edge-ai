# -*- coding: utf-8 -*-
"""
pipeline.py
============
Điều phối toàn bộ pipeline theo đúng thứ tự các Cell trong notebook
Colab gốc:

  Cell 3           -> data_loading.prepare_data
  Cell 4/5/5A       -> features
  Cell 5.5          -> data_loading.weda
  Cell 7            -> data_loading.qmi
  Cell 8            -> audit
  Cell 9            -> splitting
  Cell 9.5 / 10     -> windowing
  Cell 11           -> normalization
  Cell 12           -> augmentation
  Cell 13           -> model
  Cell 14           -> train_pretrain
  Cell 15           -> evaluation
  Cell 15.5 / 16    -> finetune_prep
  Cell 17 / 18      -> finetune_train
  Cell 19           -> threshold_selection
  Cell 20 (tùy chọn)-> next_day_test
  Cell 21           -> export.tflite_export
  Cell 22           -> export.tflite_verify
  Cell 22.5 / 23    -> export.cpp_export
  Cell 24           -> export.inference_cpp
  Cell 25           -> export.arduino_export
  Cell 26           -> export.package

Chạy trực tiếp: `python -m safewatch_pipeline.pipeline`
(hoặc dùng main.py ở thư mục gốc).
"""

from . import audit, config, splitting, windowing
from .augmentation import create_class_weights
from .data_loading.prepare_data import prepare_all_data
from .data_loading.qmi import load_qmi_sessions, print_qmi_summary
from .data_loading.weda import load_weda_sessions, print_weda_distributions
from .evaluation import evaluate_float_model
from .export.arduino_export import export_arduino_sketch
from .export.cpp_export import export_cpp_and_config
from .export.inference_cpp import export_inference_cpp
from .export.package import build_package_zip, maybe_download_in_colab, write_readme
from .export.tflite_export import export_int8_tflite
from .export.tflite_verify import verify_int8_model
from .finetune_prep import build_finetune_dataset
from .finetune_train import finetune_stage1, finetune_stage2
from .model import build_model, compile_model
from .normalization import domain_weighted_mean_std, make_normalizer
from .threshold_selection import evaluate_with_selected_threshold, select_fall_threshold


def run_full_pipeline():
    """
    Chạy toàn bộ pipeline từ đầu đến cuối, tương đương chạy tuần tự
    tất cả các cell trong notebook gốc (Cell 3 -> Cell 26).
    """

    # ---------------------------------------------------------------
    # Cell 3 — chuẩn bị dữ liệu
    # ---------------------------------------------------------------
    paths = prepare_all_data()
    qmi_extract_dir = paths["qmi_extract_dir"]
    weda_5hz_dir = paths["weda_5hz_dir"]

    # ---------------------------------------------------------------
    # Cell 5.5 — nạp session WEDA
    # ---------------------------------------------------------------
    weda_sessions = load_weda_sessions(weda_5hz_dir)
    print_weda_distributions(weda_sessions, config.CLASS_NAMES)

    # ---------------------------------------------------------------
    # Cell 7 — nạp session QMI (person A)
    # ---------------------------------------------------------------
    qmi_sessions = load_qmi_sessions(qmi_extract_dir)
    print_qmi_summary(qmi_sessions, config.CLASS_NAMES)

    # ---------------------------------------------------------------
    # Cell 8 — audit dữ liệu
    # ---------------------------------------------------------------
    audit.summarize_sessions(weda_sessions, "WEDA")
    audit.summarize_sessions(qmi_sessions, "QMI PERSON A")
    audit.plot_example_sessions(qmi_sessions, show=False)

    # ---------------------------------------------------------------
    # Cell 9 — chia train/val/test
    # ---------------------------------------------------------------
    weda_train, weda_val, weda_test = splitting.split_weda_by_user(weda_sessions)
    qmi_train, qmi_val = splitting.split_qmi_by_session(qmi_sessions)

    splitting.print_split("WEDA train", weda_train, config.CLASS_NAMES)
    splitting.print_split("WEDA validation", weda_val, config.CLASS_NAMES)
    splitting.print_split("WEDA test", weda_test, config.CLASS_NAMES)
    splitting.print_split("QMI train", qmi_train, config.CLASS_NAMES)
    splitting.print_split("QMI validation", qmi_val, config.CLASS_NAMES)

    qmi_train_ids = {r.session_id for r in qmi_train}
    qmi_validation_ids = {r.session_id for r in qmi_val}
    assert not (qmi_train_ids & qmi_validation_ids)

    # ---------------------------------------------------------------
    # Cell 9.5 / 10 — cắt cửa sổ + feature
    # ---------------------------------------------------------------
    X_weda_train_raw, y_weda_train, *_ = windowing.sessions_to_windows(
        weda_train, training=True, max_nonfall_windows=config.MAX_WEDA_NONFALL_WINDOWS_TRAIN
    )
    X_weda_val_raw, y_weda_val, *_ = windowing.sessions_to_windows(
        weda_val, training=False, max_nonfall_windows=config.MAX_WEDA_NONFALL_WINDOWS_EVAL
    )
    X_weda_test_raw, y_weda_test, *_ = windowing.sessions_to_windows(
        weda_test, training=False, max_nonfall_windows=config.MAX_WEDA_NONFALL_WINDOWS_EVAL
    )
    X_qmi_train_raw, y_qmi_train, *_ = windowing.sessions_to_windows(
        qmi_train, training=True, max_nonfall_windows=config.MAX_QMI_NONFALL_WINDOWS_TRAIN
    )
    X_qmi_val_raw, y_qmi_val, *_ = windowing.sessions_to_windows(
        qmi_val, training=False, max_nonfall_windows=config.MAX_QMI_NONFALL_WINDOWS_EVAL
    )

    # ---------------------------------------------------------------
    # Cell 11 — chuẩn hóa feature
    # ---------------------------------------------------------------
    feature_mean, feature_std = domain_weighted_mean_std(X_weda_train_raw, X_qmi_train_raw)
    normalize_features = make_normalizer(feature_mean, feature_std)

    X_weda_train = normalize_features(X_weda_train_raw)
    X_weda_val = normalize_features(X_weda_val_raw)
    X_weda_test = normalize_features(X_weda_test_raw)
    X_qmi_train = normalize_features(X_qmi_train_raw)
    X_qmi_val = normalize_features(X_qmi_val_raw)

    # ---------------------------------------------------------------
    # Cell 12 — class weights cho pretrain
    # ---------------------------------------------------------------
    weda_class_weights = create_class_weights(y_weda_train)

    # ---------------------------------------------------------------
    # Cell 13 — xây model
    # ---------------------------------------------------------------
    model = build_model()
    compile_model(model, learning_rate=1e-3)
    model.summary()

    # ---------------------------------------------------------------
    # Cell 14 — pretrain trên WEDA
    # ---------------------------------------------------------------
    from .train_pretrain import pretrain_on_weda

    pretrain_on_weda(
        model, X_weda_train, y_weda_train, X_weda_val, y_weda_val, weda_class_weights
    )

    # ---------------------------------------------------------------
    # Cell 15 — đánh giá sau pretrain
    # ---------------------------------------------------------------
    evaluate_float_model(
        model, X_weda_test, y_weda_test, title="WEDA test sau pretrain", show=False
    )

    # ---------------------------------------------------------------
    # Cell 15.5 / 16 — chuẩn bị tập fine-tune
    # ---------------------------------------------------------------
    X_finetune, y_finetune, finetune_class_weights = build_finetune_dataset(
        X_qmi_train, y_qmi_train, X_weda_train, y_weda_train
    )

    # ---------------------------------------------------------------
    # Cell 17 / 18 — fine-tune 2 giai đoạn
    # ---------------------------------------------------------------
    finetune_stage1(model, X_finetune, y_finetune, X_qmi_val, y_qmi_val, finetune_class_weights)
    _, finetuned_model_path = finetune_stage2(
        model, X_finetune, y_finetune, X_qmi_val, y_qmi_val, finetune_class_weights
    )

    # ---------------------------------------------------------------
    # Cell 19 — chọn threshold
    # ---------------------------------------------------------------
    threshold_info = select_fall_threshold(model, X_qmi_val, y_qmi_val)
    fall_threshold = threshold_info["fall_threshold"]
    high_fall_threshold = threshold_info["high_fall_threshold"]
    consecutive_required = threshold_info["consecutive_required"]

    evaluate_with_selected_threshold(
        model, X_qmi_val, y_qmi_val, X_weda_test, y_weda_test, fall_threshold
    )

    # ---------------------------------------------------------------
    # Cell 20 — (tùy chọn) test ngày hôm sau: mặc định tắt, xem
    # next_day_test.py để bật thủ công khi có dữ liệu.
    # ---------------------------------------------------------------

    # ---------------------------------------------------------------
    # Cell 21 — export TFLite INT8
    # ---------------------------------------------------------------
    tflite_path = export_int8_tflite(model, X_weda_train, X_qmi_train)

    # ---------------------------------------------------------------
    # Cell 22 — verify TFLite INT8
    # ---------------------------------------------------------------
    qmi_val_probabilities_keras = model.predict(X_qmi_val, verbose=0)[:, config.FALL]
    verify_int8_model(
        tflite_path,
        X_qmi_val,
        y_qmi_val,
        fall_threshold,
        qmi_validation_probabilities_keras=qmi_val_probabilities_keras,
        show=False,
    )

    # ---------------------------------------------------------------
    # Cell 22.5 / 23 — export C/C++ + config
    # ---------------------------------------------------------------
    cpp_paths = export_cpp_and_config(
        tflite_path,
        feature_mean,
        feature_std,
        fall_threshold,
        high_fall_threshold,
        consecutive_required,
    )

    # ---------------------------------------------------------------
    # Cell 24 — inference wrapper (TFLite Micro)
    # ---------------------------------------------------------------
    inference_header_path, inference_source_path = export_inference_cpp()

    # ---------------------------------------------------------------
    # Cell 25 — Arduino sketch mẫu
    # ---------------------------------------------------------------
    arduino_template_path = export_arduino_sketch()

    # ---------------------------------------------------------------
    # Cell 26 — README + đóng gói ZIP
    # ---------------------------------------------------------------
    readme_path = write_readme(
        config.OUTPUT_DIR, fall_threshold, high_fall_threshold, consecutive_required
    )

    package_path = build_package_zip(
        finetuned_model_path,
        tflite_path,
        cpp_paths["model_header_path"],
        cpp_paths["model_source_path"],
        cpp_paths["config_header_path"],
        cpp_paths["config_json_path"],
        inference_header_path,
        inference_source_path,
        arduino_template_path,
        readme_path,
    )

    maybe_download_in_colab(package_path)

    return package_path


if __name__ == "__main__":
    run_full_pipeline()
