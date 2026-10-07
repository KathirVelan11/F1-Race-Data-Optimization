# Backend Service (FastAPI)

The backend service serves as an asynchronous, type-safe API bridge between the React frontend and the optimization core (`f1_optimizer`).

## Architecture Principles

1. **Thin API Layer:** No mathematical models or solver logic are implemented inside FastAPI route handlers. All computations delegate to `f1_optimizer.scope1`, `f1_optimizer.scope2`, or `f1_optimizer.integration`.
2. **Asynchronous & Type-Safe:** Built with FastAPI and Pydantic v2 schemas for robust request validation and OpenAPI auto-documentation.
3. **Data Delegation:** Reads race data through `f1_optimizer.common.data.DatasetLoader`.

## Planned API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/races/seasons` | Available seasons (2018–2024) |
| `GET` | `/api/races?year={year}` | Available Grand Prix races for season |
| `GET` | `/api/races/{year}/{race_name}/drivers` | Drivers who competed in the selected race |
| `GET` | `/api/races/{year}/{race_name}/analysis` | Preprocessed race statistics, degradation curves, pit loss |
| `POST` | `/api/scope1/optimize` | Runs Scope 1 MILP (Fastest Strategy) |
| `POST` | `/api/scope2/optimize` | Runs Scope 2 Goal Programming (Balanced Strategy) |
| `POST` | `/api/compare` | Runs both scopes and returns side-by-side trade-off analysis |
| `GET` | `/api/validation/{year}/{race_name}/{driver}` | Compares predicted strategy with actual historical results |

## Running the Backend (Future Phase)

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```
