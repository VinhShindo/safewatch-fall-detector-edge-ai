# -*- coding: utf-8 -*-
"""
evaluation.py
=============
Đánh giá model (float Keras) bằng classification report + ma trận nhầm lẫn.

Nguồn gốc trong notebook Colab: Cell 15
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
)

from utils.config import CLASS_NAMES, FALL, NON_FALL, OUTPUT_DIR


def evaluate_float_model(
    model,
    X,
    y,
    title,
    threshold=0.5,
    show=True,
    output_dir: Path = OUTPUT_DIR,
):
    """(Cell 15)"""
    probabilities = model.predict(X, verbose=0)[:, FALL]

    predictions = (probabilities >= threshold).astype("int64")

    print(f"\n===== {title} =====")
    print(
        classification_report(
            y, predictions, target_names=CLASS_NAMES, digits=4, zero_division=0
        )
    )

    matrix = confusion_matrix(y, predictions, labels=[NON_FALL, FALL])

    ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=CLASS_NAMES).plot(
        values_format="d"
    )

    plt.title(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^a-zA-Z0-9_.-]+", "_", title).strip("_").lower()
    plt.savefig(
        output_dir / f"{safe_title}_confusion_matrix.png",
        dpi=150,
        bbox_inches="tight",
    )

    if show:
        plt.show()
    else:
        plt.close()

    return probabilities, predictions
