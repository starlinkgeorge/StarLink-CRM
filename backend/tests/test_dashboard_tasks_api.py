from datetime import date

from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_dashboard_tasks_keep_existing_task_behavior(client: TestClient, monkeypatch) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    today = date(2026, 8, 31)
    monkeypatch.setattr("app.services.dashboard_service.shanghai_today", lambda: today)
    customer = client.post("/api/v1/customers", json={"company_name": "Task Customer", "customer_acquired_at": today.isoformat()}, headers=admin)
    assert customer.status_code == 201
    created = client.post("/api/v1/dashboard/tasks", json={"title": "Prepare quote", "due_date": today.isoformat(), "priority": "high", "customer_id": customer.json()["id"]}, headers=admin)
    assert created.status_code == 201
    assert created.json()["customer_name"] == "Task Customer"
    listed = client.get("/api/v1/dashboard/tasks/today", headers=admin)
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Prepare quote"
    completed = client.post(f"/api/v1/dashboard/tasks/{created.json()['id']}/complete", headers=admin)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.delete(f"/api/v1/dashboard/tasks/{created.json()['id']}", headers=admin).status_code == 204


def test_dashboard_task_api_is_admin_only(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    created = client.post("/api/v1/users", json={"name": "Sales", "email": "dashboard-task-sales@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert created.status_code == 201
    sales = _login(client, "dashboard-task-sales@example.com", "SalesPass123!")
    assert client.get("/api/v1/dashboard/tasks/today", headers=sales).status_code == 403
    assert client.post("/api/v1/dashboard/tasks", json={"title": "Blocked", "due_date": "2026-08-31", "priority": "low"}, headers=sales).status_code == 403
