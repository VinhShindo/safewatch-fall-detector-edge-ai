#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_sample_qmi_v4.py
==========================
Sinh dữ liệu QMI giả lập SÁT THỰC TẾ NHẤT — version 4 (FINAL).

Triết lý v4:
  - KHÔNG dùng cross-person split (v3 gây spurious correlation)
  - Thay vào đó, tạo OVERLAP 25–30% giữa weak FALL và strong NON_FALL
  - Đây chính là điểm làm QMI recall của real data chỉ 63.6%

Đặc trưng v4:
  1. Fall strength: 40% weak / 40% medium / 20% strong
     → weak falls CỐ TÌNH giống NON_FALL mạnh
  2. Subclinical falls: 20% FALL chỉ có spike nhỏ + orientation change ít
  3. Pseudo-falls mạnh: 25% NON_FALL có spike 2-2.5g giống weak FALL
  4. Mix persona (young/elderly/heavy) trong cả FALL và NON_FALL
  5. Environmental drift + outlier + sensor placement như v3
  6. Session length 25–50 (tránh drop sau resample)
  7. Ghi đè 1 file CSV với format khớp real data

Kỳ vọng kết quả sau khi train:
  - QMI val accuracy: 85–92%
  - QMI val FALL recall: 60–75%
  - QMI val FALL precision: 0.85–1.0
  - Threshold: 0.65–0.78
  - WEDA sau FT accuracy: 88–91%
  - WEDA sau FT FALL recall: 78–86%
  - INT8 agreement: 95–99%

Cách dùng:
    cd src
    PYTHONPATH=. python3 data/generate_sample_qmi_v4.py --overwrite
    PYTHONPATH=. python3 train.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "raw" / "QMI"

SAMPLE_INTERVAL_MS = 160
GRAVITY = 9.80665


# ===========================================================================
# Persona — mixed (không cross-person như v3)
# ===========================================================================
@dataclass
class Persona:
    name: str
    gravity_scale: float
    noise_scale: float
    impact_multiplier: float
    drift_rate: float
    recovery_chance: float
    outlier_chance: float


PERSONAS = {
    "young": Persona(
        name="young",
        gravity_scale=1.00,
        noise_scale=0.20,
        impact_multiplier=1.15,
        drift_rate=0.005,
        recovery_chance=0.20,
        outlier_chance=0.06,
    ),
    "elderly": Persona(
        name="elderly",
        gravity_scale=0.98,
        noise_scale=0.32,
        impact_multiplier=0.85,
        drift_rate=0.010,
        recovery_chance=0.08,
        outlier_chance=0.10,
    ),
    "heavy": Persona(
        name="heavy",
        gravity_scale=1.04,
        noise_scale=0.40,
        impact_multiplier=1.00,
        drift_rate=0.008,
        recovery_chance=0.12,
        outlier_chance=0.08,
    ),
}


# ===========================================================================
# Helpers (giống v3)
# ===========================================================================
def _smooth_noise(rng: np.random.Generator, n: int, scale: float) -> np.ndarray:
    raw = rng.normal(0.0, scale, size=n)
    if n >= 3:
        kernel = np.array([0.25, 0.5, 0.25])
        raw = np.convolve(raw, kernel, mode="same")
    return raw


def _make_session_id(rng: np.random.Generator) -> str:
    return f"{int(rng.integers(1_000_000, 9_999_999))}_{int(rng.integers(1000, 9999))}"


def _gyro_drift(rng: np.random.Generator, n: int, rate: float) -> tuple:
    bias = rng.normal(0, rate * 5, size=3)
    drift = np.linspace(0, rate * n, n)[:, None] * rng.normal(0, 1, size=3)[None, :]
    return bias, drift


def _apply_environmental_drift(
    rng: np.random.Generator,
    ax: np.ndarray, ay: np.ndarray, az: np.ndarray,
    n: int,
) -> tuple:
    t = np.linspace(0, 1, n)
    dc = rng.normal(0, 0.15, size=3)
    ax = ax + dc[0]
    ay = ay + dc[1]
    az = az + dc[2]
    temp_drift = rng.normal(0, 0.05, size=3)
    ax = ax + temp_drift[0] * t
    ay = ay + temp_drift[1] * t
    az = az + temp_drift[2] * t
    breath = 0.03 * GRAVITY * np.sin(2 * np.pi * 0.3 * t)
    az = az + breath
    return ax, ay, az


