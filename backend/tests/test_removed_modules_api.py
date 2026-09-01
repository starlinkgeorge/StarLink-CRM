from fastapi.testclient import TestClient


def test_removed_inquiry_and_sales_funnel_routes_are_not_registered(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/inquiries", headers=headers).status_code == 404
    # These strings now reach only the typed opportunity-detail path, so they
    # fail validation instead of exposing the removed Kanban API.
    assert client.get("/api/v1/opportunities/pipeline", headers=headers).status_code == 422
    assert client.get("/api/v1/opportunities/deal-pipeline", headers=headers).status_code == 422

    dashboard = client.get("/api/v1/dashboard/stats", headers=headers)
    assert dashboard.status_code == 200
    assert "today_inquiry_count" not in dashboard.json()
    assert "pending_inquiry_count" not in dashboard.json()

    analytics = client.get("/api/v1/analytics/overview", params={"period": "month"}, headers=headers)
    assert analytics.status_code == 200
    assert "sales_funnel" not in analytics.json()
