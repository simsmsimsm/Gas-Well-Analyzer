# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
pip install -r requirements.txt
python app.py
# Serves at http://localhost:5001
```

The server runs in debug mode (auto-reload on save). There are no tests, no build step, and no linter configured.

## Architecture

Single-file Flask backend (`app.py`) + a plain-JS frontend. No frameworks, no bundler.

### Backend (`app.py`)

- **In-memory store** — `_store` dict holds one `pd.DataFrame` and a filename. Single-user; data is lost on server restart.
- **Data helpers** — `_df()` returns raw store; `_filtered_df(body)` applies `date_from`/`date_to` from the JSON request body before returning the frame. All analysis routes call `_filtered_df`.
- **`_generate_sample()`** — produces a 365-day synthetic well dataset (pressures, temperatures, rates, gas composition) with realistic correlations baked in via numpy.
- **Analysis routes** — all POST (or GET+POST for matrix/summary): `/api/scatter`, `/api/temp-overview`, `/api/matrix`, `/api/timeseries`, `/api/summary`. Stats are computed with `scipy.stats` (Pearson, Spearman, `linregress`, confidence bands).

### Frontend (`static/app.js`, `templates/index.html`, `static/style.css`)

- Global state object `S` holds the active tab, `/api/info` response, and per-tab column selections.
- **Tab flow**: switching tabs calls `buildControls()` (rebuilds sidebar inputs) then waits for the user to click **Analyze**, which dispatches to `run<Tab>()`.
- All charts rendered with **Plotly.js** (CDN, no local install). `Plotly.react()` is used for updates to avoid full redraws.
- `dateRange()` helper reads the date pickers and spreads `{date_from, date_to}` into every API request body — this is how the date filter propagates to every analysis.
- The **Temp Overview** chart wires a `plotly_click` handler to pre-fill scatter controls and switch tabs automatically.

### Data flow for a typical analysis

1. User loads data → `GET /api/sample` or `POST /api/upload` → `GET /api/info` populates `S.info` and the sidebar.
2. User adjusts date pickers / column selects → clicks **Analyze**.
3. Frontend POSTs to the relevant route with `{...columnSelections, ...dateRange()}`.
4. Backend calls `_filtered_df(body)`, runs stats, returns JSON.
5. Frontend renders via Plotly.

## Key conventions

- Column detection is name-based: temperature columns contain `"temp"` or `"temperature"` (case-insensitive); date columns are detected by dtype (`datetime64`).
- `esc()` in JS is the XSS sanitiser — use it for any user-supplied string rendered into innerHTML.
- New analysis routes should follow the pattern: accept POST, call `_filtered_df(request.get_json(force=True))`, return `jsonify(...)`.
