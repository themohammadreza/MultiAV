import httpx


def test_admin_login_and_me_with_cookie(client: httpx.Client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]

    me_response = client.get("/api/v1/admin/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


def test_admin_auth_required(client: httpx.Client):
    response = client.get("/api/v1/admin/keys/")
    assert response.status_code == 401
