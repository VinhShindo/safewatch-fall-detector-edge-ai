# SafeWatch Dataset EDA Report

Generated: 2026-09-17T06:43:50.233244+00:00

## Dataset layout

The merged raw data keeps QMI and WEDA-FALL separate under `data/raw/merge` because their raw CSV schemas differ. This EDA focuses on WEDA-FALL 5 Hz accelerometer files, which are used by the training pipeline.

## QMI

- CSV files: 9
- Total rows: 5425
- Total sessions: 175

### QMI file summary

```text
          file  rows  sessions     labels
     doing.csv  1054        34      Other
 fall_back.csv   434        14  Fall_Back
fall_front.csv   465        15 Fall_Front
 fall_left.csv   341        11  Fall_Left
fall_right.csv   434        14 Fall_Right
   jumping.csv   217         7   Standing
   sitting.csv  1054        34    Sitting
  standing.csv   403        13   Standing
   walking.csv  1023        33    Walking
```

## WEDA-FALL

- CSV files: 969
- Total rows: 60464

### WEDA file summary

```text
                                                                                                  file  rows activity_folder                                                   columns
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U01_R01_accel.csv    95             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U01_R02_accel.csv    94             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U01_R03_accel.csv    91             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U02_R01_accel.csv   135             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U02_R02_accel.csv   140             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U02_R03_accel.csv   130             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U03_R01_accel.csv    78             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U03_R02_accel.csv    65             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U03_R03_accel.csv    66             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U04_R01_accel.csv    98             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U04_R02_accel.csv   100             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U04_R03_accel.csv    91             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U05_R01_accel.csv    93             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U05_R02_accel.csv    96             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U05_R03_accel.csv   120             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U06_R01_accel.csv    73             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U06_R02_accel.csv    70             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U06_R03_accel.csv    82             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U07_R01_accel.csv    85             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U07_R02_accel.csv    99             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U07_R03_accel.csv    90             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U08_R01_accel.csv   149             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U08_R02_accel.csv   150             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U08_R03_accel.csv   130             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U09_R01_accel.csv    82             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U09_R02_accel.csv    77             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U09_R03_accel.csv    72             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U10_R01_accel.csv    82             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U10_R02_accel.csv    87             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
/home/vinh_shindo/safewatch-fall-detector-edge-ai/data/raw/WEDA-FALL/dataset/5Hz/D01/U10_R03_accel.csv   102             D01 accel_time_list, accel_x_list, accel_y_list, accel_z_list
```

## Interpretation

WEDA-FALL is used for general pretraining and QMI is used for person/sensor-specific adaptation. Keep validation and test sessions separated by session or user to avoid window leakage.
