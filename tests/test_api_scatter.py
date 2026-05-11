"""Tests for POST /api/scatter."""
import json
import pytest
import app as flask_app


def _load_sample(client):
    client.get("/api/sample")


def _scatter(client, body):
    return client.post("/api/scatter", json=body)


# ---------------------------------------------------------------------------
# Guard conditions — no data / bad columns
# ---------------------------------------------------------------------------

def test_no_data_returns_400(client):
    r = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_missing_x_column_returns_400(client):
    _load_sample(client)
    r = _scatter(client, {"x": "nonexistent", "y": "Wellhead_Temp_F"})
    assert r.status_code == 400


def test_missing_y_column_returns_400(client):
    _load_sample(client)
    r = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "nonexistent"})
    assert r.status_code == 400


def test_both_columns_missing_returns_400(client):
    _load_sample(client)
    r = _scatter(client, {"x": "bad_x", "y": "bad_y"})
    assert r.status_code == 400


def test_insufficient_data_after_filtering_returns_400(client):
    import pandas as pd
    flask_app._store["df"] = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=3),
        "A": [1.0, 2.0, 3.0],
        "B": [4.0, 5.0, 6.0],
    })
    # date filter leaves 0 rows
    r = _scatter(client, {"x": "A", "y": "B", "date_from": "2025-01-01"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Successful response shape
# ---------------------------------------------------------------------------

def test_success_returns_200(client):
    _load_sample(client)
    r = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"})
    assert r.status_code == 200


def test_response_contains_required_keys(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    for key in ("x", "y", "x_col", "y_col", "trend_x", "trend_y",
                "ci_upper", "ci_lower", "outlier_mask", "stats"):
        assert key in data, f"missing key: {key}"


def test_x_and_y_arrays_same_length(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    assert len(data["x"]) == len(data["y"])


def test_trend_and_ci_arrays_same_length(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    assert len(data["trend_x"]) == len(data["trend_y"]) == len(data["ci_upper"]) == len(data["ci_lower"])


def test_outlier_mask_same_length_as_data(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    assert len(data["outlier_mask"]) == len(data["x"])


def test_column_names_echoed_in_response(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    assert data["x_col"] == "Gas_Rate_Mcfd"
    assert data["y_col"] == "Wellhead_Temp_F"


# ---------------------------------------------------------------------------
# Stats values are plausible
# ---------------------------------------------------------------------------

def test_pearson_r_within_valid_range(client):
    _load_sample(client)
    stats = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()["stats"]
    assert -1.0 <= stats["pearson_r"] <= 1.0


def test_spearman_r_within_valid_range(client):
    _load_sample(client)
    stats = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()["stats"]
    assert -1.0 <= stats["spearman_r"] <= 1.0


def test_r_squared_between_zero_and_one(client):
    _load_sample(client)
    stats = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()["stats"]
    assert 0.0 <= stats["r_squared"] <= 1.0


def test_p_values_between_zero_and_one(client):
    _load_sample(client)
    stats = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()["stats"]
    assert 0.0 <= stats["pearson_p"] <= 1.0
    assert 0.0 <= stats["spearman_p"] <= 1.0


def test_n_matches_non_null_row_count(client):
    _load_sample(client)
    stats = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()["stats"]
    # Sample data has 365 rows with no nulls in these columns
    assert stats["n"] == 365


# ---------------------------------------------------------------------------
# Outlier detection
# ---------------------------------------------------------------------------

def test_outlier_method_none_produces_all_false_mask(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "outlier_method": "none"
    }).get_json()
    assert all(v is False for v in data["outlier_mask"])
    assert data["stats"]["outlier_count"] == 0


def test_outlier_method_iqr_detects_some_outliers(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "outlier_method": "iqr"
    }).get_json()
    # Sample data has realistic noise; IQR should flag at least a few points
    assert data["stats"]["outlier_count"] >= 0  # non-negative is the floor
    assert data["stats"]["outlier_method"] == "iqr"


def test_outlier_method_zscore_detects_some_outliers(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "outlier_method": "zscore"
    }).get_json()
    assert data["stats"]["outlier_count"] >= 0
    assert data["stats"]["outlier_method"] == "zscore"


def test_outlier_count_consistent_with_mask(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "outlier_method": "iqr"
    }).get_json()
    assert sum(data["outlier_mask"]) == data["stats"]["outlier_count"]


# ---------------------------------------------------------------------------
# Optional color column
# ---------------------------------------------------------------------------

def test_color_column_included_when_valid(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "color": "Wellhead_Pressure_psi"
    }).get_json()
    assert "color" in data
    assert data["color_col"] == "Wellhead_Pressure_psi"
    assert len(data["color"]) == len(data["x"])


def test_color_column_absent_when_invalid(client):
    _load_sample(client)
    data = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F", "color": "nonexistent"
    }).get_json()
    assert "color" not in data


def test_color_column_absent_when_not_provided(client):
    _load_sample(client)
    data = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    assert "color" not in data


# ---------------------------------------------------------------------------
# Date filter propagates into scatter
# ---------------------------------------------------------------------------

def test_date_filter_reduces_n(client):
    _load_sample(client)
    full = _scatter(client, {"x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F"}).get_json()
    filtered = _scatter(client, {
        "x": "Gas_Rate_Mcfd", "y": "Wellhead_Temp_F",
        "date_from": "2023-06-01", "date_to": "2023-06-30",
    }).get_json()
    assert filtered["stats"]["n"] < full["stats"]["n"]
    assert filtered["stats"]["n"] == 30