def _apply_placement_rotation(
    ax: np.ndarray, ay: np.ndarray, az: np.ndarray,
    placement: str, rng: np.random.Generator,
) -> tuple:
    if placement == "belt":
        return ax, ay, az
    elif placement == "pocket":
        return ax, ay * 0 - az, ay
    else:
        angle = np.deg2rad(rng.uniform(15, 75))
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        return ax, cos_a * ay - sin_a * az, sin_a * ay + cos_a * az


# ===========================================================================
# Fall generation — với overlap
# ===========================================================================
def _gen_fall(
    rng: np.random.Generator,
    n: int,
    direction: str,
    persona: Persona,
    placement: str,
) -> tuple:
    """
    Sinh cú ngã với phân bố lực MỚI:
    - 40% weak   (spike 1.5-2.5g, orientation change 40-60°)  ← KHÓ BẮT
    - 40% medium (spike 3.0-4.5g, orientation change 70-100°)
    - 20% strong (spike 5.0-6.5g, orientation change 100-130°)

    Plus: 20% sessions subclinical falls — chỉ có spike nhỏ ở 1/3 window
    """
    t = np.linspace(0, 1, n)

    # --- Phân bố strength mới (nhiều weak hơn) ---
    r = rng.random()
    if r < 0.40:
        strength = "weak"
        spike_base = rng.uniform(1.5, 2.5) * GRAVITY
        orientation_delta = rng.uniform(40, 60)
    elif r < 0.80:
        strength = "medium"
        spike_base = rng.uniform(3.0, 4.5) * GRAVITY
        orientation_delta = rng.uniform(70, 100)
    else:
        strength = "strong"
        spike_base = rng.uniform(5.0, 6.5) * GRAVITY
        orientation_delta = rng.uniform(100, 130)

    spike_amplitude = spike_base * persona.impact_multiplier

    # --- 20% subclinical falls (cực khó bắt) ---
    is_subclinical = rng.random() < 0.20
    if is_subclinical:
        spike_amplitude *= 0.5
        orientation_delta *= 0.6

    # --- Impact timing ---
    impact_center = float(rng.uniform(0.20, 0.65))
    impact_sigma = float(rng.uniform(0.03, 0.07))
    if strength == "weak":
        impact_sigma *= 1.5

    spike = spike_amplitude * np.exp(-((t - impact_center) ** 2) / (2 * impact_sigma ** 2))

    # --- Post-impact ---
    has_recovery = rng.random() < persona.recovery_chance
    post_start = min(impact_center + impact_sigma * 2.5, 0.85)

    post_scale = {
        "front": 0.35, "back": 0.55, "left": 0.40, "right": 0.45,
    }[direction]

    post_mask = t >= post_start
    if has_recovery:
        recovery_t = np.clip((t - post_start) / 0.35, 0, 1)
        post_mag = (1 - recovery_t) * post_scale * GRAVITY * persona.gravity_scale \
                   + recovery_t * 0.95 * GRAVITY * persona.gravity_scale
    else:
        post_mag = np.full(n, post_scale * GRAVITY * persona.gravity_scale)

    mag = np.ones(n) * GRAVITY * persona.gravity_scale + spike
    mag[post_mask] = post_mag[post_mask]

    # --- Axis decomposition ---
    is_impact = (t >= impact_center - impact_sigma) & (t < impact_center + impact_sigma)

    # Scale by strength (weak → ít thay đổi trục)
    strength_scale = {"weak": 0.6, "medium": 1.0, "strong": 1.3}[strength]

    if direction == "front":
        ax = 0.2 * GRAVITY + 0.6 * GRAVITY * strength_scale * is_impact \
             + 0.7 * GRAVITY * strength_scale * post_mask
        ay = 0.3 * GRAVITY + 0.3 * GRAVITY * strength_scale * is_impact
        az = np.sqrt(np.maximum(mag ** 2 - ax ** 2 - ay ** 2, 1.0))
        az[post_mask] = 0.35 * GRAVITY * persona.gravity_scale
    elif direction == "back":
        ax = 0.15 * GRAVITY + 0.4 * GRAVITY * strength_scale * is_impact
        ay = 0.3 * GRAVITY + 0.6 * GRAVITY * strength_scale * post_mask
        az = np.sqrt(np.maximum(mag ** 2 - ax ** 2 - ay ** 2, 1.0))
        az[post_mask] = 0.55 * GRAVITY * persona.gravity_scale
    elif direction == "left":
        ax = 0.05 * GRAVITY - 0.7 * GRAVITY * strength_scale * post_mask \
             + 0.3 * GRAVITY * strength_scale * is_impact
        ay = 0.25 * GRAVITY + 0.3 * GRAVITY * strength_scale * post_mask
        az = np.sqrt(np.maximum(mag ** 2 - ax ** 2 - ay ** 2, 1.0))
    else:  # right
        ax = 0.05 * GRAVITY + 0.7 * GRAVITY * strength_scale * post_mask \
             + 0.3 * GRAVITY * strength_scale * is_impact
        ay = 0.25 * GRAVITY + 0.3 * GRAVITY * strength_scale * post_mask
        az = np.sqrt(np.maximum(mag ** 2 - ax ** 2 - ay ** 2, 1.0))

    # --- Outlier ---
    if rng.random() < persona.outlier_chance:
        outlier_type = rng.choice(["double_spike", "delayed", "attenuated"])
        if outlier_type == "double_spike":
            second_center = min(impact_center + 0.15, 0.9)
            spike2 = spike_amplitude * 0.5 * np.exp(
                -((t - second_center) ** 2) / (2 * 0.03 ** 2)
            )
            mag = mag + spike2
            ax = ax + 0.3 * GRAVITY * spike2 / GRAVITY
        elif outlier_type == "delayed":
            shift = int(n * 0.15)
            ax = np.roll(ax, shift)
            ay = np.roll(ay, shift)
            az = np.roll(az, shift)
        else:  # attenuated
            ax = ax * 0.5 + 0.5 * np.mean(ax)
            ay = ay * 0.5 + 0.5 * np.mean(ay)

    # --- Sensor noise ---
    noise = persona.noise_scale
    ax += _smooth_noise(rng, n, noise)
    ay += _smooth_noise(rng, n, noise)
    az += _smooth_noise(rng, n, noise)

    # --- Placement + Environmental ---
    ax, ay, az = _apply_placement_rotation(ax, ay, az, placement, rng)
    ax, ay, az = _apply_environmental_drift(rng, ax, ay, az, n)

    # --- Gyro: spike giảm theo strength ---
    bias, drift = _gyro_drift(rng, n, persona.drift_rate)
    strength_factor = {"weak": 0.4, "medium": 1.0, "strong": 1.5}[strength]
    gyro_x = 35 * strength_factor * np.exp(-((t - impact_center) ** 2) / 0.008) \
             + bias[0] + drift[:, 0] + _smooth_noise(rng, n, 0.6)
    gyro_y = 28 * strength_factor * np.exp(-((t - impact_center) ** 2) / 0.012) \
             + bias[1] + drift[:, 1] + _smooth_noise(rng, n, 0.6)
    gyro_z = 45 * strength_factor * np.exp(-((t - impact_center) ** 2) / 0.016) \
             + bias[2] + drift[:, 2] + _smooth_noise(rng, n, 0.6)

    # --- Pitch / roll: biên độ theo strength ---
    pitch_base = -70 + rng.uniform(-8, 8)
    roll_base = 65 + rng.uniform(-8, 8)
    pitch = pitch_base + 20 * (t - 0.5) * strength_scale + rng.normal(0, 1.2, n)
    roll_direction = {
        "front": +1, "back": -1, "left": -1, "right": +1,
    }[direction]
    roll = roll_base + orientation_delta * roll_direction * post_mask \
           + rng.normal(0, 1.2, n)

    return ax, ay, az, gyro_x, gyro_y, gyro_z, pitch, roll


