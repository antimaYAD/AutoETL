import io
import json

import numpy as np
import pandas as pd

from app.services import analytics_service


def _sales_df(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "order_id": range(1, n + 1),
            "order_date": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
            "customer_id": rng.integers(1, 30, n),
            "product": rng.choice(["A", "B", "C", "D"], n),
            "region": rng.choice(["North", "South"], n),
            "quantity": rng.integers(1, 10, n),
            "unit_price": rng.uniform(10, 100, n).round(2),
        }
    )
    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    return df


def test_domain_detection_sales():
    result = analytics_service.detect_domain(_sales_df())
    assert result["domain"] == "sales"
    assert result["confidence"] > 0


def test_domain_detection_hr():
    df = pd.DataFrame({"employee_id": [1, 2], "department": ["a", "b"], "salary": [10, 20], "hire_date": ["2020-01-01", "2021-01-01"]})
    assert analytics_service.detect_domain(df)["domain"] == "hr"


def test_domain_detection_unknown_falls_back_to_general():
    df = pd.DataFrame({"foo": [1, 2], "bar": [3, 4]})
    assert analytics_service.detect_domain(df)["domain"] == "general"


def _report_style_df() -> pd.DataFrame:
    """Mimics a Tally-style export: title row, real headers in row 1, Excel serial
    dates, numbers stored as text and one unlabeled total column."""
    rng = np.random.default_rng(3)
    n = 200
    qty = rng.integers(1, 20, n)
    price = rng.uniform(100, 900, n).round(2)
    serial = 45900 + rng.integers(0, 150, n)
    header = ["Order Date", "Customer Name", "State", "Quantity", "Unit Sale price", "Total Cost Amount", None]
    body = [
        [str(serial[i]), f"Cust {i % 25}", ["MH", "DL", "WB"][i % 3], str(qty[i]), str(price[i]),
         str(round(qty[i] * price[i] * 0.8, 2)), str(round(qty[i] * price[i], 2))]
        for i in range(n)
    ]
    raw = pd.DataFrame([header] + body, columns=["For Period 1-Apr-26 To 4-Sep-26"] + [f"Unnamed: {i}" for i in range(1, 7)])
    raw["Unnamed: 7"] = np.nan
    return raw


def test_prepare_promotes_header_converts_types_and_names_derived_column():
    prepared, notes = analytics_service.prepare_dataframe(_report_style_df())
    assert list(prepared.columns[:3]) == ["Order Date", "Customer Name", "State"]
    assert pd.api.types.is_datetime64_any_dtype(prepared["Order Date"])
    assert pd.api.types.is_numeric_dtype(prepared["Quantity"])
    assert "Total Sale Amount" in prepared.columns
    assert any("headers" in n for n in notes)


def test_report_style_file_gets_real_kpis_and_charts():
    result = analytics_service.analyze_dataset(_report_style_df())
    keys = {k["key"] for k in result["kpis"]}
    assert {"total_revenue", "gross_profit", "margin_pct", "customers", "mom_growth"} <= keys
    assert result["columns_used"]["revenue"] == "Total Sale Amount"
    kinds = {c["kind"] for c in result["charts"]}
    assert {"line", "forecast", "hbar", "donut", "histogram", "scatter", "heatmap"} <= kinds
    assert result["stats"] and result["categories"] and result["preparation"]
    json.dumps(result, allow_nan=False)


def test_partial_last_period_is_excluded_from_trends():
    dates = pd.date_range("2025-01-01", "2025-06-03", freq="D")
    df = pd.DataFrame({"order_date": dates.strftime("%Y-%m-%d"), "revenue": np.arange(len(dates)) + 100.0, "region": "N"})
    result = analytics_service.analyze_dataset(df)
    assert any("incomplete" in f for f in result["insights"]["facts"])
    line = next(c for c in result["charts"] if c["kind"] == "line")
    assert all("Jun" not in row["label"] for row in line["data"])


def test_charts_declare_axis_labels_and_series():
    result = analytics_service.analyze_dataset(_sales_df())
    for chart in result["charts"]:
        if chart["kind"] in {"line", "bar", "hbar", "histogram", "forecast", "scatter"}:
            assert chart["x_label"] and chart["y_label"] and chart["series"]


def test_column_roles_floats_are_measures_not_ids():
    df, _ = analytics_service.prepare_dataframe(_sales_df())
    roles = analytics_service.detect_column_roles(df)
    assert "order_id" in roles["id"]
    assert "revenue" in roles["measure"]
    assert "unit_price" in roles["measure"]
    assert "order_date" in roles["date"]


def test_kpis_only_when_columns_exist():
    result = analytics_service.analyze_dataset(_sales_df())
    keys = {k["key"] for k in result["kpis"]}
    assert {"total_revenue", "aov", "total_orders", "customers"} <= keys
    # no cost column -> no profit/margin KPIs (framework section 20)
    assert "gross_profit" not in keys
    assert "margin_pct" not in keys


def test_generic_dataset_still_gets_quality_kpis_and_charts():
    df = pd.DataFrame({"a": [5, 2, 9, 4, 7, 1, 8], "b": [12, 4, 18, 8, 14, 2, 16], "c": list("xyxyxyx")})
    result = analytics_service.analyze_dataset(df)
    keys = {k["key"] for k in result["kpis"]}
    assert {"completeness", "missing_pct", "duplicate_pct"} <= keys
    kinds = {c["kind"] for c in result["charts"]}
    assert "heatmap" in kinds
    assert result["forecast"] is None


def test_forecast_generated_for_time_series():
    result = analytics_service.analyze_dataset(_sales_df())
    assert result["forecast"] is not None
    assert len(result["forecast"]["forecast"]) == analytics_service.FORECAST_PERIODS
    assert any(c["kind"] == "forecast" for c in result["charts"])


def test_anomaly_detection_flags_outlier():
    df = pd.DataFrame({"value": [10] * 20 + [10_000]})
    result = analytics_service.detect_anomalies(df, {"measure": ["value"]})
    assert result and result[0]["outlier_count"] == 1


def test_result_is_json_serializable_with_nans():
    df = _sales_df()
    df.loc[3:8, "revenue"] = np.nan
    df.loc[5, "product"] = None
    json.dumps(analytics_service.analyze_dataset(df), allow_nan=False)


def test_empty_and_tiny_dataframes_do_not_crash():
    analytics_service.analyze_dataset(pd.DataFrame({"a": [1]}))
    analytics_service.analyze_dataset(pd.DataFrame({"a": []}))


def test_analytics_endpoint(client, auth_headers):
    csv = _sales_df().to_csv(index=False).encode()
    upload = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("sales.csv", io.BytesIO(csv), "text/csv")},
    )
    dataset_id = upload.json()["id"]
    response = client.get(f"/api/v1/datasets/{dataset_id}/analytics", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["domain"]["domain"] == "sales"
    assert body["charts"] and body["kpis"] and body["insights"]["facts"]


def test_analytics_requires_auth_and_ownership(client, auth_headers):
    assert client.get("/api/v1/datasets/1/analytics").status_code == 401
    assert client.get("/api/v1/datasets/999/analytics", headers=auth_headers).status_code == 404
