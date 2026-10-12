import io
from pathlib import Path

import pandas as pd

TEST_DATA_DIR = Path(__file__).parent / "data"


def _make_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def _upload(client, headers, filename="sales_messy.csv"):
    with open(TEST_DATA_DIR / filename, "rb") as f:
        return client.post(
            "/api/v1/datasets/upload",
            headers=headers,
            files={"file": (filename, f, "text/csv")},
        )


def test_upload_requires_auth(client):
    with open(TEST_DATA_DIR / "sales_messy.csv", "rb") as f:
        response = client.post("/api/v1/datasets/upload", files={"file": ("sales_messy.csv", f, "text/csv")})
    assert response.status_code == 401


def test_upload_success(client, auth_headers):
    response = _upload(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "sales_messy.csv"
    assert len(body["versions"]) == 1
    assert body["versions"][0]["version_number"] == 1


def test_upload_rejects_unsupported_extension(client, auth_headers):
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("data.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client, auth_headers):
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_upload_multisheet_excel_merges_sheets(client, auth_headers):
    content = _make_xlsx(
        {
            "Sales": pd.DataFrame({"order": [1, 2], "amount": [10.0, 20.0]}),
            "Costs": pd.DataFrame({"order": [3], "cost": [5.0]}),
        }
    )
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("book.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201
    body = response.json()
    version = body["versions"][0]
    # 2 rows + 1 row merged; union of columns plus source_sheet
    assert version["row_count"] == 3
    assert version["column_count"] == 4
    assert version["source_sheets"] == ["Sales", "Costs"]

    sample = client.get(f"/api/v1/datasets/{body['id']}/sample", headers=auth_headers)
    assert sample.status_code == 200
    data = sample.json()
    assert "source_sheet" in data["columns"]
    assert {r["source_sheet"] for r in data["rows"]} == {"Sales", "Costs"}


def test_upload_single_sheet_excel_has_no_source_column(client, auth_headers):
    content = _make_xlsx({"Only": pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})})
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("single.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201
    body = response.json()
    version = body["versions"][0]
    assert version["row_count"] == 2
    assert version["column_count"] == 2
    assert version["source_sheets"] == ["Only"]

    sample = client.get(f"/api/v1/datasets/{body['id']}/sample", headers=auth_headers)
    assert "source_sheet" not in sample.json()["columns"]


def test_upload_report_style_excel_promotes_headers(client, auth_headers):
    """Workbook with a title row above the real header row must not surface
    'Unnamed: N' columns in the profile/sample."""
    from openpyxl import Workbook

    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(["For Period 1-Apr-26 To 4-Sep-26"])
    ws.append(["Date", "Customer", "Amount"])
    ws.append(["2026-04-01", "A Corp", 10.0])
    ws.append(["2026-04-02", "B Ltd", 20.0])
    wb.save(buf)

    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("report.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201
    body = response.json()
    version = body["versions"][0]
    assert version["row_count"] == 2
    assert version["column_count"] == 3

    sample = client.get(f"/api/v1/datasets/{body['id']}/sample", headers=auth_headers)
    assert sample.status_code == 200
    assert sample.json()["columns"] == ["Date", "Customer", "Amount"]

    profile = client.post(f"/api/v1/datasets/{body['id']}/profile", headers=auth_headers)
    assert profile.status_code == 200
    profiled_cols = [c["column"] for c in profile.json()["columns"]]
    assert profiled_cols == ["Date", "Customer", "Amount"]


def test_upload_empty_workbook_rejected(client, auth_headers):
    content = _make_xlsx({"Empty": pd.DataFrame()})
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("empty.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 400


def test_list_datasets_only_returns_own(client, auth_headers):
    _upload(client, auth_headers)
    response = client.get("/api/v1/datasets", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_dataset_not_found(client, auth_headers):
    response = client.get("/api/v1/datasets/999999", headers=auth_headers)
    assert response.status_code == 404


def test_profile_and_analyze_flow(client, auth_headers):
    upload_response = _upload(client, auth_headers)
    dataset_id = upload_response.json()["id"]

    profile_response = client.post(f"/api/v1/datasets/{dataset_id}/profile", headers=auth_headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["row_count"] == 8

    analyze_response = client.post(f"/api/v1/datasets/{dataset_id}/analyze", headers=auth_headers)
    assert analyze_response.status_code == 200
    assert analyze_response.json()["issue_count"] > 0


def test_preview_and_transform_flow(client, auth_headers):
    upload_response = _upload(client, auth_headers)
    dataset_id = upload_response.json()["id"]

    plan = {"steps": [{"operation": "trim_whitespace", "column": "*"}]}
    preview_response = client.post(f"/api/v1/datasets/{dataset_id}/preview", headers=auth_headers, json=plan)
    assert preview_response.status_code == 200
    assert len(preview_response.json()["previews"]) == 1

    transform_response = client.post(f"/api/v1/datasets/{dataset_id}/transform", headers=auth_headers, json=plan)
    assert transform_response.status_code == 200
    body = transform_response.json()
    assert body["rows_before"] == body["rows_after"] == 8

    dataset_response = client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    assert len(dataset_response.json()["versions"]) == 2


def test_transform_unknown_operation_rejected(client, auth_headers):
    upload_response = _upload(client, auth_headers)
    dataset_id = upload_response.json()["id"]
    plan = {"steps": [{"operation": "delete_database", "column": "*"}]}
    response = client.post(f"/api/v1/datasets/{dataset_id}/transform", headers=auth_headers, json=plan)
    assert response.status_code == 400


def test_delete_dataset(client, auth_headers):
    upload_response = _upload(client, auth_headers)
    dataset_id = upload_response.json()["id"]
    delete_response = client.delete(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    assert delete_response.status_code == 204
    get_response = client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    assert get_response.status_code == 404