# ===========================================================================
# Non-fall generation — với pseudo-fall MẠNH
# ===========================================================================
def _gen_nonfall(
    rng: np.random.Generator,
    n: int,
    activity: str,
    persona: Persona,
    placement: str,
) -> tuple:
    """
    NON_FALL có pseudo-fall MẠNH hơn v2/v3:
    - Other: 35% sessions có spike 2.0-2.5g (giống weak FALL)
    - Jumping: 35% sessions mạnh (spike 2.5g)
    - Walking: 25% stumble vừa
    """
    t = np.linspace(0, 1, n)
    noise = persona.noise_scale
    g = persona.gravity_scale

    if activity == "Sitting":
        if rng.random() < 0.40:
            stand_center = rng.uniform(0.4, 0.7)
            stand_width = 0.15
            stand_mask = np.abs(t - stand_center) < stand_width
            base = 0.75 * GRAVITY * g
            mag = np.where(stand_mask, 0.95 * GRAVITY * g, base)
            ax = 0.30 * GRAVITY + _smooth_noise(rng, n, noise)
            ay = 0.45 * GRAVITY + _smooth_noise(rng, n, noise)
            az = np.sqrt(np.maximum(mag ** 2 - ax ** 2 - ay ** 2, 1.0))
        else:
            base = 0.75 * GRAVITY * g
            ax = 0.30 * GRAVITY + _smooth_noise(rng, n, noise)
            ay = 0.45 * GRAVITY + _smooth_noise(rng, n, noise)
            az = np.sqrt(np.maximum(base ** 2 - ax ** 2 - ay ** 2, 1.0))
        gyro_x = _smooth_noise(rng, n, 0.5)
        gyro_y = _smooth_noise(rng, n, 0.5)
        gyro_z = _smooth_noise(rng, n, 0.5)
        pitch = -20 + _smooth_noise(rng, n, 1.2)
        roll = 35 + _smooth_noise(rng, n, 1.2)

    elif activity == "Standing":
        base = 1.00 * GRAVITY * g
        ax = 0.65 * GRAVITY + _smooth_noise(rng, n, noise * 0.5)
        ay = 0.20 * GRAVITY + _smooth_noise(rng, n, noise * 0.5)
        az = np.sqrt(np.maximum(base ** 2 - ax ** 2 - ay ** 2, 1.0))
        gyro_x = _smooth_noise(rng, n, 0.5)
        gyro_y = _smooth_noise(rng, n, 0.5)
        gyro_z = _smooth_noise(rng, n, 0.5)
        pitch = -75 + _smooth_noise(rng, n, 1.2)
        roll = 70 + _smooth_noise(rng, n, 1.2)

    elif activity == "Walking":
        base = 1.00 * GRAVITY * g
        step = 0.20 * GRAVITY * np.sin(2 * np.pi * 1.2 * t * 2)
        # 25% stumble mạnh
        if rng.random() < 0.25:
            stumble_center = rng.uniform(0.3, 0.7)
            stumble = rng.uniform(0.6, 0.9) * GRAVITY * np.exp(
                -((t - stumble_center) ** 2) / 0.008
            )
            step = step + stumble
        ax = 0.65 * GRAVITY + step + _smooth_noise(rng, n, noise)
        ay = 0.20 * GRAVITY + _smooth_noise(rng, n, noise)
        az = np.sqrt(np.maximum((base + step) ** 2 - ax ** 2 - ay ** 2, 1.0))
        gyro_x = 8 * np.sin(2 * np.pi * 1.2 * t) + _smooth_noise(rng, n, 0.6)
        gyro_y = _smooth_noise(rng, n, 0.6)
        gyro_z = 5 * np.cos(2 * np.pi * 1.2 * t) + _smooth_noise(rng, n, 0.6)
        pitch = -72 + _smooth_noise(rng, n, 1.2)
        roll = 88 + _smooth_noise(rng, n, 1.2)

    elif activity == "Jumping":
        base = 1.00 * GRAVITY * g
        spikes = np.zeros(n)
        # 35% sessions nhảy mạnh (spike to → giống weak fall)
        is_strong = rng.random() < 0.35
        amp = rng.uniform(2.0, 2.5) if is_strong else rng.uniform(0.6, 1.0)
        for center in (rng.uniform(0.25, 0.35), rng.uniform(0.65, 0.75)):
            spikes += amp * GRAVITY * np.exp(-((t - center) ** 2) / 0.005)
        ax = 0.65 * GRAVITY + spikes * 0.5 + _smooth_noise(rng, n, noise)
        ay = 0.20 * GRAVITY + spikes * 0.4 + _smooth_noise(rng, n, noise)
        az = np.sqrt(np.maximum((base + spikes) ** 2 - ax ** 2 - ay ** 2, 1.0))
        gyro_x = 15 * np.gradient(spikes) + _smooth_noise(rng, n, 0.6)
        gyro_y = _smooth_noise(rng, n, 0.6)
        gyro_z = 12 * np.gradient(spikes) + _smooth_noise(rng, n, 0.6)
        pitch = -70 + _smooth_noise(rng, n, 1.5)
        roll = 75 + _smooth_noise(rng, n, 1.5)

    else:  # "Other" — adversarial mạnh
        base = 1.10 * GRAVITY * g
        # 35% sessions có spike 2.0-2.5g giống weak FALL
        if rng.random() < 0.35:
            impact_center = rng.uniform(0.25, 0.65)
            spike_amp = rng.uniform(2.0, 2.5) * GRAVITY
            spike = spike_amp * np.exp(-((t - impact_center) ** 2) / 0.006)
            recovery_mask = t > impact_center
            recovery_t = np.clip((t - impact_center) / 0.25, 0, 1)
            ax = 0.5 * GRAVITY + spike * 0.6 + _smooth_noise(rng, n, noise)
            ay = 0.3 * GRAVITY + spike * 0.4 + _smooth_noise(rng, n, noise)
            az = np.sqrt(np.maximum((base + spike) ** 2 - ax ** 2 - ay ** 2, 1.0))
            az = np.where(recovery_mask,
                          1.0 * GRAVITY * g + 0.3 * GRAVITY * (1 - recovery_t),
                          az)
        else:
            ax = 0.5 * GRAVITY + 0.4 * GRAVITY * np.sin(2 * np.pi * 0.7 * t) \
                 + _smooth_noise(rng, n, noise)
            ay = 0.3 * GRAVITY + 0.3 * GRAVITY * np.cos(2 * np.pi * 0.5 * t) \
                 + _smooth_noise(rng, n, noise)
            az = np.sqrt(np.maximum(base ** 2 - ax ** 2 - ay ** 2, 1.0))
        gyro_x = 20 * np.sin(2 * np.pi * 0.5 * t) + _smooth_noise(rng, n, 1.2)
        gyro_y = _smooth_noise(rng, n, 1.2)
        gyro_z = 20 * np.cos(2 * np.pi * 0.5 * t) + _smooth_noise(rng, n, 1.2)
        pitch = -60 + 25 * np.sin(2 * np.pi * 0.5 * t) + _smooth_noise(rng, n, 1.5)
        roll = 80 + 25 * np.cos(2 * np.pi * 0.5 * t) + _smooth_noise(rng, n, 1.5)

    # Placement + Environmental
    ax, ay, az = _apply_placement_rotation(ax, ay, az, placement, rng)
    ax, ay, az = _apply_environmental_drift(rng, ax, ay, az, n)

    # Gyro drift
    bias, drift = _gyro_drift(rng, n, persona.drift_rate)
    gyro_x = gyro_x + bias[0] + drift[:, 0]
    gyro_y = gyro_y + bias[1] + drift[:, 1]
    gyro_z = gyro_z + bias[2] + drift[:, 2]

    return ax, ay, az, gyro_x, gyro_y, gyro_z, pitch, roll


