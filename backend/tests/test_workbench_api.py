from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_workbench_tasks_note_and_today_stats(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    customer = client.post("/api/v1/customers", json={"company_name": "Workbench Customer", "customer_acquired_at": today.isoformat()}, headers=admin)
    assert customer.status_code == 201
    created = client.post("/api/v1/workbench/tasks", json={"title": "Prepare quote", "due_date": today.isoformat(), "priority": "high", "customer_id": customer.json()["id"]}, headers=admin)
    assert created.status_code == 201
    assert created.json()["customer_name"] == "Workbench Customer"
    overview = client.get("/api/v1/workbench/today", headers=admin)
    assert overview.status_code == 200
    assert overview.json()["metrics"]["new_customers"] == 1
    assert overview.json()["tasks"][0]["title"] == "Prepare quote"
    completed = client.post(f"/api/v1/workbench/tasks/{created.json()['id']}/complete", headers=admin)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.get("/api/v1/workbench/today", headers=admin).json()["metrics"]["completed_tasks"] == 1
    note = client.put("/api/v1/workbench/daily-note", json={"content": "Confirmed factory sample."}, headers=admin)
    assert note.status_code == 200
    assert client.put("/api/v1/workbench/daily-note", json={"content": "Updated note."}, headers=admin).json()["content"] == "Updated note."
    assert client.delete(f"/api/v1/workbench/tasks/{created.json()['id']}", headers=admin).status_code == 204


def test_workbench_is_admin_only(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    created = client.post("/api/v1/users", json={"name": "Sales", "email": "workbench-sales@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert created.status_code == 201
    sales = _login(client, "workbench-sales@example.com", "SalesPass123!")
    assert client.get("/api/v1/workbench/today", headers=sales).status_code == 403
    assert client.post("/api/v1/workbench/tasks", json={"title": "Blocked", "due_date": shanghai_today().isoformat(), "priority": "low"}, headers=sales).status_code == 403
