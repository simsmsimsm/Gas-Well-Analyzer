"""Tests for _filtered_df() — the date-range filter applied by every analysis route."""
import pandas as pd
import pytest
import app as flask_app
from app import _filtered_df


def _load(df):
    flask_app._store["df"] = df


# ---------------------------------------------------------------------------
# None / empty store
# ---------------------------------------------------------------------------

def test_returns_none_when_no_data_loaded():
    assert _filtered_df({}) is None


def test_returns_none_when_store_is_none():
    flask_app._store["df"] = None
    assert _filtered_df({"date_from": "2024-01-01"}) is None


# ---------------------------------------------------------------------------
# No filter applied
# ---------------------------------------------------------------------------

def test_returns_full_df_when_no_dates_given(simple_df):
    _load(simple_df)
    result = _filtered_df({})
    assert len(result) == 10


def test_returns_full_df_when_date_keys_absent(simple_df):
    _load(simple_df)
    result = _filtered_df({"x": "Value", "y": "Other"})
    assert len(result) == 10


# ---------------------------------------------------------------------------
# date_from only
# ---------------------------------------------------------------------------

def test_date_from_filters_lower_bound(simple_df):
    _load(simple_df)
    # Dates are 2024-01-01 through 2024-01-10; keep from day 6 onward → 5 rows
    result = _filtered_df({"date_from": "2024-01-06"})
    assert len(result) == 5
    assert result["Date"].min() >= pd.Timestamp("2024-01-06")


def test_date_from_inclusive(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_from": "2024-01-01"})
    assert len(result) == 10  # boundary row included


def test_date_from_beyond_all_data_returns_empty(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_from": "2025-01-01"})
    assert len(result) == 0


# ---------------------------------------------------------------------------
# date_to only
# ---------------------------------------------------------------------------

def test_date_to_filters_upper_bound(simple_df):
    _load(simple_df)
    # Keep up to day 3 → 3 rows
    result = _filtered_df({"date_to": "2024-01-03"})
    assert len(result) == 3
    assert result["Date"].max() <= pd.Timestamp("2024-01-03")


def test_date_to_inclusive(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_to": "2024-01-10"})
    assert len(result) == 10  # boundary row included


def test_date_to_before_all_data_returns_empty(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_to": "2023-01-01"})
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Both bounds
# ---------------------------------------------------------------------------

def test_both_bounds_applied_together(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_from": "2024-01-04", "date_to": "2024-01-07"})
    assert len(result) == 4
    assert result["Date"].min() >= pd.Timestamp("2024-01-04")
    assert result["Date"].max() <= pd.Timestamp("2024-01-07")


def test_single_day_window(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_from": "2024-01-05", "date_to": "2024-01-05"})
    assert len(result) == 1
    assert result["Date"].iloc[0] == pd.Timestamp("2024-01-05")


def test_inverted_range_returns_empty(simple_df):
    _load(simple_df)
    result = _filtered_df({"date_from": "2024-01-08", "date_to": "2024-01-03"})
    assert len(result) == 0


# ---------------------------------------------------------------------------
# DataFrame without a date column
# ---------------------------------------------------------------------------

def test_no_date_column_skips_filter():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    _load(df)
    result = _filtered_df({"date_from": "2024-01-01", "date_to": "2024-12-31"})
    # No date column → filter is a no-op, all rows returned
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Works correctly with the sample dataset
# ---------------------------------------------------------------------------

def test_filter_on_sample_data(sample_df):
    _load(sample_df)
    result = _filtered_df({"date_from": "2023-06-01", "date_to": "2023-06-30"})
    assert len(result) == 30
    assert result["Date"].min() >= pd.Timestamp("2023-06-01")
    assert result["Date"].max() <= pd.Timestamp("2023-06-30")


def test_full_sample_returned_with_no_filter(sample_df):
    _load(sample_df)
    result = _filtered_df({})
    assert len(result) == 365
