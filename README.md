# OTC-X

An innovation that turns the OTC‑X market into a live, map-like radar: it highlights unusual trading activity, liquidity spikes and standout price moves across Swiss unlisted equities—making opportunities easier to spot and the market easier to understand.

## Repository Layout

- `frontend/` – Streamlit dashboard (config, styles, charts, components, layout, and `app.py` orchestrator)
- `backend/` – Data pipeline and operations (`operations/`, `data/`, `logs/`, `pipeline.py`)
- `run_frontend.py` – Convenience launcher for the dashboard
- `run_backend.py` – Convenience runner for the full data pipeline
- `otcx_paths.py` – Shared path helpers for consistent data/log locations
- `tests/` – Baseline unit, integration, and E2E smoke tests

## Usage

### Backend pipeline
```bash
python run_backend.py
```
Runs the full scrape → fetch → consolidate → metrics pipeline. Output data is written to `backend/data/`.

### Frontend dashboard
```bash
streamlit run frontend/app.py
# or
python run_frontend.py
```
Loads the dashboard against the parquet data in `backend/data/`.

### Tests
```bash
pytest
```

## Notes
- Data files live in `backend/data/` and are referenced via dynamic paths (`otcx_paths.py`) so the app works regardless of working directory.
- Logs from download jobs are written to `backend/logs/` (log files are git-ignored; the directory is kept via `.gitkeep`).
