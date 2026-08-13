from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today
from test_crm_api import login


def test_business_analytics_uses_archive_dates_and_current_quotation_version(
    client: TestClient,
) -> None:
    """The dashboard must count business data without using CRM import timestamps."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Analytics Today Customer",
            "contact_name": "Buyer",
            "country": "Canada",
            "source": "RFQ",
            "customer_type": "Online store",
            "interested_product": "Pink Tower",
            "customer_acquired_at": today.isoformat(),
            "followup_stage": "已报价",
        },
        headers=admin_token,
    )
    assert customer.status_code == 201
    previous_customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Analytics Earlier Customer",
            "customer_acquired_at": (today - timedelta(days=40)).isoformat(),
        },
        headers=admin_token,
    )
    assert previous_customer.status_code == 201

    product = client.post(
        "/api/v1/products",
        json={"sku": "AN-001", "name": "Analytics Product", "reference_price": "25.00"},
        headers=admin_token,
    )
    assert product.status_code == 201
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer.json()["id"],
            "currency": "USD",
            "payment_term": "100% before shipment",
            "delivery_time": "30 days",
            "validity_days": 30,
            "shipping_cost": "3.00",
            "items": [{"product_id": product.json()["id"], "unit_price": "25.00", "quantity": "1"}],
        },
        headers=admin_token,
    )
    assert quotation.status_code == 201
    opportunity_id = quotation.json()["opportunity_id"]
    won = client.put(
        f"/api/v1/opportunities/{opportunity_id}",
        json={"deal_stage": "Won"},
        headers=admin_token,
    )
    assert won.status_code == 200
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer.json()["id"],
            "type": "Email",
            "content": "Analytics follow-up",
            "followup_date": today.isoformat(),
        },
        headers=admin_token,
    )
    assert followup.status_code == 201

    overview = client.get("/api/v1/analytics/overview", params={"period": "today"}, headers=admin_token)
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["kpis"]["new_customer_count"] == 1
    assert payload["kpis"]["quotation_count"] == 1
    assert payload["kpis"]["won_opportunity_count"] == 1
    assert payload["kpis"]["quotation_amounts"] == [{"currency": "USD", "amount": "28.00"}]
    assert payload["kpis"]["won_amounts"] == [{"currency": "USD", "amount": "28.00"}]
    assert payload["kpis"]["quote_to_win_rate"] == 100.0
    assert payload["followup_summary"]["created_followup_count"] == 1
    assert payload["source_analysis"] == [{"value": "RFQ", "count": 1, "percentage": 100.0}]


def test_business_analytics_requires_a_complete_custom_range(client: TestClient) -> None:
    token = login(client, "admin@example.com", "AdminPass123!")

    response = client.get(
        "/api/v1/analytics/overview",
        params={"period": "custom", "start_date": "2026-08-01"},
        headers=token,
    )

    assert response.status_code == 422
