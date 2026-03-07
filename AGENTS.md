# AGENTS.md

This file provides guidance for agentic coding agents working in this repository.

## Project Overview

Post-race Formula 1 analysis toolkit. Loads race data via FastF1, computes performance metrics, generates predictions, and serves results via a Streamlit dashboard. Blog-ready chart exports for a separate Astro-based GitHub Pages site.

This is a learning project — educational focus, not production-grade. Prioritise clarity and correctness over abstraction.

---

## Build / Lint / Test Commands

### Package Management (uses uv)

```bash
uv sync                                  # Install all dependencies from lockfile
uv add <package>                         # Add new dependency
uv run <command>                         # Run any command in the environment
```

### Running the Application

```bash
uv run streamlit run dashboard/app.py    # Run Streamlit dashboard
uv run jupyter lab                       # Run Jupyter notebooks
uv run python scripts/post_race_etl.py   # Post-race data loading
uv run python scripts/backfill_season.py # Bulk historical data load
uv run python scripts/export_blog_charts.py  # Export PNGs for blog
```

### Testing

> **Note**: No test framework is currently set up. When adding tests:
> - Use `pytest` as the test framework
> - Place tests in a `tests/` directory at the project root
> - Run a single test: `uv run pytest tests/test_file.py::test_function_name`
> - Run all tests: `uv run pytest tests/`

### Code Quality

> **Note**: No linter/formatter is currently configured. When adding:
> - Use `black` for formatting and `ruff` for linting
> - Run format: `uv run black .`
> - Run lint: `uv run ruff check .`

---

## Code Style Guidelines

### General Principles

- **Prefer explicit over clever** — this is a learning project
- **Type hints required** on all `src/` functions
- **Docstrings required** on public functions (one-liner minimum)
- No logic in dashboard pages — they call `src/` and `components/charts.py`

### Imports

- Use absolute imports from package root: `from src import loader`
- Group imports in this order: stdlib, third-party, local
- Sort alphabetically within groups

```python
import pandas as pd
from typing import Optional

import fastf1

from src import metrics, strategy
```

### Formatting

- 4 spaces for indentation (no tabs)
- Maximum line length: 100 characters
- Use trailing commas in multi-line calls

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `loader.py` |
| Functions | snake_case | `calculate_degradation()` |
| Classes | PascalCase | `RaceSession` |
| Constants | UPPER_SNAKE_CASE | `FUEL_CORRECTION = 0.06` |
| Variables | snake_case | `lap_times` |

### Type Hints

- Use `Optional[X]` instead of `X | None` for Python 3.9 compatibility
- Always specify return types for functions

```python
def calculate_pace(lap_times: pd.Series, fuel_effect: float = 0.06) -> Optional[float]:
    """Calculate average pace for a stint."""
    ...
```

### Error Handling

- Use specific exceptions, not bare `except:`
- Add context to errors with custom messages

```python
try:
    session.load()
except fastf1.api.DataNotAvailableError as e:
    raise DataLoadError(f"Failed to load session: {e}") from e
```

### Data Conventions

**FastF1 Caching**: Always enable before session load:
```python
fastf1.Cache.enable_cache('data/f1_cache')
```

**Lap Filtering**: Use `pick_quicklaps(threshold=1.07)` for pace analysis, `pick_accurate()` for timing-critical analysis. Filter out pit laps: `PitInTime.isna() & PitOutTime.isna()`

**Fuel Correction**: ~0.06s/lap improvement from fuel burn

**Cross-Race Comparison**: Use percentage gap, not raw times:
```python
pct_gap = 100 * (driver_time - leader_time) / leader_time
```

### File Organization

```
src/                     # Core logic — all reusable functions
├── loader.py            # FastF1 session loading, caching
├── metrics.py           # Degradation, pace calculations
├── strategy.py          # Stint analysis, undercut detection
├── prediction.py        # Scoring model, Elo ratings
├── circuit.py           # Circuit classification
└── export.py            # Chart export helpers

dashboard/               # Streamlit app
├── app.py               # Entry point
├── pages/               # Dashboard pages
└── components/charts.py # Shared visualisation

scripts/                 # ETL and export scripts
notebooks/               # Ad-hoc exploration only
```

### Dashboard Pages

- No business logic in dashboard pages
- Import and call functions from `src/` and `dashboard/components/charts.py`
- Keep pages thin — they should render charts

---

## Architecture and Data Notes

### Data Sources

- **FastF1** (primary): 2018–present session data
- **Jolpica-F1**: Pre-2018 historical data only
- **OpenF1/F1DB**: Not currently used

### Data Storage

- **SQLite** (`data/f1.db`): Processed race data, cross-race queries
- **Parquet** (`data/processed/`): Per-race lap data
- **FastF1 cache** (`data/f1_cache/`): Download cache only

### Two-Repo Setup

- This repo: Analysis workbench
- `f1-blog` repo: Astro-based GitHub Pages site
- `exports/` folder: PNGs copied to blog's `src/assets/`

---

## Common Workflows

### Post-Race Analysis

1. Run `scripts/post_race_etl.py` after the race
2. Open dashboard for analysis
3. Run `scripts/export_blog_charts.py` for blog PNGs
4. Write post in `f1-blog` repo

### Adding New Analysis

1. Add function to appropriate `src/` module
2. Add tests to `tests/` (create if needed)
3. Update dashboard page or create new page in `dashboard/pages/`
4. Run lint and typecheck
