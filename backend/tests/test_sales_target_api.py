from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_sales_target_uses_orders_and_manual_amounts_separately(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    customer = client.post("/api/v1/customers", json={"company_name": "Sales Target Customer", "customer_acquired_at": today.isoformat()}, headers=admin)
    assert customer.status_code == 201
    order = client.post("/api/v1/orders", json={"order_no": "TARGET-001", "customer_id": customer.json()["id"], "order_date": today.isoformat(), "currency": "USD", "order_amount": "100.00"}, headers=admin)
    assert order.status_code == 201
    target = client.put(f"/api/v1/dashboard/sales-targets/{today.year}", json={"target_amount": "1200.00"}, headers=admin)
    assert target.status_code == 200
    created = client.post("/api/v1/dashboard/other-sales", json={"sale_date": today.isoformat(), "amount": "50.00", "currency": "USD", "note": "Offline order"}, headers=admin)
    assert created.status_code == 201
    eur = client.post("/api/v1/dashboard/other-sales", json={"sale_date": today.isoformat(), "amount": "30.00", "currency": "EUR", "note": "Different currency"}, headers=admin)
    assert eur.status_code == 201
    progress = client.get("/api/v1/dashboard/sales-target-progress", headers=admin)
    assert progress.status_code == 200
    annual = next(item for item in progress.json()["periods"] if item["key"] == "year")
    assert annual["actual_amount"] == "150.00"
    assert progress.json()["annual_analysis"]["crm_order_amount"] == "100.00"
    assert progress.json()["annual_analysis"]["manual_amount"] == "50.00"
    assert next(item for item in progress.json()["currency_breakdown"] if item["currency"] == "EUR")["actual_amount"] == "30.00"
    updated = client.put(f"/api/v1/dashboard/other-sales/{created.json()['id']}", json={"sale_date": today.isoformat(), "amount": "75.00", "currency": "USD", "note": "Updated"}, headers=admin)
    assert updated.status_code == 200
    assert client.delete(f"/api/v1/dashboard/other-sales/{created.json()['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/v1/dashboard/other-sales/{eur.json()['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/v1/dashboard/other-sales?year={today.year}", headers=admin).json() == []


def test_viewer_cannot_modify_sales_target_or_manual_amounts(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    created = client.post("/api/v1/users", json={"name": "Target Viewer", "email": "target-viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"}, headers=admin)
    assert created.status_code == 201
    viewer = _login(client, "target-viewer@example.com", "ViewerPass123!")
    assert client.put("/api/v1/dashboard/sales-targets/2026", json={"target_amount": "1.00"}, headers=viewer).status_code == 403
    assert client.post("/api/v1/dashboard/other-sales", json={"sale_date": "2026-09-01", "amount": "1.00", "currency": "USD", "note": "Blocked"}, headers=viewer).status_code == 403