# ===========================================================================
# Ghi file
# ===========================================================================
def _write_file(
    path: Path,
    activity: str,
    label: str,
    n_sessions: int,
    rng: np.random.Generator,
    min_samples: int = 25,
    max_samples: int = 50,
) -> None:
    rows = []
    persona_weights = {"young": 0.45, "elderly": 0.35, "heavy": 0.20}
    persona_names = list(persona_weights.keys())
    persona_probs = list(persona_weights.values())

    placement_probs = {"belt": 0.55, "pocket": 0.30, "wrist": 0.15}
    placement_names = list(placement_probs.keys())
    placement_weights = list(placement_probs.values())

    for _ in range(n_sessions):
        session_id = _make_session_id(rng)
        n = int(rng.integers(min_samples, max_samples + 1))

        persona_name = rng.choice(persona_names, p=persona_probs)
        placement = rng.choice(placement_names, p=placement_weights)
        persona = PERSONAS[persona_name]

        if label == "FALL":
            direction = activity.replace("Fall_", "").lower()
            ax, ay, az, gx, gy, gz, pitch, roll = _gen_fall(
                rng, n, direction, persona, placement
            )
        else:
            ax, ay, az, gx, gy, gz, pitch, roll = _gen_nonfall(
                rng, n, activity, persona, placement
            )

        t0 = int(rng.integers(100_000, 5_000_000))
        timestamps = t0 + np.arange(n) * SAMPLE_INTERVAL_MS

        for i in range(n):
            rows.append(
                {
                    "session_id": session_id,
                    "label": activity,
                    "timestamp_ms": int(timestamps[i]),
                    "accel_x(m_s2)": float(ax[i]),
                    "accel_y(m_s2)": float(ay[i]),
                    "accel_z(m_s2)": float(az[i]),
                    "gyro_x(deg_s)": float(gx[i]),
                    "gyro_y(deg_s)": float(gy[i]),
                    "gyro_z(deg_s)": float(gz[i]),
                    "pitch_deg": float(pitch[i]),
                    "roll_deg": float(roll[i]),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"  ✓ {path.name:20s} {n_sessions:3d} sessions, {len(df):5d} rows, "
          f"label={label}, activity={activity}")


# ===========================================================================
# Main
# ===========================================================================
def generate_all(
    output_dir: Path,
    n_fall_per_direction: int = 35,
    n_nonfall_per_activity: int = 35,
    seed: int = 42,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    print(f"===== GENERATE SAMPLE QMI v4 (REALISTIC — FINAL) =====")
    print(f"Output: {output_dir}")
    print(f"Fall sessions / direction : {n_fall_per_direction}")
    print(f"Non-fall sessions / activity: {n_nonfall_per_activity}")
    print(f"Personas: young(45%) / elderly(35%) / heavy(20%) — MIXED")
    print(f"Placements: belt(55%) / pocket(30%) / wrist(15%)")
    print(f"Session length: 25–50 samples")
    print(f"FALL strength: 40% weak / 40% medium / 20% strong")
    print(f"Subclinical falls: 20%")
    print(f"Pseudo-falls: Sitting(40%) / Walking(25%) / Jumping(35%) / Other(35%)")
    print()

    fall_specs = [
        ("fall_front.csv",  "Fall_Front", "FALL"),
        ("fall_back.csv",   "Fall_Back",  "FALL"),
        ("fall_left.csv",   "Fall_Left",  "FALL"),
        ("fall_right.csv",  "Fall_Right", "FALL"),
    ]
    for filename, activity, label in fall_specs:
        _write_file(output_dir / filename, activity, label,
                    n_fall_per_direction, rng)

    nonfall_specs = [
        ("walking.csv",  "Walking",  "NON_FALL"),
        ("sitting.csv",  "Sitting",  "NON_FALL"),
        ("standing.csv", "Standing", "NON_FALL"),
        ("jumping.csv",  "Jumping",  "NON_FALL"),
        ("doing.csv",    "Other",    "NON_FALL"),
    ]
    for filename, activity, label in nonfall_specs:
        _write_file(output_dir / filename, activity, label,
                    n_nonfall_per_activity, rng)

    total = 4 * n_fall_per_direction + 5 * n_nonfall_per_activity
    print()
    print(f"===== DONE =====")
    print(f"Tổng sessions: {total}")
    print(f"FALL     : {4 * n_fall_per_direction}")
    print(f"NON_FALL : {5 * n_nonfall_per_activity}")
    print()
    print("Chạy pipeline:")
    print("    cd src && PYTHONPATH=. python3 train.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fall-per-direction", type=int, default=35)
    parser.add_argument("--nonfall-per-activity", type=int, default=35)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output_dir.exists() and any(args.output_dir.glob("*.csv")):
        if not args.overwrite:
            print(f"⚠️  {args.output_dir} đã có CSV. Dùng --overwrite để ghi đè.")
            return

    generate_all(
        args.output_dir,
        n_fall_per_direction=args.fall_per_direction,
        n_nonfall_per_activity=args.nonfall_per_activity,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()