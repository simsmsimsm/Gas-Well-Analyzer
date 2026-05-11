import pytest
import pandas as pd
import app as flask_app


@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store():
    """Reset in-memory store before every test to prevent state bleed."""
    flask_app._store["df"] = None
    flask_app._store["filename"] = ""
    yield
    flask_app._store["df"] = None
    flask_app._store["filename"] = ""


@pytest.fixture
def sample_df():
    """365-row sample DataFrame matching _generate_sample() structure."""
    return flask_app._generate_sample()


@pytest.fixture
def simple_df():
    """Minimal DataFrame with a date column and two numeric columns."""
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "Value": range(10),
        "Other": range(10, 20),
    })
