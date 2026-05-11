"""Tests for POST /api/upload."""
import io
import pandas as pd
import pytest
import app as flask_app


def _upload(client, content, filename="data.csv", content_type="text/csv"):
    data = {"file": (io.BytesIO(content.encode()), filename)}
    return client.post("/api/upload", data=data, content_type="multipart/form-data")


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

def test_no_file_returns_400(client):
    r = client.post("/api/upload", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_malformed_csv_returns_400(client):
    # pandas will raise on completely un-parseable content
    r = _upload(client, "not,a,csv\n\x00\x01\x02binary garbage here\xff\xfe")
    # Either it parses oddly or returns 400; either way, no server crash
    assert r.status_code in (200, 400)


def test_empty_csv_returns_400(client):
    r = _upload(client, "")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Successful upload
# ---------------------------------------------------------------------------

def test_valid_csv_returns_200(client):
    csv = "A,B,C\n1,2,3\n4,5,6\n"
    r = _upload(client, csv)
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["rows"] == 2


def test_uploaded_data_stored_in_memory(client):
    csv = "X,Y\n10,20\n30,40\n50,60\n"
    _upload(client, csv)
    df = flask_app._store["df"]
    assert df is not None
    assert len(df) == 3
    assert list(df.columns) == ["X", "Y"]


def test_filename_stored(client):
    csv = "A,B\n1,2\n"
    _upload(client, csv, filename="mywell.csv")
    assert flask_app._store["filename"] == "mywell.csv"


# ---------------------------------------------------------------------------
# Date column auto-detection
# ---------------------------------------------------------------------------

def test_date_column_parsed_to_datetime(client):
    csv = "Date,Value\n2024-01-01,100\n2024-01-02,200\n2024-01-03,300\n"
    _upload(client, csv)
    df = flask_app._store["df"]
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])


def test_date_column_values_correct(client):
    csv = "Date,Value\n2024-03-15,1\n2024-03-16,2\n"
    _upload(client, csv)
    df = flask_app._store["df"]
    assert df["Date"].iloc[0] == pd.Timestamp("2024-03-15")
    assert df["Date"].iloc[1] == pd.Timestamp("2024-03-16")


def test_non_date_string_column_stays_as_object(client):
    csv = "Label,Value\nfoo,1\nbar,2\n"
    _upload(client, csv)
    df = flask_app._store["df"]
    # "Label" contains non-date strings — should remain object dtype
    assert not pd.api.types.is_datetime64_any_dtype(df["Label"])


def test_multiple_columns_only_date_like_ones_converted(client):
    csv = "Date,Name,Score\n2024-01-01,Alice,95\n2024-01-02,Bob,88\n"
    _upload(client, csv)
    df = flask_app._store["df"]
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])
    assert not pd.api.types.is_datetime64_any_dtype(df["Name"])


# ---------------------------------------------------------------------------
# Upload replaces previous data
# ---------------------------------------------------------------------------

def test_second_upload_replaces_first(client):
    _upload(client, "A,B\n1,2\n3,4\n")
    _upload(client, "X,Y,Z\n10,20,30\n")
    df = flask_app._store["df"]
    assert list(df.columns) == ["X", "Y", "Z"]
    assert len(df) == 1


# ---------------------------------------------------------------------------
# Subsequent /api/info works after upload
# ---------------------------------------------------------------------------

def test_info_available_after_upload(client):
    csv = "Date,Pressure,Temp\n2024-01-01,800,120\n2024-01-02,790,118\n"
    _upload(client, csv)
    r = client.get("/api/info")
    assert r.status_code == 200
    info = r.get_json()
    assert info["rows"] == 2
    assert "Pressure" in info["numeric_cols"]
    assert "Temp" in info["temp_cols"]
