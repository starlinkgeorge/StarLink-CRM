from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_persist_settings_and_reminders_use_new_cadence(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    current = client.get("/api/v1/settings", headers=admin)
    assert current.status_code == 200
    settings = current.json()
    settings["followup_rules"].update(
        {
            "rule_start_date": "2026-08-12",
            "quoted_reminder_days": 4,
            "cold_customer_after_days": 20,
        }
    )
    settings["company_profile"]["company_name"] = "StarLink Settings Test"
    settings["quotation_order_defaults"].update(
        {
            "default_currency": "EUR",
            "default_quotation_validity_days": 45,
            "default_payment_term": "Full payment before shipment",
            "default_delivery_time": "20 days",
        }
    )
    saved = client.put("/api/v1/settings", json=settings, headers=admin)
    assert saved.status_code == 200
    assert saved.json()["followup_rules"]["quoted_reminder_days"] == 4
    assert saved.json()["company_profile"]["company_name"] == "StarLink Settings Test"

    today = shanghai_today()
    customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Settings Reminder Customer",
            "customer_acquired_at": today.isoformat(),
            "followup_stage": "已报价",
        },
        headers=admin,
    )
    assert customer.status_code == 201
    reminders = client.get("/api/v1/followup-reminders", headers=admin)
    assert reminders.status_code == 200
    item = next(item for item in reminders.json()["items"] if item["id"] == customer.json()["id"])
    assert item["suggested_followup_date"] == (today.fromordinal(today.toordinal() + 4)).isoformat()

    quote = client.post("/api/v1/quotations", json={"customer_id": customer.json()["id"]}, headers=admin)
    assert quote.status_code == 201
    selected = quote.json()["selected_version"]
    assert selected["currency"] == "EUR"
    assert selected["validity_days"] == 45
    assert selected["payment_term"] == "Full payment before shipment"


def test_rule_start_date_hides_history_until_a_real_followup(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    settings = client.get("/api/v1/settings", headers=admin).json()
    settings["followup_rules"]["rule_start_date"] = "2026-08-12"
    assert client.put("/api/v1/settings", json=settings, headers=admin).status_code == 200
    historical = client.post(
        "/api/v1/customers",
        json={"company_name": "Historical Settings Customer", "customer_acquired_at": "2026-08-11", "followup_stage": "沟通中"},
        headers=admin,
    )
    assert historical.status_code == 201
    reminders = client.get("/api/v1/followup-reminders", headers=admin).json()
    item = next(item for item in reminders["items"] if item["id"] == historical.json()["id"])
    assert item["followup_reminder"]["status"] == "not_applicable"
    assert item["is_cold_customer"] is False


def test_non_admin_cannot_update_system_settings(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "AdminPass123!")
    created = client.post(
        "/api/v1/users",
        json={"name": "Sales", "email": "settings-sales@example.com", "password": "SalesPass123!", "role": "Sales"},
        headers=admin,
    )
    assert created.status_code == 201
    sales = _login(client, "settings-sales@example.com", "SalesPass123!")
    settings = client.get("/api/v1/settings", headers=sales)
    assert settings.status_code == 200
    denied = client.put("/api/v1/settings", json=settings.json(), headers=sales)
    assert denied.status_code == 403
