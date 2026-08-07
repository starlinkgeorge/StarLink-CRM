from fastapi.testclient import TestClient


def create_user(client: TestClient) -> dict:
    token = login(client, "admin@example.com", "AdminPass123!")
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Sales User",
            "email": "sales@example.com",
            "password": "SalesPass123!",
            "role": "Sales",
        },
        headers=token,
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_lifecycle_with_contacts_and_followups(client: TestClient) -> None:
    user = create_user(client)
    sales_token = login(client, "sales@example.com", "SalesPass123!")
    create_customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Dalian Montessori School",
            "country": "China",
            "email": "buyer@example.com",
            "source": "Alibaba",
            "level": "A",
            "status": "Lead",
            "owner_id": user["id"],
        }, headers=sales_token,
    )
    assert create_customer.status_code == 201
    customer = create_customer.json()
    stats = client.get("/api/v1/dashboard/stats", headers=sales_token)
    assert stats.status_code == 200
    assert stats.json()["customer_count"] == 1

    contact = client.post(
        "/api/v1/contacts",
        json={"customer_id": customer["id"], "name": "Li Mei", "position": "Buyer"}, headers=sales_token,
    )
    assert contact.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer["id"],
            "user_id": user["id"],
            "type": "Email",
            "content": "Sent the product catalogue.",
        }, headers=sales_token,
    )
    assert followup.status_code == 201
    stats_after_followup = client.get("/api/v1/dashboard/stats", headers=sales_token)
    assert stats_after_followup.json()["followup_count"] == 1

    detail = client.get(f"/api/v1/customers/{customer['id']}", headers=sales_token)
    assert detail.status_code == 200
    assert detail.json()["contacts"][0]["name"] == "Li Mei"
    assert detail.json()["followups"][0]["type"] == "Email"

    tag = client.post("/api/v1/tags", json={"name": "Alibaba High Priority"}, headers=sales_token)
    assert tag.status_code == 201
    linked = client.post(f"/api/v1/customers/{customer['id']}/tags/{tag.json()['id']}", headers=sales_token)
    assert linked.status_code == 200
    assert linked.json()["tags"][0]["name"] == "Alibaba High Priority"

    listing = client.get("/api/v1/customers", params={"q": "Montessori", "tag_id": tag.json()["id"], "limit": 10}, headers=sales_token)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    update = client.put(f"/api/v1/customers/{customer['id']}", json={"status": "Contacted"}, headers=sales_token)
    assert update.status_code == 200
    assert update.json()["status"] == "Contacted"

    delete = client.delete(f"/api/v1/customers/{customer['id']}", headers=sales_token)
    assert delete.status_code == 204


def test_user_email_must_be_unique(client: TestClient) -> None:
    user = create_user(client)
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    users = client.get("/api/v1/users", headers=admin_token)
    assert users.status_code == 200
    assert users.json()[0]["id"] == user["id"]
    detail = client.get(f"/api/v1/users/{user['id']}", headers=admin_token)
    assert detail.status_code == 200
    assert detail.json()["email"] == "sales@example.com"
    duplicate = client.post(
        "/api/v1/users",
        json={"name": "Another", "email": "sales@example.com", "password": "AnotherPass123!"},
        headers=admin_token,
    )
    assert duplicate.status_code == 409


def test_login_rejects_invalid_password_and_protects_api(client: TestClient) -> None:
    invalid_login = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "incorrect"}
    )
    assert invalid_login.status_code == 401
    unauthenticated = client.get("/api/v1/customers")
    assert unauthenticated.status_code == 401


def test_refresh_token_rotates_and_old_token_is_rejected(client: TestClient) -> None:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "AdminPass123!"}
    )
    refresh_token = login_response.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


def test_viewer_cannot_modify_customer(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    viewer = client.post(
        "/api/v1/users",
        json={"name": "Viewer", "email": "viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"},
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "viewer@example.com", "ViewerPass123!")
    forbidden = client.post("/api/v1/customers", json={"company_name": "Blocked"}, headers=viewer_token)
    assert forbidden.status_code == 403


def test_sales_cannot_access_another_users_customer(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales = client.post(
        "/api/v1/users",
        json={"name": "Sales", "email": "sales2@example.com", "password": "SalesPass123!", "role": "Sales"},
        headers=admin_token,
    )
    assert sales.status_code == 201
    customer = client.post(
        "/api/v1/customers", json={"company_name": "Admin Account"}, headers=admin_token
    )
    assert customer.status_code == 201
    sales_token = login(client, "sales2@example.com", "SalesPass123!")
    blocked = client.get(f"/api/v1/customers/{customer.json()['id']}", headers=sales_token)
    assert blocked.status_code == 403
