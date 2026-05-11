"""Tests for POST /api/timeseries."""
import pytest
import app as flask_app


def _load_sample(client):
    client.get("/api/sample")


def _ts(client, body):
    return client.post("/api/timeseries", json=body)


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

def test_no_data_returns_400(client):
    r = _ts(client, {"columns": ["Gas_Rate_Mcfd"]})
    assert r.status_code == 400


def test_no_columns_selected_returns_400(client):
    _load_sample(client)
    r = _ts(client, {"columns": []})
    assert r.status_code == 400


def test_empty_columns_key_absent_returns_400(client):
    _load_sample(client)
    r = _ts(client, {"date_col": "Date"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Successful response shape
# ---------------------------------------------------------------------------

def test_success_returns_200(client):
    _load_sample(client)
    r = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]})
    assert r.status_code == 200


def test_response_contains_required_keys(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    for key in ("x", "x_label", "series", "rolling_window"):
        assert key in data, f"missing key: {key}"


def test_x_is_list_of_date_strings(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert isinstance(data["x"], list)
    assert data["x"][0] == "2023-01-01"
    assert data["x"][-1] == "2023-12-31"


def test_x_label_set_to_date_column_name(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert data["x_label"] == "Date"


def test_series_length_matches_columns_requested(client):
    _load_sample(client)
    cols = ["Gas_Rate_Mcfd", "Wellhead_Pressure_psi"]
    data = _ts(client, {"date_col": "Date", "columns": cols}).get_json()
    assert len(data["series"]) == 2


def test_series_names_match_requested_columns(client):
    _load_sample(client)
    cols = ["Gas_Rate_Mcfd", "Condensate_Rate_Bbl"]
    data = _ts(client, {"date_col": "Date", "columns": cols}).get_json()
    names = {s["name"] for s in data["series"]}
    assert names == set(cols)


def test_y_array_length_matches_x(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert len(data["series"][0]["y"]) == len(data["x"])


# ---------------------------------------------------------------------------
# Rolling window
# ---------------------------------------------------------------------------

def test_rolling_window_absent_when_not_requested(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert data["rolling_window"] is None
    assert "y_rolling" not in data["series"][0]


def test_rolling_window_absent_when_zero(client):
    _load_sample(client)
    data = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"], "rolling_window": 0
    }).get_json()
    assert data["rolling_window"] is None


def test_rolling_window_absent_when_one(client):
    _load_sample(client)
    data = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"], "rolling_window": 1
    }).get_json()
    assert data["rolling_window"] is None


def test_rolling_window_present_when_gte_two(client):
    _load_sample(client)
    data = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"], "rolling_window": 7
    }).get_json()
    assert data["rolling_window"] == 7
    assert "y_rolling" in data["series"][0]


def test_y_rolling_same_length_as_y(client):
    _load_sample(client)
    data = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"], "rolling_window": 14
    }).get_json()
    s = data["series"][0]
    assert len(s["y_rolling"]) == len(s["y"])


def test_rolling_window_echoed_in_response(client):
    _load_sample(client)
    data = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"], "rolling_window": 30
    }).get_json()
    assert data["rolling_window"] == 30


# ---------------------------------------------------------------------------
# No date column → fallback to row index
# ---------------------------------------------------------------------------

def test_fallback_to_row_index_when_no_date_col(client):
    _load_sample(client)
    data = _ts(client, {"columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert data["x_label"] == "Row Index"
    assert isinstance(data["x"][0], int)


def test_fallback_row_index_starts_at_zero(client):
    _load_sample(client)
    data = _ts(client, {"columns": ["Gas_Rate_Mcfd"]}).get_json()
    assert data["x"][0] == 0


# ---------------------------------------------------------------------------
# Invalid / non-numeric column silently skipped
# ---------------------------------------------------------------------------

def test_non_numeric_column_excluded_from_series(client):
    _load_sample(client)
    # "Date" is datetime, not numeric — should not appear in series
    data = _ts(client, {"date_col": "Date", "columns": ["Date", "Gas_Rate_Mcfd"]}).get_json()
    names = [s["name"] for s in data["series"]]
    assert "Date" not in names
    assert "Gas_Rate_Mcfd" in names


def test_unknown_column_excluded_from_series(client):
    _load_sample(client)
    data = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd", "nonexistent"]}).get_json()
    names = [s["name"] for s in data["series"]]
    assert "nonexistent" not in names
    assert "Gas_Rate_Mcfd" in names


# ---------------------------------------------------------------------------
# Date filter propagates
# ---------------------------------------------------------------------------

def test_date_filter_reduces_x_length(client):
    _load_sample(client)
    full = _ts(client, {"date_col": "Date", "columns": ["Gas_Rate_Mcfd"]}).get_json()
    filtered = _ts(client, {
        "date_col": "Date", "columns": ["Gas_Rate_Mcfd"],
        "date_from": "2023-06-01", "date_to": "2023-06-30",
    }).get_json()
    assert len(filtered["x"]) == 30
    assert len(filtered["x"]) < len(full["x"])
