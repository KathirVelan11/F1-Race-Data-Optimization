# Data Directory

This directory contains the datasets used by the F1 Race Strategy & Performance Optimization project.

## Directory Layout

```
data/
├── raw/
│   ├── kaggle/                 # Raw Kaggle historical tables (1950–2024)
│   │   ├── circuits.csv
│   │   ├── constructor_results.csv
│   │   ├── constructor_standings.csv
│   │   ├── constructors.csv
│   │   ├── driver_standings.csv
│   │   ├── drivers.csv
│   │   ├── lap_times.csv
│   │   ├── pit_stops.csv
│   │   ├── qualifying.csv
│   │   ├── races.csv
│   │   ├── results.csv
│   │   ├── seasons.csv
│   │   ├── sprint_results.csv
│   │   └── status.csv
│   └── fastf1/                 # Flat per-lap FastF1 extracts (2018–2024)
│       ├── f1_data_2018_2021.csv
│       └── f1_data_2022_2024.csv
└── processed/
    └── combined_dataset.csv    # Master joined dataset (161,443 rows, 12MB)
```

## Master Combined Dataset (`data/processed/combined_dataset.csv`)

The master dataset joins Kaggle lap times, pit stops, and race results with FastF1 tyre compound, tyre life, and stint data across the modern hybrid era (2018–2024).

### Schema

| Column | Type | Description |
| :--- | :--- | :--- |
| `raceId` | int | Kaggle unique race identifier |
| `Year` | int | Season year (2018–2024) |
| `Race` | string | Grand Prix event name |
| `Driver` | string | 3-letter driver code (e.g. `VER`, `HAM`, `LEC`) |
| `Team` | string | Constructor name |
| `Lap` | int | Lap number within race |
| `LapTime` | string | Recorded lap time (`M:SS.sss` format) |
| `Position` | int | Track position at end of lap |
| `Compound` | string | Tyre compound (`SOFT`, `MEDIUM`, `HARD`, etc.) |
| `TyreLife` | float | Age of current tyre set in laps |
| `Stint` | float | Current stint number |
| `pit_duration` | float | Pit stop duration in seconds (`NaN` if no stop) |

### Integrity Policy

- **Do NOT re-download or duplicate:** The dataset is already built and validated.
- **Consumption:** Both Scope 1 (MILP) and Scope 2 (Goal Programming) consume this data through the common loader interface `src/f1_optimizer/common/data/dataset_loader.py`.
- **Rebuilding:** If raw sources ever need re-processing, use `python scripts/build_dataset.py`.
