# F1 Race Strategy Optimization - Run Guide

This project optimizes Formula 1 race strategy using a Python backend and a React frontend.

## 1. Prerequisites

Make sure the following are installed on your machine:

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- Git

## 2. Clone and open the project

```bash
git clone <your-repository-url>
cd F1-Race-Data-Optimization-main
```

## 3. Create the Python environment

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If the project uses `uv` instead of `pip`, you can also use:

```bash
uv sync
```

## 4. Start the backend

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

API docs will be available at:

- http://localhost:8000/docs
- http://localhost:8000/redoc

## 5. Start the frontend

Open a second terminal and run:

```bash
cd frontend
npm install
npm run dev
```

Then open:

- http://localhost:5173/

## 6. Useful project commands

### Run backend tests

```bash
source .venv/bin/activate
pytest -q
```

### Run frontend build check

```bash
cd frontend
npm run build
```

## 7. Project structure summary

- `backend/` - FastAPI application and API routes
- `src/f1_optimizer/` - optimization models and solver logic
- `data/` - processed and raw race datasets
- `frontend/` - React + Vite dashboard
- `tests/` - validation and regression tests
- `docs/` - project architecture and analysis documents

## 8. Notes

- Do not commit local environment folders such as `.venv/`
- Do not commit generated caches or temporary artifacts
- Do not commit PDF or presentation files unless specifically required by the project brief

## 9. Recommended production workflow

```bash
git checkout implementation
git add .
git commit -m "Add implementation and run guide"
git push -u origin implementation
```
