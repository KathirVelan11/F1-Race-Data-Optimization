# Frontend Architecture (React + TypeScript + Vite)

The frontend for the F1 Race Strategy & Performance Optimization project provides an interactive dashboard designed specifically for Formula 1 strategy evaluation and Operations Research demonstrations.

## Planned Screens & Pages

1. **Dashboard / Home (`src/pages/DashboardPage.tsx`):**
   - High-level overview of F1 pit strategy trade-offs.
   - Quick-start navigation to Scope 1 (MILP) and Scope 2 (Goal Programming).
2. **Race Selection & Analysis (`src/pages/RaceAnalysisPage.tsx`):**
   - Select season (2018–2024), Grand Prix, and driver.
   - View empirical tyre degradation curves, pit-stop historical distributions, and lap time scatter plots.
3. **Scope 1 — Fastest Strategy (`src/pages/Scope1Page.tsx`):**
   - Configure MILP constraints (max stops, min stint length, pit loss $P$).
   - Execute MILP solve.
   - Display optimal pit laps, tyre compound assignment per stint, and minimum race time $T^*$.
4. **Scope 2 — Balanced Strategy (`src/pages/Scope2Page.tsx`):**
   - Interactive weight sliders for Team Priorities ($w_1$ Time, $w_2$ Pit stops, $w_3$ Degradation).
   - Execute Goal Programming solve.
   - Display balanced stints, deviation analysis ($d_1^+, d_2^+, d_3^+$), and trade-offs.
5. **Strategy Comparison (`src/pages/ComparisonPage.tsx`):**
   - Side-by-side visual comparison of Scope 1 vs Scope 2 stints.
   - Delta breakdown: extra time vs pit stops avoided vs tyre wear conserved.
6. **Model Validation (`src/pages/ValidationPage.tsx`):**
   - Ground truth comparison against official Kaggle `results.csv` and `pit_stops.csv`.
   - Percentage accuracy, residual error, and actual vs predicted stint timeline.

## Component Directory Map (`src/components/`)

- `RaceSelector/`: Dropdowns for season, race, and driver selection.
- `RaceSummary/`: High-level event metadata (circuit, total laps, conditions).
- `TyreDegradationChart/`: Scatter/line charts of degradation curves per compound.
- `PitStopTimeline/`: Pit stop history and pit window visualization.
- `StrategyTimeline/`: Stint Gantt-style timeline showing tyre compound colors (Soft: Red, Medium: Yellow, Hard: White).
- `MetricCard/`: Stat display cards for Total Time, Stint Counts, Degradation Index, Solver Duration.
- `StrategyComparison/`: Side-by-side diff matrix comparing MILP vs Goal Programming.
- `WeightSelector/`: Sliders / normalized inputs for Goal Programming priority weights.
- `OptimizationStatus/`: Status badges (OPTIMAL, SOLVING, INFEASIBLE).
- `ValidationPanel/`: Actual vs Predicted metrics table with percentage deviation.

## Service Layer (`src/services/`)

- `api.ts`: Central Axios / Fetch API client communicating with the FastAPI backend.
- `raceService.ts`: Fetching race lists, summaries, and lap data.
- `optimizationService.ts`: Triggering Scope 1, Scope 2, and Comparison runs.
- `validationService.ts`: Fetching historical ground truth data.

## Running the Frontend (Future Phase)

```bash
npm run dev
```
