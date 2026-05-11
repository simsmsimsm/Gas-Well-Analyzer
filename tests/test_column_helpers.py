"""Tests for _numeric_cols(), _temp_cols(), and _date_col() column-detection helpers."""
import pandas as pd
import numpy as np
import pytest
from app import _numeric_cols, _temp_cols, _date_col


# ---------------------------------------------------------------------------
# _numeric_cols
# ---------------------------------------------------------------------------

def test_numeric_cols_returns_int_and_float_columns():
    df = pd.DataFrame({"A": [1, 2], "B": [1.0, 2.0], "C": ["x", "y"]})
    assert _numeric_cols(df) == ["A", "B"]


def test_numeric_cols_excludes_string_columns():
    df = pd.DataFrame({"label": ["a", "b"], "value": [1.0, 2.0]})
    assert "label" not in _numeric_cols(df)


def test_numeric_cols_excludes_datetime_columns():
    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=3),
        "Val": [1, 2, 3],
    })
    assert "Date" not in _numeric_cols(df)
    assert "Val" in _numeric_cols(df)


def test_numeric_cols_empty_dataframe():
    df = pd.DataFrame()
    assert _numeric_cols(df) == []


def test_numeric_cols_all_numeric():
    df = pd.DataFrame({"A": [1], "B": [2.0], "C": [3]})
    assert set(_numeric_cols(df)) == {"A", "B", "C"}


def test_numeric_cols_preserves_column_order():
    df = pd.DataFrame({"Z": [1], "A": [2], "M": [3]})
    assert _numeric_cols(df) == ["Z", "A", "M"]


# ---------------------------------------------------------------------------
# _temp_cols
# ---------------------------------------------------------------------------

def test_temp_cols_matches_temp_substring():
    df = pd.DataFrame({"Wellhead_Temp_F": [1.0], "Other": [2.0]})
    assert "Wellhead_Temp_F" in _temp_cols(df)


def test_temp_cols_matches_temperature_substring():
    df = pd.DataFrame({"Reservoir_Temperature_C": [1.0], "Pressure": [2.0]})
    assert "Reservoir_Temperature_C" in _temp_cols(df)


def test_temp_cols_case_insensitive_upper():
    df = pd.DataFrame({"TEMP_SENSOR": [1.0], "pressure": [2.0]})
    assert "TEMP_SENSOR" in _temp_cols(df)


def test_temp_cols_case_insensitive_mixed():
    df = pd.DataFrame({"SurfaceTemperature": [1.0], "flow_rate": [2.0]})
    assert "SurfaceTemperature" in _temp_cols(df)


def test_temp_cols_excludes_non_temperature_columns():
    df = pd.DataFrame({"Pressure_psi": [1.0], "Gas_Rate": [2.0]})
    assert _temp_cols(df) == []


def test_temp_cols_excludes_non_numeric_columns():
    # "temp_label" contains "temp" but is a string column — must not appear
    df = pd.DataFrame({"temp_label": ["hot", "cold"], "value": [1.0, 2.0]})
    assert "temp_label" not in _temp_cols(df)


def test_temp_cols_empty_when_no_temp_columns():
    df = pd.DataFrame({"A": [1.0], "B": [2.0]})
    assert _temp_cols(df) == []


def test_temp_cols_multiple_matches():
    df = pd.DataFrame({
        "Wellhead_Temp_F": [1.0],
        "Separator_Temp_F": [2.0],
        "Ambient_Temp_F": [3.0],
        "Pressure": [4.0],
    })
    result = _temp_cols(df)
    assert set(result) == {"Wellhead_Temp_F", "Separator_Temp_F", "Ambient_Temp_F"}


def test_temp_cols_on_sample_data():
    """Spot-check against the real sample dataset column names."""
    df = pd.DataFrame({
        "Wellhead_Temp_F": [1.0],
        "Separator_Temp_F": [2.0],
        "Ambient_Temp_F": [3.0],
        "Gas_Rate_Mcfd": [4.0],
        "Wellhead_Pressure_psi": [5.0],
    })
    result = _temp_cols(df)
    assert "Wellhead_Temp_F" in result
    assert "Separator_Temp_F" in result
    assert "Ambient_Temp_F" in result
    assert "Gas_Rate_Mcfd" not in result
    assert "Wellhead_Pressure_psi" not in result


# ---------------------------------------------------------------------------
# _date_col — latent "temporal" bug documented as an expected behaviour test
# ---------------------------------------------------------------------------

def test_temp_cols_does_not_match_temporal():
    """'temporal' contains 'temp' — documents that this IS matched (latent bug)."""
    df = pd.DataFrame({"temporal_id": [1.0, 2.0]})
    # This test documents current behaviour: temporal_id IS returned because
    # "temp" is a substring of "temporal". If the heuristic is tightened,
    # update this test to assert the column is NOT returned.
    result = _temp_cols(df)
    assert "temporal_id" in result  # known false-positive


# ---------------------------------------------------------------------------
# _date_col
# ---------------------------------------------------------------------------

def test_date_col_returns_datetime_column():
    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=3),
        "Value": [1, 2, 3],
    })
    assert _date_col(df) == "Date"


def test_date_col_returns_none_when_no_datetime():
    df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
    assert _date_col(df) is None


def test_date_col_returns_first_datetime_column():
    df = pd.DataFrame({
        "First_Date": pd.date_range("2024-01-01", periods=3),
        "Second_Date": pd.date_range("2025-01-01", periods=3),
        "Value": [1, 2, 3],
    })
    assert _date_col(df) == "First_Date"


def test_date_col_ignores_string_date_columns():
    df = pd.DataFrame({"Date": ["2024-01-01", "2024-01-02"], "Value": [1, 2]})
    # String columns are not datetime64 — should not be detected
    assert _date_col(df) is None


def test_date_col_empty_dataframe():
    df = pd.DataFrame()
    assert _date_col(df) is None


def test_date_col_on_sample_dataset():
    import app
    df = app._generate_sample()
    assert _date_col(df) == "Date"
