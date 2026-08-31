from datetime import date

from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _metric(payload: dict[str, object], metric_key: str) -> dict[str, object]:
    return next(item for item in payload["metrics"] if item["metric_key"] == metric_key)


def test_admin_workbench_tasks_daily_metrics_and_note(client: TestClient, monkeypatch) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    day_one = date(2026, 8, 27)
    monkeypatch.setattr("app.services.workbench_service.shanghai_today", lambda: day_one)
    today = day_one
    customer = client.post("/api/v1/customers", json={"company_name": "Workbench Customer", "customer_acquired_at": today.isoformat()}, headers=admin)
    assert customer.status_code == 201
    created = client.post("/api/v1/workbench/tasks", json={"title": "Prepare quote", "due_date": today.isoformat(), "priority": "high", "customer_id": customer.json()["id"]}, headers=admin)
    assert created.status_code == 201
    assert created.json()["customer_name"] == "Workbench Customer"
    updated = client.put("/api/v1/workbench/metrics", json={"metric_group": "customer_development", "metric_key": "facebook", "completed_value": 2, "target_value": 10}, headers=admin)
    assert updated.status_code == 200
    overview = client.get("/api/v1/workbench", headers=admin)
    assert overview.status_code == 200
    assert _metric(overview.json(), "facebook")["completed_value"] == "2.00"
    assert overview.json()["tasks"][0]["title"] == "Prepare quote"
    completed = client.post(f"/api/v1/workbench/tasks/{created.json()['id']}/complete", headers=admin)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    note = client.put("/api/v1/workbench/daily-note", json={"content": "Confirmed factory sample."}, headers=admin)
    assert note.status_code == 200
    assert client.put("/api/v1/workbench/daily-note", json={"content": "Updated note."}, headers=admin).json()["content"] == "Updated note."
    assert client.delete(f"/api/v1/workbench/tasks/{created.json()['id']}", headers=admin).status_code == 204
    day_two = date(2026, 8, 28)
    monkeypatch.setattr("app.services.workbench_service.shanghai_today", lambda: day_two)
    assert client.put("/api/v1/workbench/metrics", json={"metric_group": "customer_development", "metric_key": "facebook", "completed_value": 3, "target_value": 8}, headers=admin).status_code == 200
    assert _metric(client.get("/api/v1/workbench", headers=admin).json(), "facebook")["completed_value"] == "3.00"
    weekly = client.get("/api/v1/workbench?period=week", headers=admin)
    assert weekly.status_code == 200
    assert _metric(weekly.json(), "facebook") == {"metric_group": "customer_development", "metric_key": "facebook", "completed_value": "5.00", "target_value": "18.00"}


def test_workbench_is_admin_only(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    created = client.post("/api/v1/users", json={"name": "Sales", "email": "workbench-sales@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert created.status_code == 201
    sales = _login(client, "workbench-sales@example.com", "SalesPass123!")
    assert client.get("/api/v1/workbench", headers=sales).status_code == 403
    assert client.post("/api/v1/workbench/tasks", json={"title": "Blocked", "due_date": shanghai_today().isoformat(), "priority": "low"}, headers=sales).status_code == 403
