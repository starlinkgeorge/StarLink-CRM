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


def _opportunity_quotation(client: TestClient, token: dict, customer_id: int, name: str):
    product = client.post(
        "/api/v1/products",
        json={"sku": f"WON-{name}", "name": f"Won order {name}", "reference_price": "123.45"},
        headers=token,
    )
    assert product.status_code == 201, product.text
    opportunity = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": f"Won opportunity {name}"},
        headers=token,
    )
    assert opportunity.status_code == 201, opportunity.text
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer_id,
            "opportunity_id": opportunity.json()["id"],
            "currency": "USD",
            "items": [{"product_id": product.json()["id"], "unit_price": "123.45", "quantity": "2"}],
        },
        headers=token,
    )
    assert quotation.status_code == 201, quotation.text
    return opportunity.json(), quotation.json()


def test_winning_opportunity_creates_and_reuses_the_quotation_order(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    customer_id = _customer(client, admin, "Won Order Customer")
    opportunity, quotation = _opportunity_quotation(client, admin, customer_id, "AUTO")

    won = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"deal_stage": "Won"},
        headers=admin,
    )
    assert won.status_code == 200, won.text
    body = won.json()
    assert body["order_auto_created"] is True
    assert body["order_no"] == quotation["quotation_number"]
    assert body["order_id"] is not None
    order = client.get(f"/api/v1/orders/{body['order_id']}", headers=admin)
    assert order.status_code == 200, order.text
    assert order.json()["customer_id"] == customer_id
    assert order.json()["opportunity_id"] == opportunity["id"]
    assert order.json()["quotation_id"] == quotation["id"]
    assert order.json()["currency"] == quotation["currency"]
    assert Decimal(order.json()["order_amount"]) == Decimal(quotation["total_amount"])
    # Retain the commercial trail: an order-linked opportunity cannot be deleted.
    assert client.delete(f"/api/v1/opportunities/{opportunity['id']}", headers=admin).status_code == 409

    repeat = client.put(f"/api/v1/opportunities/{opportunity['id']}", json={"deal_stage": "Won"}, headers=admin)
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["order_auto_created"] is None
    assert client.get("/api/v1/orders", params={"customer_id": customer_id, "limit": 100, "offset": 0}, headers=admin).json()["total"] == 1

    assert client.put(f"/api/v1/opportunities/{opportunity['id']}", json={"deal_stage": "Contacted"}, headers=admin).status_code == 200
    won_again = client.put(f"/api/v1/opportunities/{opportunity['id']}", json={"deal_stage": "Won"}, headers=admin)
    assert won_again.status_code == 200, won_again.text
    assert won_again.json()["order_auto_created"] is False
    assert won_again.json()["order_id"] == body["order_id"]
    assert client.get("/api/v1/orders", params={"customer_id": customer_id, "limit": 100, "offset": 0}, headers=admin).json()["total"] == 1


