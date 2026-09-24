def test_register_success(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "alice@example.com", "password": "password123"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"


def test_register_duplicate_email_rejected(client):
    payload = {"email": "alice@example.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_register_invalid_email_rejected(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert response.status_code == 422


def test_login_success(client):
    client.post("/api/v1/auth/register", json={"email": "bob@example.com", "password": "password123"})
    response = client.post(
        "/api/v1/auth/login", data={"username": "bob@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_unauthorized(client):
    client.post("/api/v1/auth/register", json={"email": "carol@example.com", "password": "password123"})
    response = client.post(
        "/api/v1/auth/login", data={"username": "carol@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
