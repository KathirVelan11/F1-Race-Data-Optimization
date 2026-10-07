"""
Builds the master F1 dataset from raw sources only -- no intermediate
files, one script, raw -> processed.

Inputs  (data/raw/):
  kaggle/*.csv        Raw Kaggle F1 tables (races, results, pit_stops,
                       lap_times, drivers, constructors).
  fastf1/*.csv         Flat per-lap FastF1 extracts (tyre compound, tyre
                       age, stint, position) already pulled from the
                       FastF1 API -- one file per year-range.

Output (data/processed/):
  combined_dataset.csv  Lap-by-lap master dataset: Kaggle lap times/pit
                         stops/results joined with FastF1 tyre data.
"""
import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'raw')
KAGGLE_DIR = os.path.join(RAW_DIR, 'kaggle')
FASTF1_DIR = os.path.join(RAW_DIR, 'fastf1')
PROCESSED_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'processed')
os.makedirs(PROCESSED_DIR, exist_ok=True)

# All 22 rounds of the 2022 season now have FastF1 data.
RACES_2022_AVAILABLE = [
    'Bahrain Grand Prix', 'Saudi Arabian Grand Prix', 'Australian Grand Prix',
    'Emilia Romagna Grand Prix', 'Miami Grand Prix', 'Spanish Grand Prix',
    'Monaco Grand Prix', 'Azerbaijan Grand Prix', 'Canadian Grand Prix',
    'British Grand Prix', 'Austrian Grand Prix', 'French Grand Prix',
    'Hungarian Grand Prix', 'Belgian Grand Prix', 'Dutch Grand Prix',
    'Italian Grand Prix', 'Singapore Grand Prix', 'Japanese Grand Prix',
    'United States Grand Prix', 'Mexico City Grand Prix',
    'São Paulo Grand Prix', 'Abu Dhabi Grand Prix',
]

print("Loading raw Kaggle tables...")
races = pd.read_csv(f'{KAGGLE_DIR}/races.csv')
results = pd.read_csv(f'{KAGGLE_DIR}/results.csv')
pit_stops = pd.read_csv(f'{KAGGLE_DIR}/pit_stops.csv')
lap_times = pd.read_csv(f'{KAGGLE_DIR}/lap_times.csv')
drivers = pd.read_csv(f'{KAGGLE_DIR}/drivers.csv')
constructors = pd.read_csv(f'{KAGGLE_DIR}/constructors.csv')

print("Loading raw FastF1 lap extracts...")
fastf1_1821 = pd.read_csv(f'{FASTF1_DIR}/f1_data_2018_2021.csv')
fastf1_2224 = pd.read_csv(f'{FASTF1_DIR}/f1_data_2022_2024.csv')
fastf1_22 = fastf1_2224[(fastf1_2224['Year'] == 2022) & (fastf1_2224['Race'].isin(RACES_2022_AVAILABLE))]
fastf1_23_24 = fastf1_2224[fastf1_2224['Year'].isin([2023, 2024])]
fastf1_data = pd.concat([fastf1_1821, fastf1_22, fastf1_23_24], ignore_index=True)
fastf1_data['Lap'] = fastf1_data['Lap'].astype(int)
print(f"  2018-2021: {len(fastf1_1821):,} rows")
print(f"  2022 ({fastf1_22['Race'].nunique()} races: {sorted(fastf1_22['Race'].unique())}): {len(fastf1_22):,} rows")
print(f"  2023-2024: {len(fastf1_23_24):,} rows")

# Restrict Kaggle races to the years/races we actually have FastF1 data for
years_in_scope = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
races_scope = races[races['year'].isin(years_in_scope)].copy()
races_scope = races_scope[(races_scope['year'] != 2022) | (races_scope['name'].isin(RACES_2022_AVAILABLE))]

lap_times = lap_times.merge(drivers[['driverId', 'code']], on='driverId', how='left')
lap_times_scope = lap_times[lap_times['raceId'].isin(races_scope['raceId'])].copy()
pit_stops_scope = pit_stops[pit_stops['raceId'].isin(races_scope['raceId'])].copy()
lap_times_scope = lap_times_scope.merge(races_scope[['raceId', 'year', 'name']], on='raceId', how='left')
lap_times_scope['lap'] = lap_times_scope['lap'].astype(int)

print("\nMerging Kaggle lap times with FastF1 tyre data...")
merged = lap_times_scope.merge(
    fastf1_data,
    left_on=['year', 'name', 'code', 'lap'],
    right_on=['Year', 'Race', 'Driver', 'Lap'],
    how='inner'
)

# Attach pit stop info -- join directly on lap == pit_lap so each lap-row
# only ever matches its OWN pit stop (if any), with no duplication.
pit_small = pit_stops_scope[['raceId', 'driverId', 'lap', 'duration']].rename(columns={'duration': 'pit_duration'})
merged = merged.merge(pit_small, on=['raceId', 'driverId', 'lap'], how='left')

# Attach constructor name via results
res_small = results[['raceId', 'driverId', 'constructorId']].drop_duplicates()
merged = merged.merge(res_small, on=['raceId', 'driverId'], how='left')
constructors_renamed = constructors[['constructorId', 'name']].rename(columns={'name': 'Team'})
merged = merged.merge(constructors_renamed, on='constructorId', how='left')

final_cols = ['raceId', 'year', 'Race', 'code', 'Team', 'lap', 'time', 'position', 'Compound', 'TyreLife', 'Stint', 'pit_duration']
merged_final = merged[final_cols].rename(columns={
    'code': 'Driver', 'time': 'LapTime', 'position': 'Position', 'lap': 'Lap', 'year': 'Year'
})

output_path = os.path.join(PROCESSED_DIR, 'combined_dataset.csv')
merged_final.to_csv(output_path, index=False)
print(f"\nSaved: {output_path}")
print(f"Rows: {len(merged_final):,}")
print(f"Columns: {list(merged_final.columns)}")
print(f"Year breakdown:\n{merged_final['Year'].value_counts().sort_index()}")
