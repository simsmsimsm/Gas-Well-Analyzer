# Gas Well Correlation Analyzer

A browser-based analytics tool for exploring correlations between temperature, pressure, production rates, and gas composition in well data. Built with Flask and Plotly.js — no database, no build step.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

| Tab | What it does |
|-----|-------------|
| **Scatter** | XY scatter plot with linear regression, 95% confidence band, Pearson/Spearman stats, and optional outlier highlighting |
| **Temp Overview** | Bar chart ranking the Pearson correlation of any temperature column against every other numeric variable — click a bar to drill into Scatter |
| **Correlation Matrix** | Full heatmap of pairwise Pearson r values across all numeric columns, with p-value-aware cell annotations |
| **Time Series** | Multi-series line chart with per-series Y axes and optional rolling average overlay (7 / 14 / 30 / 90-point or custom) |
| **Summary** | Descriptive statistics table (count, mean, std, min, P25, median, P75, max) for all numeric columns |

All five tabs respect the **date range filter** — narrowing the date window re-runs any analysis against the filtered subset without reloading data.

---

## Quick Start

```bash
# 1. Install dependencies (Python 3.10+ recommended)
pip install -r requirements.txt

# 2. Start the server
python app.py
# → http://localhost:5001
```

Open `http://localhost:5001` in your browser. Click **Load Sample Well Data** to explore a built-in 365-day synthetic dataset, or upload your own CSV.

---

## Data Requirements

### Uploading a CSV

- The file must be a standard comma-separated CSV.
- Any column whose values parse as dates (e.g. `2024-01-15`, `01/15/2024`) is automatically detected as the date column and activates the date range filter.
- All remaining numeric columns are available for analysis.
- Non-numeric, non-date columns are ignored.

### Expected column types

| Type | Detection | Example column names |
|------|-----------|----------------------|
| Date | Auto-parsed from any object column that converts cleanly to `datetime` | `Date`, `Timestamp`, `Sample_Date` |
| Temperature | Any numeric column with `temp` or `temperature` in the name (case-insensitive) | `Wellhead_Temp_F`, `Separator_Temperature` |
| Numeric | All other numeric columns | `Gas_Rate_Mcfd`, `Wellhead_Pressure_psi` |

There is no required column naming convention beyond the temperature detection heuristic above. Any numeric CSV will work.

---

## Sample Dataset

The built-in sample simulates 365 days of daily production data for a single gas condensate well, with physically realistic correlations baked in:

| Column | Unit | Description |
|--------|------|-------------|
| `Date` | — | 2023-01-01 to 2023-12-31, daily |
| `Wellhead_Temp_F` | °F | Driven by gas rate and ambient temperature |
| `Separator_Temp_F` | °F | Mostly ambient-driven with a small flow component |
| `Ambient_Temp_F` | °F | Seasonal sinusoidal pattern |
| `Wellhead_Pressure_psi` | psi | Declines ~25% over the year (reservoir depletion) |
| `Tubing_Pressure_psi` | psi | ~92% of wellhead pressure |
| `Casing_Pressure_psi` | psi | ~105% of wellhead pressure |
| `Gas_Rate_Mcfd` | Mcf/d | Declines with reservoir depletion |
| `Condensate_Rate_Bbl` | Bbl/d | CGR × gas rate / 1000 |
| `Water_Rate_Bbl` | Bbl/d | Increases slightly with depletion |
| `CGR_BblMMcf` | Bbl/MMcf | Higher at lower separator temperatures (retrograde) |
| `BTU_Content` | BTU/scf | Driven by heavier hydrocarbon components |
| `Specific_Gravity` | — | Correlates with BTU content |
| `Methane_pct` | mol% | Inversely related to CGR |
| `Ethane_pct` | mol% | Positively related to CGR |
| `Propane_pct` | mol% | Positively related to CGR |
| `CO2_pct` | mol% | ~1.5%, low variance |
| `N2_pct` | mol% | ~0.8%, low variance |
| `H2S_ppm` | ppm | Weakly correlated with wellhead pressure |

