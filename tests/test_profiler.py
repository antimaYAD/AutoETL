import pandas as pd

from app.services.profiler_service import profile_dataframe
from tests.conftest import load_fixture_df


def test_profile_sales_messy():
    df = load_fixture_df("sales_messy.csv")
    result = profile_dataframe(df)

    assert result["row_count"] == len(df)
    assert result["column_count"] == len(df.columns)
    columns_by_name = {c["column"]: c for c in result["columns"]}

    assert columns_by_name["email"]["inferred_type"] == "email"
    assert columns_by_name["amount"]["null_count"] == 0
    assert columns_by_name["customer_name"]["null_count"] == 1


def test_profile_empty_dataframe():
    df = pd.DataFrame({"a": [], "b": []})
    result = profile_dataframe(df)
    assert result["row_count"] == 0
    assert len(result["columns"]) == 2
    for col in result["columns"]:
        assert col["inferred_type"] == "unknown"


def test_profile_numeric_column_stats():
    df = pd.DataFrame({"amount": [10, 20, 30, 40]})
    result = profile_dataframe(df)
    col = result["columns"][0]
    assert col["min"] == 10
    assert col["max"] == 40
    assert col["mean"] == 25.0
    assert col["median"] == 25.0


def test_profile_detects_mixed_types():
    df = pd.DataFrame({"col": [1, "two", 3.0]})
    result = profile_dataframe(df)
    assert result["columns"][0]["mixed_types"] is True
