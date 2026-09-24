from pathlib import Path

TEST_DATA_DIR = Path(__file__).parent / "data"


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
