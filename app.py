import json
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from scipy import stats as sp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "gwanalyzer-dev")

# Single-user in-memory store
_store: dict = {"df": None, "filename": ""}


# ---------------------------------------------------------------------------
# Sample data generator
# ---------------------------------------------------------------------------

def _generate_sample() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 365
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    t = np.arange(n)

    # Seasonal ambient temperature (°F)
    ambient = 45 + 30 * np.sin(2 * np.pi * (t - 60) / 365) + rng.normal(0, 3, n)

    # Reservoir depletion (linear over the year)
    depletion = np.linspace(1.0, 0.75, n)

    gas_rate = np.clip(5000 * depletion + rng.normal(0, 150, n), 1000, 6000)
    wh_pressure = np.clip(800 * depletion + rng.normal(0, 20, n), 200, 950)
    tubing_pressure = np.clip(wh_pressure * 0.92 + rng.normal(0, 10, n), 180, 900)
    casing_pressure = np.clip(wh_pressure * 1.05 + rng.normal(0, 15, n), 200, 1000)

    # Wellhead temp: driven by gas rate (higher flow = warmer) and ambient
    wh_temp = 120 + 0.012 * (gas_rate - 3750) + 0.25 * (ambient - 45) + rng.normal(0, 2, n)

    # Separator temp: mostly ambient-driven
    sep_temp = np.clip(ambient + 15 + 0.03 * (gas_rate - 3750) / 100 + rng.normal(0, 2, n), 35, 130)

    # CGR (Bbl/MMcf) — retrograde condensation: higher at LOWER separator temps
    cgr = np.clip(15 - 0.30 * (sep_temp - 60) + rng.normal(0, 1, n), 2, 40)
    condensate_rate = cgr * gas_rate / 1000
    water_rate = np.clip(10 * (1 + 0.5 * (1 - depletion)) + rng.normal(0, 2, n), 1, 50)

    # Gas composition — heavier components correlate with higher CGR
    methane = np.clip(82 - 0.30 * cgr + rng.normal(0, 0.5, n), 65, 95)
    ethane  = np.clip(7  + 0.10 * cgr + rng.normal(0, 0.3, n), 2, 15)
    propane = np.clip(3  + 0.08 * cgr + rng.normal(0, 0.2, n), 0.5, 8)
    co2     = np.clip(1.5 + rng.normal(0, 0.1, n), 0.5, 4)
    n2_col  = np.clip(0.8 + rng.normal(0, 0.05, n), 0.2, 2)
    c4plus  = np.clip(100 - methane - ethane - propane - co2 - n2_col, 0, 10)

    btu = np.clip(900 + 5 * ethane + 8 * propane + 12 * c4plus + rng.normal(0, 5, n), 850, 1400)
    specific_gravity = np.clip(0.55 + 0.0002 * (btu - 1000) + rng.normal(0, 0.005, n), 0.52, 0.80)
    h2s_ppm = np.clip(5 + 0.003 * wh_pressure + rng.normal(0, 2, n), 0, 40)

    return pd.DataFrame({
        "Date":                 dates,
        "Wellhead_Temp_F":      wh_temp.round(1),
        "Separator_Temp_F":     sep_temp.round(1),
        "Ambient_Temp_F":       ambient.round(1),
        "Wellhead_Pressure_psi": wh_pressure.round(0),
        "Tubing_Pressure_psi":  tubing_pressure.round(0),
        "Casing_Pressure_psi":  casing_pressure.round(0),
        "Gas_Rate_Mcfd":        gas_rate.round(0),
        "Condensate_Rate_Bbl":  condensate_rate.round(1),
        "Water_Rate_Bbl":       water_rate.round(1),
        "CGR_BblMMcf":          cgr.round(2),
        "BTU_Content":          btu.round(1),
        "Specific_Gravity":     specific_gravity.round(4),
        "Methane_pct":          methane.round(2),
        "Ethane_pct":           ethane.round(2),
        "Propane_pct":          propane.round(2),
        "CO2_pct":              co2.round(2),
        "N2_pct":               n2_col.round(2),
        "H2S_ppm":              h2s_ppm.round(1),
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df() -> pd.DataFrame | None:
    return _store["df"]


def _filtered_df(body: dict) -> pd.DataFrame | None:
    df = _store["df"]
    if df is None:
        return None
    date_from = body.get("date_from")
    date_to   = body.get("date_to")
    if date_from or date_to:
        dcol = _date_col(df)
        if dcol:
            if date_from:
                df = df[df[dcol] >= pd.to_datetime(date_from)]
            if date_to:
                df = df[df[dcol] <= pd.to_datetime(date_to)]
    return df


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="number").columns.tolist()


def _temp_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in _numeric_cols(df) if "temp" in c.lower() or "temperature" in c.lower()]


def _date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    return None


