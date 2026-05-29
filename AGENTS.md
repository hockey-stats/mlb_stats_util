# Agent Instructions - MLB Stats Utility

This repository provides utility scripts for fetching and calculating detailed MLB player statistics using `pybaseball` and `polars`. It is designed to bridge the gap between various data sources (Baseball-Reference, FanGraphs, Statcast) and provide a unified, cleaned dataset for analysis.

## Project Overview

- **Language:** Python 3.12+ (utilizing modern typing and performance features)
- **Package Manager:** `uv` (faster and more reliable than traditional pip/venv)
- **Core Libraries:** 
    - `pybaseball`: Primary interface for fetching data from Baseball-Reference, FanGraphs, and Statcast.
    - `polars`: High-performance DataFrame library used for all data manipulation. Pandas should be avoided for internal logic.

## Build, Lint, and Test Commands

### Environment Setup
The project uses `uv` for dependency management. To set up the environment and install dependencies:
```bash
uv sync
```

### Execution
Run the statistics generation scripts directly using `uv run`. This ensures the correct virtual environment is used:
```bash
# Generate detailed batter stats (wOBA, wRC+, xwOBA)
uv run python src/get_detailed_batter_stats.py

# Generate detailed pitcher stats (K%, BB%, K-BB%, xERA)
uv run python src/get_detailed_pitcher_stats.py
```

### Testing
There is currently no automated test suite (e.g., `pytest`). Agents should verify changes by:
1. Running the relevant script in `src/`.
2. Verifying the printed Polars DataFrame output for correctness (e.g., no nulls in critical columns, reasonable stat values).
3. Ensuring the `if __name__ == "__main__":` block is configured for a valid year (usually the current or most recent season).

### Linting
No formal linting configuration (`ruff.toml` or `.flake8`) exists. However, code should adhere to PEP 8. Agents are encouraged to use `ruff` if available:
```bash
uv run ruff check .
```

## Code Style & Guidelines

### 1. Imports
- **Standard Library:** `typing`, `datetime`, etc.
- **Third-Party:** 
    - `import pybaseball as pyb`
    - `import polars as pl`
- **Ordering:** Standard library first, then third-party, then local modules.

### 2. Typing
- **Mandatory Type Hints:** All function signatures must include type hints for parameters and return values.
- **Variable Hints:** Use type hints for complex variables like mappings or DataFrames to aid editor completion and static analysis.
- **Polars Types:** Use `pl.DataFrame` and `pl.Series` where appropriate. Use `Any` sparingly.

### 3. Naming Conventions
- **General:** `snake_case` for functions, variables, and modules.
- **Statistical Constants:** Follow domain-specific casing for formulas (e.g., `wBB`, `wOBAScale`, `runsPerPA`) to maintain consistency with FanGraphs "Guts" definitions.
- **DataFrames:** Use `df` for intermediate DataFrames and `final_df` or `results_df` for the end product.

### 4. Polars Usage
- **Vectorization:** Prefer vectorized operations over row-wise operations (`map_elements`).
- **Row-wise Logic:** When row-wise logic is necessary (e.g., complex mapping or multi-column formulas), use `pl.struct(pl.all()).map_elements(func, return_dtype=...)`.
- **Joins:** Always specify `how` and `on` explicitly in `df.join()`.
- **Floating Point:** Round statistical floats to 3 significant figures using `.round_sig_figs(3)` for readability.

### 5. Documentation
- **Style:** Use Sphinx/reStructuredText style docstrings.
- **Content:** Every function should have a brief description, `:param type name: description`, and `:return type: description`.
- **In-line Comments:** Use sparingly to explain *why* a specific statistical formula or mapping adjustment is being made.

### 6. Error Handling
- **Specific Exceptions:** Raise or catch specific exceptions like `KeyError` or `ValueError`.
- **Data Mappings:** Be proactive about missing data in team mappings. If a team or park factor is missing, print the offending keys to `stdout` to assist in debugging.
- **Fallbacks:** Implement fallback logic where possible (e.g., checking the other league if a player's team mapping fails due to a mid-season trade).

### 7. Data Source Peculiarities
- **Player Names:** Names fetched from Baseball-Reference often contain special characters or escape sequences. Use the following cleaning pattern:
  ```python
  name.encode('latin-1').decode('unicode_escape').encode('latin-1').decode('utf-8')
  ```
- **Team IDs:** Be aware of different ID systems (Baseball-Reference vs. Statcast/MLB ID). `mlbID` should often be renamed to `player_id` or `playerID` for consistency during joins.
- **Data Latency:** Statcast expected stats (xwOBA, xERA) might not be available for the current day's games immediately. Scripts should handle potentially empty joins gracefully.
- **Bref Column Names:** Baseball-Reference dataframes often have names that overlap with Statcast (e.g., `BA` vs `AVG`). Always verify column names after a join to ensure the desired metric is being used.

### 8. Statistical Calculations
- **wOBA:** Weighted On-Base Average. Calculated using constants from FanGraphs. Formula: `((wBB * uBB) + (wHBP * HBP) + (w1B * 1B) + (w2B * 2B) + (w3B * 3B) + (wHR * HR)) / (AB + uBB + SF + HBP)`.
- **wRC+:** Weighted Runs Created Plus. Requires park factors and league average wOBA/runs per PA.
- **xERA:** Expected ERA based on Statcast data. Fetched separately and joined on `player_id`.
- **K-BB%:** Strikeout rate minus walk rate. A key metric for pitcher evaluation, calculated as `(SO/BF * 100) - (BB/BF * 100)`.

## Common Pitfalls
- **Team Mapping:** Baseball-Reference uses city names (e.g., "Chicago") which can refer to two teams (Cubs/White Sox). Always use the `Lev` column (AL/NL) to differentiate.
- **Multi-team Players:** Players traded during the season may appear with "TOT" or multiple entries. The current logic handles this by taking the last team in a comma-separated string.
- **Park Factors:** Park factors are currently hardcoded in a mapping. If a team is missing, the script will raise a `KeyError`.
- **Data Conversion:** `pybaseball` returns pandas DataFrames. Always convert to Polars immediately using `pl.from_pandas(df)`.

## Task-Specific Guidance

### Adding a New Statistic
When adding a new metric:
1. Identify the source columns needed from the raw data.
2. If the calculation is complex, create a standalone function with type hints and docstrings.
3. Use `df.with_columns()` to add the new metric.
4. Update the selection list at the end of the `get_detailed_*_stats` functions to include the new column.

### Modifying Team Mappings
If a team moves or a new abbreviation is needed:
1. Update `get_team_name` in both batter and pitcher scripts (they currently share similar logic but are independent).
2. Update `get_fg_abbreviation` to ensure consistency with FanGraphs-based tools or exports.

## Repository Structure

- `src/`: Core logic and scripts.
    - `get_detailed_batter_stats.py`: Calculations for wOBA, wRC+, and integration with Statcast xwOBA.
    - `get_detailed_pitcher_stats.py`: Calculations for K-BB% and integration with Statcast xERA.
- `pyproject.toml`: Project metadata and dependency list.
- `uv.lock`: Deterministic dependency lockfile.
- `README.md`: Basic project overview.

## Future Improvements
- Consolidate shared logic (like team mapping) into a `utils.py` module.
- Implement a `pytest` suite to verify statistical calculations against known benchmarks.
- Add support for historical park factors (currently using static mappings).