### Correlations worth exploring in the sample data

- **Separator_Temp_F → CGR_BblMMcf**: negative (retrograde condensation — colder separator = more liquid dropout)
- **Gas_Rate_Mcfd → Wellhead_Temp_F**: positive (higher flow warms the wellhead)
- **Wellhead_Pressure_psi → Gas_Rate_Mcfd**: strong positive (both decline with depletion)
- **CGR_BblMMcf → Methane_pct**: negative (richer gas has less methane by fraction)

---

## Using the Interface

### 1. Load data
Click **Load Sample Well Data** or drag a CSV onto **Upload CSV**. The sidebar shows the filename and row count once loaded.

### 2. Filter by date (optional)
If a date column is detected, a **Date Range** picker appears. Adjust the From/To fields and click **Reset Range** to restore the full dataset. Every analysis re-filters on the fly — no need to reload.

### 3. Configure the analysis
Each tab shows its own controls in the sidebar:

- **Scatter** — choose X axis, Y axis, an optional colour-by column, and an outlier detection method (IQR fence at 1.5×IQR, or Z-score |z| > 3). Outliers are highlighted in the plot but not removed from the regression.
- **Temp Overview** — choose a temperature column; the chart ranks all other columns by |r|.
- **Correlation Matrix** — no configuration needed; uses all numeric columns.
- **Time Series** — choose the X axis (date column or row index), tick any number of Y columns, and optionally enable a rolling average.
- **Summary** — no configuration needed.

### 4. Click Analyze
Results render in the main panel. The **Scatter** tab additionally shows a statistics panel below the chart with Pearson r, Spearman ρ, R², sample size, and a plain-English interpretation.

### 5. Drill down from Temp Overview
Clicking any bar in the **Temp Overview** chart automatically switches to the **Scatter** tab with the temperature column pre-set as X and the clicked variable as Y, and runs the analysis immediately.

---

## Statistics Reference

| Statistic | Where shown | Interpretation |
|-----------|-------------|----------------|
| **Pearson r** | Scatter, Temp Overview, Matrix | Linear correlation, –1 to +1 |
| **Spearman ρ** | Scatter | Rank-based (monotonic) correlation, robust to non-linearity |
| **R²** | Scatter | Proportion of variance in Y explained by X |
| **p-value** | Scatter, Temp Overview | Significance of r; `*` p<0.05, `**` p<0.01, `***` p<0.001, `ns` not significant |
| **95% CI band** | Scatter | Confidence interval around the regression line |
| **Regression equation** | Scatter | ŷ = slope·x + intercept |

---

## Project Structure

```
Gas Well Analyzer/
├── app.py               # Flask backend — data loading, filtering, analysis routes
├── requirements.txt     # Python dependencies
├── templates/
│   └── index.html       # Single-page shell; loads Plotly.js from CDN
└── static/
    ├── app.js           # All frontend logic — state, tab switching, Plotly rendering
    └── style.css        # Layout and component styles
```

The server holds one dataset in memory at a time (`_store` dict). Data is lost on server restart. This is a single-user local tool; it is not designed for concurrent access or production deployment.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | HTTP server and routing |
| `pandas` | DataFrame handling and date parsing |
| `numpy` | Numerical operations and sample data generation |
| `scipy` | Pearson/Spearman correlation, linear regression, confidence intervals |
| `python-dotenv` | Optional `.env` support for `FLASK_SECRET_KEY` |
| **Plotly.js** (CDN) | Interactive charting in the browser |

---

## Configuration

Create a `.env` file in the project root to override the default Flask secret key:

```
FLASK_SECRET_KEY=your-secret-here
```

The server runs on port **5001** by default. To change it, edit the last line of `app.py`:

```python
app.run(debug=True, port=5001)
```