def _regression_band(x: np.ndarray, y: np.ndarray, x_line: np.ndarray):
    n = len(x)
    slope, intercept, r, p, se = sp.linregress(x, y)
    y_hat = slope * x + intercept
    ss_res = np.sum((y - y_hat) ** 2)
    mse = ss_res / (n - 2)
    x_mean = x.mean()
    ss_xx = np.sum((x - x_mean) ** 2)
    se_line = np.sqrt(mse * (1 / n + (x_line - x_mean) ** 2 / ss_xx))
    t_crit = sp.t.ppf(0.975, df=n - 2)
    y_line = slope * x_line + intercept
    return y_line, y_line + t_crit * se_line, y_line - t_crit * se_line, slope, intercept, r, p, se


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — data management
# ---------------------------------------------------------------------------

@app.route("/api/sample")
def load_sample():
    _store["df"] = _generate_sample()
    _store["filename"] = "sample_well_data (365 days)"
    return jsonify({"ok": True, "rows": len(_store["df"])})


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    try:
        df = pd.read_csv(f)
        for col in df.select_dtypes(include=["object", "str"]).columns:
            try:
                parsed = pd.to_datetime(df[col])
                df[col] = parsed
            except Exception:
                pass
        _store["df"] = df
        _store["filename"] = f.filename
        return jsonify({"ok": True, "rows": len(df)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/info")
def info():
    df = _df()
    if df is None:
        return jsonify({"error": "no data"}), 400

    columns = [
        {
            "name": col,
            "is_numeric": bool(pd.api.types.is_numeric_dtype(df[col])),
            "is_datetime": bool(pd.api.types.is_datetime64_any_dtype(df[col])),
        }
        for col in df.columns
    ]

    preview = df.head(8).copy()
    for col in preview.select_dtypes("datetime64[ns]").columns:
        preview[col] = preview[col].dt.strftime("%Y-%m-%d")

    dcol = _date_col(df)
    date_min = date_max = None
    if dcol:
        date_min = df[dcol].min().strftime("%Y-%m-%d")
        date_max = df[dcol].max().strftime("%Y-%m-%d")

    return jsonify({
        "filename": _store["filename"],
        "rows": len(df),
        "columns": columns,
        "numeric_cols": _numeric_cols(df),
        "temp_cols": _temp_cols(df),
        "date_col": dcol,
        "date_min": date_min,
        "date_max": date_max,
        "preview": json.loads(preview.to_json(orient="records")),
    })


# ---------------------------------------------------------------------------
# Routes — analysis
# ---------------------------------------------------------------------------

@app.route("/api/scatter", methods=["POST"])
def scatter():
    body = request.get_json(force=True)
    df = _filtered_df(body)
    if df is None:
        return jsonify({"error": "no data"}), 400
    x_col = body.get("x")
    y_col = body.get("y")
    color_col = body.get("color")  # optional

    if x_col not in df.columns or y_col not in df.columns:
        return jsonify({"error": "invalid columns"}), 400

    cols = [x_col, y_col]
    if color_col and color_col in df.columns:
        cols.append(color_col)

    sub = df[cols].dropna()
    if len(sub) < 4:
        return jsonify({"error": "insufficient data after removing nulls"}), 400

    x = sub[x_col].values.astype(float)
    y = sub[y_col].values.astype(float)
    n = len(x)

    # Outlier detection
    outlier_method = body.get("outlier_method", "none")
    outlier_mask = np.zeros(n, dtype=bool)
    if outlier_method == "iqr":
        for arr in (x, y):
            q1, q3 = np.percentile(arr, 25), np.percentile(arr, 75)
            iqr = q3 - q1
            outlier_mask |= (arr < q1 - 1.5 * iqr) | (arr > q3 + 1.5 * iqr)
    elif outlier_method == "zscore":
        for arr in (x, y):
            z = np.abs(sp.zscore(arr))
            outlier_mask |= z > 3

    pearson_r, pearson_p = sp.pearsonr(x, y)
    spearman_r, spearman_p = sp.spearmanr(x, y)

    x_line = np.linspace(x.min(), x.max(), 300)
    y_line, ci_up, ci_lo, slope, intercept, r_val, _, se = _regression_band(x, y, x_line)

    result = {
        "x": x.tolist(),
        "y": y.tolist(),
        "x_col": x_col,
        "y_col": y_col,
        "trend_x": x_line.tolist(),
        "trend_y": y_line.tolist(),
        "ci_upper": ci_up.tolist(),
        "ci_lower": ci_lo.tolist(),
        "outlier_mask": outlier_mask.tolist(),
        "outlier_method": outlier_method,
        "outlier_count": int(outlier_mask.sum()),
        "stats": {
            "n": n,
            "pearson_r": round(float(pearson_r), 4),
            "pearson_p": round(float(pearson_p), 6),
            "spearman_r": round(float(spearman_r), 4),
            "spearman_p": round(float(spearman_p), 6),
            "r_squared": round(float(r_val ** 2), 4),
            "slope": round(float(slope), 6),
            "intercept": round(float(intercept), 4),
            "std_err": round(float(se), 6),
            "outlier_count": int(outlier_mask.sum()),
            "outlier_method": outlier_method,
        },
    }

    if color_col and color_col in df.columns:
        result["color"] = sub[color_col].tolist()
        result["color_col"] = color_col

    return jsonify(result)


@app.route("/api/temp-overview", methods=["POST"])
def temp_overview():
    body = request.get_json(force=True)
    df = _filtered_df(body)
    if df is None:
        return jsonify({"error": "no data"}), 400
    temp_col = body.get("temp_col")
    if temp_col not in df.columns:
        return jsonify({"error": "invalid column"}), 400

    others = [c for c in _numeric_cols(df) if c != temp_col]
    results = []
    for col in others:
        valid = df[[temp_col, col]].dropna()
        if len(valid) < 4:
            continue
        r, p = sp.pearsonr(valid[temp_col].values.astype(float),
                           valid[col].values.astype(float))
        results.append({
            "column": col,
            "pearson_r": round(float(r), 4),
            "pearson_p": round(float(p), 6),
            "significant": bool(p < 0.05),
        })

    results.sort(key=lambda d: abs(d["pearson_r"]), reverse=True)
    return jsonify({"temp_col": temp_col, "correlations": results})


@app.route("/api/matrix", methods=["GET", "POST"])
def matrix():
    body = request.get_json(force=True, silent=True) or {}
    df = _filtered_df(body)
    if df is None:
        return jsonify({"error": "no data"}), 400

    num = df.select_dtypes(include="number")
    if num.empty:
        return jsonify({"error": "no numeric columns"}), 400

    corr = num.corr(method="pearson")
    cols = corr.columns.tolist()
    n = len(num)

    # p-value matrix
    p_mat = []
    for c1 in cols:
        row = []
        for c2 in cols:
            if c1 == c2:
                row.append(0.0)
            else:
                v = num[[c1, c2]].dropna()
                if len(v) >= 4:
                    _, p = sp.pearsonr(v[c1].values, v[c2].values)
                    row.append(round(float(p), 6))
                else:
                    row.append(1.0)
        p_mat.append(row)

    return jsonify({
        "columns": cols,
        "matrix": corr.round(3).values.tolist(),
        "p_matrix": p_mat,
        "n": n,
    })


@app.route("/api/timeseries", methods=["POST"])
def timeseries():
    body = request.get_json(force=True)
    df = _filtered_df(body)
    if df is None:
        return jsonify({"error": "no data"}), 400
    date_col = body.get("date_col")
    columns = body.get("columns", [])

    if not columns:
        return jsonify({"error": "no columns selected"}), 400

    if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df_s = df.sort_values(date_col)
        x_vals = df_s[date_col].dt.strftime("%Y-%m-%d").tolist()
        x_label = date_col
    else:
        df_s = df.reset_index(drop=True)
        x_vals = df_s.index.tolist()
        x_label = "Row Index"

    rolling_window = int(body.get("rolling_window") or 0)

    series = []
    for col in columns:
        if col in df_s.columns and pd.api.types.is_numeric_dtype(df_s[col]):
            raw = df_s[col].where(pd.notna(df_s[col]), other=None)
            entry = {"name": col, "y": raw.tolist()}
            if rolling_window >= 2:
                rolled = df_s[col].rolling(window=rolling_window, min_periods=1).mean()
                rolled = rolled.where(pd.notna(rolled), other=None)
                entry["y_rolling"] = rolled.tolist()
            series.append(entry)

    return jsonify({
        "x": x_vals,
        "x_label": x_label,
        "series": series,
        "rolling_window": rolling_window if rolling_window >= 2 else None,
    })


@app.route("/api/summary", methods=["GET", "POST"])
def summary():
    body = request.get_json(force=True, silent=True) or {}
    df = _filtered_df(body)
    if df is None:
        return jsonify({"error": "no data"}), 400

    num = df.select_dtypes(include="number")
    desc = num.describe(percentiles=[0.25, 0.5, 0.75]).round(4)

    rows = []
    for col in desc.columns:
        rows.append({
            "column": col,
            "count":  int(desc.loc["count", col]),
            "mean":   float(desc.loc["mean", col]),
            "std":    float(desc.loc["std", col]),
            "min":    float(desc.loc["min", col]),
            "p25":    float(desc.loc["25%", col]),
            "median": float(desc.loc["50%", col]),
            "p75":    float(desc.loc["75%", col]),
            "max":    float(desc.loc["max", col]),
        })

    return jsonify(rows)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5001)
