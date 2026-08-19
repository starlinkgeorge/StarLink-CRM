"""Order V1 regression coverage: money, quote uniqueness, RBAC and profit."""

from decimal import Decimal

from fastapi.testclient import TestClient

from test_crm_api import login


def _customer(client: TestClient, token: dict, name: str) -> int:
    response = client.post("/api/v1/customers", json={"company_name": name}, headers=token)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _order(client: TestClient, token: dict, customer_id: int, order_no: str, **overrides: str):
    payload = {
        "order_no": order_no, "customer_id": customer_id, "order_date": "2026-08-19",
        "currency": "USD", "order_amount": "10000.00", "rmb_received_amount": "70850.00",
        "purchase_cost": "42000.00", "freight_cost": "8000.00", **overrides,
    }
    return client.post("/api/v1/orders", json=payload, headers=token)


def test_order_profit_is_decimal_and_can_be_negative(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    customer_id = _customer(client, admin, "Order Profit Customer")
    created = _order(client, admin, customer_id, "SO-PROFIT-1")
    assert created.status_code == 201, created.text
    assert Decimal(created.json()["profit"]) == Decimal("20850.00")
    assert Decimal(created.json()["realized_exchange_rate"]) == Decimal("7.085")
    updated = client.put(f"/api/v1/orders/{created.json()['id']}", json={"rmb_received_amount": "50000.00", "purchase_cost": "45000.00", "freight_cost": "10000.00"}, headers=admin)
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["profit"]) == Decimal("-5000.00")
    assert Decimal(updated.json()["profit_margin"]) == Decimal("-10.0")


def test_order_permissions_and_quotation_can_only_have_one_order(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    user = client.post("/api/v1/users", json={"name": "Order Sales", "email": "order-sales@example.com", "password": "OrderPass123!", "role": "Sales"}, headers=admin)
    assert user.status_code == 201
    sales = login(client, "order-sales@example.com", "OrderPass123!")
    customer_id = _customer(client, admin, "Admin Only Customer")
    assert _order(client, sales, customer_id, "SO-FORBIDDEN-1").status_code == 403
    own_customer = _customer(client, sales, "Sales Own Customer")
    own = _order(client, sales, own_customer, "SO-SALES-1")
    assert own.status_code == 201
    assert client.delete(f"/api/v1/orders/{own.json()['id']}", headers=sales).status_code == 403
    admin_order = _order(client, admin, customer_id, "SO-ADMIN-1")
    assert admin_order.status_code == 201
    assert client.get(f"/api/v1/orders/{admin_order.json()['id']}", headers=sales).status_code == 403

    viewer_user = client.post("/api/v1/users", json={"name": "Order Viewer", "email": "order-viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"}, headers=admin)
    assert viewer_user.status_code == 201
    viewer = login(client, "order-viewer@example.com", "ViewerPass123!")
    assert client.get("/api/v1/orders", headers=viewer).status_code == 200
    assert _order(client, viewer, customer_id, "SO-VIEWER-1").status_code == 403

    product = client.post(
        "/api/v1/products",
        json={"sku": "ORDER-QUOTE-1", "name": "Order Quote Product", "reference_price": "100.00"},
        headers=admin,
    )
    assert product.status_code == 201
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer_id,
            "currency": "USD",
            "items": [{"product_id": product.json()["id"], "unit_price": "100.00", "quantity": "1"}],
        },
        headers=admin,
    )
    assert quotation.status_code == 201, quotation.text
    first = _order(client, admin, customer_id, "SO-QUOTE-1", quotation_id=quotation.json()["id"])
    assert first.status_code == 201, first.text
    assert client.get(f"/api/v1/orders/by-quotation/{quotation.json()['id']}", headers=admin).json()["id"] == first.json()["id"]
    duplicate = _order(client, admin, customer_id, "SO-QUOTE-2", quotation_id=quotation.json()["id"])
    assert duplicate.status_code == 409

    admin_opportunity = client.post("/api/v1/opportunities", json={"customer_id": own_customer, "name": "Admin quote scope"}, headers=admin)
    assert admin_opportunity.status_code == 201
    scoped_quotation = client.post(
        "/api/v1/quotations",
        json={"customer_id": own_customer, "opportunity_id": admin_opportunity.json()["id"], "currency": "USD", "items": [{"product_id": product.json()["id"], "unit_price": "100.00", "quantity": "1"}]},
        headers=admin,
    )
    assert scoped_quotation.status_code == 201, scoped_quotation.text
    assert _order(client, sales, own_customer, "SO-QUOTE-SCOPE-1", quotation_id=scoped_quotation.json()["id"]).status_code == 403