def test_winning_requires_a_quotation_and_respects_opportunity_ownership(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    no_quote_customer = _customer(client, admin, "No Quote Won Customer")
    no_quote = client.post(
        "/api/v1/opportunities",
        json={"customer_id": no_quote_customer, "name": "No quote opportunity"},
        headers=admin,
    )
    assert no_quote.status_code == 201, no_quote.text
    blocked = client.put(f"/api/v1/opportunities/{no_quote.json()['id']}", json={"deal_stage": "Won"}, headers=admin)
    assert blocked.status_code == 409
    assert "没有关联报价单" in blocked.json()["detail"]
    unchanged = client.get(f"/api/v1/opportunities/{no_quote.json()['id']}", headers=admin)
    assert unchanged.json()["deal_stage"] == "New Inquiry"

    viewer_user = client.post("/api/v1/users", json={"name": "Won Viewer", "email": "won-viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"}, headers=admin)
    assert viewer_user.status_code == 201
    viewer = login(client, "won-viewer@example.com", "ViewerPass123!")
    assert client.put(f"/api/v1/opportunities/{no_quote.json()['id']}", json={"deal_stage": "Won"}, headers=viewer).status_code == 403

    sales_a_user = client.post("/api/v1/users", json={"name": "Won Sales A", "email": "won-sales-a@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    sales_b_user = client.post("/api/v1/users", json={"name": "Won Sales B", "email": "won-sales-b@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert sales_a_user.status_code == 201 and sales_b_user.status_code == 201
    sales_a = login(client, "won-sales-a@example.com", "SalesPass123!")
    sales_b = login(client, "won-sales-b@example.com", "SalesPass123!")
    sales_customer = _customer(client, sales_a, "Sales A Won Customer")
    opportunity, _ = _opportunity_quotation(client, sales_a, sales_customer, "SALES")
    forbidden = client.put(f"/api/v1/opportunities/{opportunity['id']}", json={"deal_stage": "Won"}, headers=sales_b)
    assert forbidden.status_code == 403
    assert client.get("/api/v1/orders", params={"customer_id": sales_customer, "limit": 100, "offset": 0}, headers=admin).json()["total"] == 0


def test_existing_won_opportunity_can_be_edited_without_recreating_an_order(client: TestClient) -> None:
    """The order guard applies only to a real transition into Won."""
    admin = login(client, "admin@example.com", "AdminPass123!")
    customer_id = _customer(client, admin, "Existing Won Edit Customer")
    opportunity, _ = _opportunity_quotation(client, admin, customer_id, "EDIT")

    won = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"deal_stage": "Won"},
        headers=admin,
    )
    assert won.status_code == 200, won.text
    order_id = won.json()["order_id"]

    note_update = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"next_action": "Confirm production artwork"},
        headers=admin,
    )
    assert note_update.status_code == 200, note_update.text
    assert note_update.json()["next_action"] == "Confirm production artwork"
    assert note_update.json()["order_id"] == order_id

    amount_update = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"amount": "999.99", "probability": 100},
        headers=admin,
    )
    assert amount_update.status_code == 200, amount_update.text
    assert Decimal(amount_update.json()["amount"]) == Decimal("999.99")
    assert amount_update.json()["order_id"] == order_id
    assert client.get("/api/v1/orders", params={"customer_id": customer_id, "limit": 100, "offset": 0}, headers=admin).json()["total"] == 1


def test_historical_won_backfill_is_admin_only_and_idempotent(client: TestClient) -> None:
    admin = login(client, "admin@example.com", "AdminPass123!")
    sales_user = client.post(
        "/api/v1/users",
        json={"name": "Backfill Sales", "email": "backfill-sales@example.com", "password": "SalesPass123!", "role": "Sales"},
        headers=admin,
    )
    assert sales_user.status_code == 201
    sales = login(client, "backfill-sales@example.com", "SalesPass123!")
    customer_id = _customer(client, admin, "Historical Won Customer")

    product = client.post(
        "/api/v1/products",
        json={"sku": "HIST-WON-1", "name": "Historical Won Product", "reference_price": "88.00"},
        headers=admin,
    )
    assert product.status_code == 201, product.text
    historical = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": "Historical won with quote", "deal_stage": "Won"},
        headers=admin,
    )
    assert historical.status_code == 201, historical.text
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer_id,
            "opportunity_id": historical.json()["id"],
            "currency": "USD",
            "items": [{"product_id": product.json()["id"], "unit_price": "88.00", "quantity": "2"}],
        },
        headers=admin,
    )
    assert quotation.status_code == 201, quotation.text
    without_quote = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": "Historical won without quote", "deal_stage": "Won"},
        headers=admin,
    )
    assert without_quote.status_code == 201, without_quote.text

    assert client.get("/api/v1/orders/won-backfill/preview", headers=sales).status_code == 403
    assert client.post("/api/v1/orders/won-backfill", json={}, headers=sales).status_code == 403

    preview = client.get("/api/v1/orders/won-backfill/preview", headers=admin)
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["total_won"] >= 2
    quoted_candidate = next(item for item in preview_body["candidates"] if item["opportunity_id"] == historical.json()["id"])
    no_quote_candidate = next(item for item in preview_body["candidates"] if item["opportunity_id"] == without_quote.json()["id"])
    assert quoted_candidate["quotation_id"] == quotation.json()["id"]
    assert no_quote_candidate["reason"] is not None

    # SQLite test timestamps are intentionally timezone-naive, so an Admin must
    # explicitly approve the fallback business date before creation.
    built = client.post(
        "/api/v1/orders/won-backfill",
        json={"fallback_order_date": "2026-08-19"},
        headers=admin,
    )
    assert built.status_code == 200, built.text
    assert built.json()["created"] == 1
    order = built.json()["created_orders"][0]
    assert order["opportunity_id"] == historical.json()["id"]
    assert order["quotation_id"] == quotation.json()["id"]
    assert order["order_no"] == quotation.json()["quotation_number"]

    repeated = client.post(
        "/api/v1/orders/won-backfill",
        json={"fallback_order_date": "2026-08-19"},
        headers=admin,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["created"] == 0
    assert repeated.json()["already_ordered"] >= 1
