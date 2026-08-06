from fastapi.testclient import TestClient


def create_user(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Sales User",
            "email": "sales@example.com",
            "password_hash": "development-only-hash",
            "role": "Sales",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_customer_lifecycle_with_contacts_and_followups(client: TestClient) -> None:
    user = create_user(client)
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
        },
    )
    assert create_customer.status_code == 201
    customer = create_customer.json()

    contact = client.post(
        "/api/v1/contacts",
        json={"customer_id": customer["id"], "name": "Li Mei", "position": "Buyer"},
    )
    assert contact.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer["id"],
            "user_id": user["id"],
            "type": "Email",
            "content": "Sent the product catalogue.",
        },
    )
    assert followup.status_code == 201

    detail = client.get(f"/api/v1/customers/{customer['id']}")
    assert detail.status_code == 200
    assert detail.json()["contacts"][0]["name"] == "Li Mei"
    assert detail.json()["followups"][0]["type"] == "Email"

    listing = client.get("/api/v1/customers", params={"q": "Montessori", "limit": 10})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    update = client.put(f"/api/v1/customers/{customer['id']}", json={"status": "Contacted"})
    assert update.status_code == 200
    assert update.json()["status"] == "Contacted"

    delete = client.delete(f"/api/v1/customers/{customer['id']}")
    assert delete.status_code == 204


def test_user_email_must_be_unique(client: TestClient) -> None:
    user = create_user(client)
    users = client.get("/api/v1/users")
    assert users.status_code == 200
    assert users.json()[0]["id"] == user["id"]
    detail = client.get(f"/api/v1/users/{user['id']}")
    assert detail.status_code == 200
    assert detail.json()["email"] == "sales@example.com"
    duplicate = client.post(
        "/api/v1/users",
        json={"name": "Another", "email": "sales@example.com", "password_hash": "hash"},
    )
    assert duplicate.status_code == 409
