# F1 Dataset Merge Map

How Kaggle's historical tables and FastF1's tyre telemetry combine into one lap-by-lap dataset (161,443 rows): `data/processed/combined_dataset.csv`.

## Raw inputs used (8 of 16 files)

**Kaggle source:**
- `races.csv` — scopes which races (2018–2024) are in play
- `lap_times.csv` — 589,081 rows, the backbone table
- `drivers.csv` — driverId → 3-letter code
- `pit_stops.csv` — 11,371 rows, pit lap + duration
- `results.csv` — driver → constructorId per race
- `constructors.csv` — constructorId → team name

**FastF1 source:**
- `f1_data_2018_2021.csv` — 87,192 rows, compound/tyre life/stint
- `f1_data_2022_2024.csv` — 74,601 rows, compound/tyre life/stint

## Merge sequence — 5 joins

1. **Attach driver codes** (left join) — `lap_times` + `drivers` on `driverId` → adds the 3-letter code (e.g. `VER`) each lap row needs to later match FastF1.

2. **Attach year & race name** (left join) — `lap_times` + `races` (scoped to 2018–2024) on `raceId` → adds `year` and race `name`.

3. **Core fusion: Kaggle × FastF1** (inner join) — composite key `(year, race name, driver code, lap)`. This is the only step that actually merges the two independent sources. A lap survives only if **both** sides have it, which is why the final row count (161,443) is smaller than Kaggle's full 2018–2024 lap count.

4. **Attach pit stop duration** (left join) — `+ pit_stops` on `(raceId, driverId, lap)` → only the exact pit lap gets a `pit_duration` value; every other lap gets `NaN`.

5. **Attach team name** (left join × 2) — `+ results` on `(raceId, driverId)` → `constructorId`, then `+ constructors` on `constructorId` → `Team`.

## Output

`combined_dataset.csv` — 161,443 rows × 12 columns: `raceId, Year, Race, Driver, Team, Lap, LapTime, Position, Compound, TyreLife, Stint, pit_duration`.

See the main [README](../../README.md#final-dataset-structure-combined_datasetcsv) for the full column reference.
