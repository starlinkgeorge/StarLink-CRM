"""Regression coverage for Admin-only order profit analysis."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.services.followup_reminder_service import shanghai_today
from test_crm_api import login


def _customer(client: TestClient, token: dict, name: str) -> int:
    response = client.post(
        "/api/v1/customers", json={"company_name": name}, headers=token
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _order(
    client: TestClient,
    token: dict,
    customer_id: int,
    order_no: str,
    order_date: date,
    **overrides: object,
):
    payload = {
        "order_no": order_no,
        "customer_id": customer_id,
        "order_date": order_date.isoformat(),
        "currency": "USD",
        "order_amount": "100.00",
        "rmb_received_amount": "1000.00",
        "purchase_cost": "400.00",
        "freight_cost": "100.00",
        **overrides,
    }
    response = client.post("/api/v1/orders", json=payload, headers=token)
    assert response.status_code == 201, response.text
    return response.json()


def test_profit_analysis_excludes_pending_orders_and_keeps_currencies_separate(
    client: TestClient,
) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    first_customer = _customer(client, admin, "Profit First Customer")
    second_customer = _customer(client, admin, "Profit Second Customer")
    _order(client, admin, first_customer, "PROFIT-USD-1", today)
    _order(
        client,
        admin,
        second_customer,
        "PROFIT-EUR-1",
        today,
        currency="EUR",
        order_amount="200.00",
        rmb_received_amount="2000.00",
        purchase_cost="1500.00",
        freight_cost="200.00",
    )
    pending = _order(
        client,
        admin,
        first_customer,
        "PROFIT-PENDING-1",
        today,
        rmb_received_amount=None,
        purchase_cost=None,
        freight_cost=None,
    )
    assert pending["profit_accounting_status"] == "Pending"
    assert pending["profit"] is None

    response = client.get(
        "/api/v1/orders/analytics/profit",
        params={
            "period": "custom",
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
        },
        headers=admin,
    )
    assert response.status_code == 200, response.text
    body = response.json()["selected_summary"]
    assert body["order_count"] == 3
    assert body["accounted_order_count"] == 2
    assert body["pending_order_count"] == 1
    assert Decimal(body["rmb_received_total"]) == Decimal("3000.00")
    assert Decimal(body["purchase_cost_total"]) == Decimal("1900.00")
    assert Decimal(body["freight_cost_total"]) == Decimal("300.00")
    assert Decimal(body["profit_total"]) == Decimal("800.00")
    assert Decimal(body["profit_margin"]) == Decimal("26.66666666666666666666666667")
    assert {item["currency"]: Decimal(item["amount"]) for item in body["order_amounts"]} == {
        "EUR": Decimal("200.00"),
        "USD": Decimal("200.00"),
    }
    assert {item["customer_company"] for item in response.json()["customer_ranking"]} == {
        "Profit First Customer", "Profit Second Customer"
    }
    assert len(response.json()["monthly_trend"]) == 12


def test_profit_analysis_all_pending_and_empty_ranges(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    customer_id = _customer(client, admin, "All Pending Profit Customer")
    _order(
        client, admin, customer_id, "PROFIT-PENDING-ONLY", today,
        rmb_received_amount=None, purchase_cost="50.00", freight_cost="10.00",
    )
    pending = client.get(
        "/api/v1/orders/analytics/profit",
        params={"period": "today"}, headers=admin,
    )
    assert pending.status_code == 200, pending.text
    summary = pending.json()["selected_summary"]
    assert summary["order_count"] == 1
    assert summary["accounted_order_count"] == 0
    assert summary["pending_order_count"] == 1
    assert Decimal(summary["profit_total"]) == Decimal("0")
    assert summary["profit_margin"] is None

    empty = client.get(
        "/api/v1/orders/analytics/profit",
        params={"period": "custom", "start_date": "2020-01-01", "end_date": "2020-01-01"},
        headers=admin,
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["selected_summary"]["order_count"] == 0


def test_profit_periods_custom_boundaries_and_admin_only(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    customer_id = _customer(client, admin, "Profit Boundary Customer")
    _order(client, admin, customer_id, "PROFIT-TODAY-1", today, rmb_received_amount="0.00", purchase_cost="0.00", freight_cost="0.00")
    _order(client, admin, customer_id, "PROFIT-LAST-YEAR-1", date(today.year - 1, 12, 31))
    _order(
        client, admin, customer_id, "PROFIT-LOSS-1", date(today.year - 1, 12, 30),
        rmb_received_amount="100.00", purchase_cost="140.00", freight_cost="20.00",
    )

    same_day = client.get(
        "/api/v1/orders/analytics/profit",
        params={"period": "custom", "start_date": today.isoformat(), "end_date": today.isoformat()},
        headers=admin,
    )
    assert same_day.status_code == 200, same_day.text
    assert same_day.json()["selected_summary"]["order_count"] == 1
    assert same_day.json()["selected_summary"]["profit_margin"] is None

    cross_year = client.get(
        "/api/v1/orders/analytics/profit",
        params={"period": "custom", "start_date": f"{today.year - 1}-12-30", "end_date": f"{today.year}-01-01"},
        headers=admin,
    )
    assert cross_year.status_code == 200, cross_year.text
    assert Decimal(cross_year.json()["selected_summary"]["profit_total"]) == Decimal("440.00")

    for period in ("today", "month", "quarter", "half_year", "year"):
        response = client.get("/api/v1/orders/analytics/profit", params={"period": period}, headers=admin)
        assert response.status_code == 200, response.text
        assert len(response.json()["monthly_trend"]) == 12

    invalid = client.get(
        "/api/v1/orders/analytics/profit",
        params={"period": "custom", "start_date": today.isoformat()},
        headers=admin,
    )
    assert invalid.status_code == 422

    sales_user = client.post(
        "/api/v1/users",
        json={"name": "Profit Sales", "email": "profit-sales@example.com", "password": "SalesPass123!", "role": "Sales"},
        headers=admin,
    )
    assert sales_user.status_code == 201
    sales = login(client, "profit-sales@example.com", "SalesPass123!")
    assert client.get("/api/v1/orders/analytics/profit", headers=sales).status_code == 403
    viewer_user = client.post(
        "/api/v1/users",
        json={"name": "Profit Viewer", "email": "profit-viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"},
        headers=admin,
    )
    assert viewer_user.status_code == 201
    viewer = login(client, "profit-viewer@example.com", "ViewerPass123!")
    assert client.get("/api/v1/orders/analytics/profit", headers=viewer).status_code == 403
