"""Tests for GET /api/info, POST /api/matrix, and GET+POST /api/summary."""
import math
import pytest
import app as flask_app


def _load_sample(client):
    client.get("/api/sample")


# ===========================================================================
# /api/info
# ===========================================================================

class TestInfo:
    def test_no_data_returns_400(self, client):
        r = client.get("/api/info")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_returns_200_after_sample_loaded(self, client):
        _load_sample(client)
        assert client.get("/api/info").status_code == 200

    def test_contains_required_keys(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        for key in ("filename", "rows", "columns", "numeric_cols", "temp_cols",
                    "date_col", "date_min", "date_max", "preview"):
            assert key in data, f"missing key: {key}"

    def test_row_count_correct(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        assert data["rows"] == 365

    def test_date_col_detected(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        assert data["date_col"] == "Date"

    def test_date_min_and_max_correct(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        assert data["date_min"] == "2023-01-01"
        assert data["date_max"] == "2023-12-31"

    def test_numeric_cols_non_empty(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        assert len(data["numeric_cols"]) > 0
        assert "Date" not in data["numeric_cols"]

    def test_temp_cols_subset_of_numeric_cols(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        for tc in data["temp_cols"]:
            assert tc in data["numeric_cols"]

    def test_preview_has_at_most_8_rows(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        assert len(data["preview"]) <= 8

    def test_preview_dates_formatted_as_strings(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        date_val = data["preview"][0]["Date"]
        assert isinstance(date_val, str)
        assert date_val == "2023-01-01"

    def test_columns_list_has_correct_shape(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        for col in data["columns"]:
            assert "name" in col
            assert "is_numeric" in col
            assert "is_datetime" in col

    def test_date_column_flagged_as_datetime(self, client):
        _load_sample(client)
        data = client.get("/api/info").get_json()
        date_entry = next(c for c in data["columns"] if c["name"] == "Date")
        assert date_entry["is_datetime"] is True
        assert date_entry["is_numeric"] is False

    def test_no_date_min_max_when_no_date_col(self, client):
        import pandas as pd
        flask_app._store["df"] = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        data = client.get("/api/info").get_json()
        assert data["date_col"] is None
        assert data["date_min"] is None
        assert data["date_max"] is None


# ===========================================================================
# /api/matrix
# ===========================================================================

class TestMatrix:
    def test_no_data_returns_400(self, client):
        r = client.post("/api/matrix", json={})
        assert r.status_code == 400

    def test_returns_200_with_sample(self, client):
        _load_sample(client)
        assert client.post("/api/matrix", json={}).status_code == 200

    def test_contains_required_keys(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        for key in ("columns", "matrix", "p_matrix", "n"):
            assert key in data, f"missing key: {key}"

    def test_matrix_is_square(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        n = len(data["columns"])
        assert len(data["matrix"]) == n
        for row in data["matrix"]:
            assert len(row) == n

    def test_p_matrix_is_square(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        n = len(data["columns"])
        assert len(data["p_matrix"]) == n
        for row in data["p_matrix"]:
            assert len(row) == n

    def test_diagonal_is_one(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        for i, row in enumerate(data["matrix"]):
            assert abs(row[i] - 1.0) < 1e-6, f"diagonal [{i}][{i}] should be 1.0"

    def test_p_diagonal_is_zero(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        for i, row in enumerate(data["p_matrix"]):
            assert row[i] == 0.0, f"p diagonal [{i}][{i}] should be 0.0"

    def test_matrix_values_between_neg1_and_1(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        for row in data["matrix"]:
            for val in row:
                assert -1.0 <= val <= 1.0, f"correlation {val} out of range"

    def test_matrix_is_symmetric(self, client):
        _load_sample(client)
        data = client.post("/api/matrix", json={}).get_json()
        mat = data["matrix"]
        n = len(mat)
        for i in range(n):
            for j in range(n):
                assert abs(mat[i][j] - mat[j][i]) < 1e-6

    def test_no_numeric_columns_returns_400(self, client):
        import pandas as pd
        flask_app._store["df"] = pd.DataFrame({"Name": ["Alice", "Bob"]})
        r = client.post("/api/matrix", json={})
        assert r.status_code == 400

    def test_date_filter_reduces_n(self, client):
        _load_sample(client)
        full = client.post("/api/matrix", json={}).get_json()
        filtered = client.post("/api/matrix", json={
            "date_from": "2023-06-01", "date_to": "2023-06-30"
        }).get_json()
        assert filtered["n"] < full["n"]

    def test_accessible_via_get(self, client):
        _load_sample(client)
        assert client.get("/api/matrix").status_code == 200


# ===========================================================================
# /api/summary
# ===========================================================================

class TestSummary:
    def test_no_data_returns_400(self, client):
        r = client.post("/api/summary", json={})
        assert r.status_code == 400

    def test_returns_200_with_sample(self, client):
        _load_sample(client)
        assert client.post("/api/summary", json={}).status_code == 200

    def test_returns_list(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_row_has_required_keys(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        for row in data:
            for key in ("column", "count", "mean", "std", "min", "p25", "median", "p75", "max"):
                assert key in row, f"missing key '{key}' in row for {row.get('column')}"

    def test_count_equals_row_count(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        for row in data:
            assert row["count"] == 365

    def test_min_lte_p25_lte_median_lte_p75_lte_max(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        for row in data:
            assert row["min"] <= row["p25"] <= row["median"] <= row["p75"] <= row["max"], \
                f"percentile ordering violated for {row['column']}"

    def test_std_is_non_negative(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        for row in data:
            assert row["std"] >= 0

    def test_only_numeric_columns_in_summary(self, client):
        _load_sample(client)
        data = client.post("/api/summary", json={}).get_json()
        col_names = [r["column"] for r in data]
        assert "Date" not in col_names

    def test_date_filter_reduces_count(self, client):
        _load_sample(client)
        filtered = client.post("/api/summary", json={
            "date_from": "2023-06-01", "date_to": "2023-06-30"
        }).get_json()
        for row in filtered:
            assert row["count"] == 30

    def test_accessible_via_get(self, client):
        _load_sample(client)
        assert client.get("/api/summary").status_code == 200
