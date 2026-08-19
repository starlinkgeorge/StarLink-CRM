"""Regression coverage for Bug Fix Batch A authorization and deletion safety."""

from fastapi.testclient import TestClient

from test_crm_api import login


def _create_user(client: TestClient, *, name: str, email: str, role: str) -> dict:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    response = client.post(
        "/api/v1/users",
        json={
            "name": name,
            "email": email,
            "password": "RolePass123!",
            "role": role,
        },
        headers=admin_token,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _inquiry_payload(company_name: str) -> dict:
    return {
        "company_name": company_name,
        "contact_name": "Buyer",
        "country": "United States",
        "email": f"{company_name.lower().replace(' ', '.')}@example.com",
        "source": "Alibaba",
        "source_platform": "Alibaba International",
        "inquiry_content": "Please quote for preschool furniture.",
    }


def test_inquiry_owner_scope_blocks_sales_idor_but_keeps_admin_and_viewer_rules(
    client: TestClient,
) -> None:
    _create_user(client, name="Sales A", email="sales-a@example.com", role="Sales")
    _create_user(client, name="Sales B", email="sales-b@example.com", role="Sales")
    _create_user(client, name="Viewer", email="viewer@example.com", role="Viewer")
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales_a_token = login(client, "sales-a@example.com", "RolePass123!")
    sales_b_token = login(client, "sales-b@example.com", "RolePass123!")
    viewer_token = login(client, "viewer@example.com", "RolePass123!")

    created = client.post(
        "/api/v1/inquiries",
        json=_inquiry_payload("Sales B Kindergarten"),
        headers=sales_b_token,
    )
    assert created.status_code == 201, created.text
    inquiry_id = created.json()["id"]

    own_listing = client.get("/api/v1/inquiries", headers=sales_b_token)
    assert own_listing.status_code == 200
    assert [item["id"] for item in own_listing.json()["items"]] == [inquiry_id]

    hidden_listing = client.get("/api/v1/inquiries", headers=sales_a_token)
    assert hidden_listing.status_code == 200
    assert hidden_listing.json()["total"] == 0
    # Dashboard counts must use the same ownership scope as the list API.
    assert client.get("/api/v1/dashboard/stats", headers=sales_a_token).json()[
        "today_inquiry_count"
    ] == 0
    assert client.get("/api/v1/dashboard/stats", headers=sales_b_token).json()[
        "today_inquiry_count"
    ] == 1
    assert client.get(f"/api/v1/inquiries/{inquiry_id}", headers=sales_a_token).status_code == 403
    assert client.put(
        f"/api/v1/inquiries/{inquiry_id}",
        json={"status": "Processing"},
        headers=sales_a_token,
    ).status_code == 403
    assert client.post(
        f"/api/v1/inquiries/{inquiry_id}/convert", headers=sales_a_token
    ).status_code == 403

    # Viewer retains the previous organization-wide read-only policy but is
    # denied state-changing operations.
    assert client.get(f"/api/v1/inquiries/{inquiry_id}", headers=viewer_token).status_code == 200
    assert client.put(
        f"/api/v1/inquiries/{inquiry_id}",
        json={"status": "Processing"},
        headers=viewer_token,
    ).status_code == 403
    assert client.post(
        f"/api/v1/inquiries/{inquiry_id}/convert", headers=viewer_token
    ).status_code == 403

    # Admin can manage records owned by either Sales account.
    assert client.put(
        f"/api/v1/inquiries/{inquiry_id}",
        json={"status": "Processing"},
        headers=admin_token,
    ).status_code == 200
    assert client.post(
        f"/api/v1/inquiries/{inquiry_id}/convert", headers=admin_token
    ).status_code == 201


def test_customer_delete_requires_admin_and_preserves_related_business_history(
    client: TestClient,
) -> None:
    sales = _create_user(client, name="Sales Owner", email="sales-owner@example.com", role="Sales")
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales_token = login(client, "sales-owner@example.com", "RolePass123!")

    sales_customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Sales Protected Customer", "owner_id": sales["id"]},
        headers=sales_token,
    )
    assert sales_customer.status_code == 201
    sales_customer_id = sales_customer.json()["id"]
    assert client.delete(
        f"/api/v1/customers/{sales_customer_id}", headers=sales_token
    ).status_code == 403
    assert client.get(
        f"/api/v1/customers/{sales_customer_id}", headers=sales_token
    ).status_code == 200

    protected = client.post(
        "/api/v1/customers",
        json={"company_name": "History Protected Customer"},
        headers=admin_token,
    )
    assert protected.status_code == 201
    customer_id = protected.json()["id"]
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    contact = client.post(
        "/api/v1/contacts",
        json={"customer_id": customer_id, "name": "History Buyer"},
        headers=admin_token,
    )
    assert contact.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": "History Opportunity"},
        headers=admin_token,
    )
    assert opportunity.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer_id,
            "user_id": admin_id,
            "type": "Email",
            "content": "Do not cascade-delete this history.",
        },
        headers=admin_token,
    )
    assert followup.status_code == 201

    blocked = client.delete(f"/api/v1/customers/{customer_id}", headers=admin_token)
    assert blocked.status_code == 409
    assert "1 contact(s)" in blocked.json()["detail"]
    assert "1 opportunity/opportunities" in blocked.json()["detail"]
    assert "1 follow-up record(s)" in blocked.json()["detail"]
    assert client.get(f"/api/v1/customers/{customer_id}", headers=admin_token).status_code == 200
    assert client.get(
        f"/api/v1/opportunities/{opportunity.json()['id']}", headers=admin_token
    ).status_code == 200
    assert client.get(
        "/api/v1/followups", params={"customer_id": customer_id}, headers=admin_token
    ).json()[0]["id"] == followup.json()["id"]

    disposable = client.post(
        "/api/v1/customers",
        json={"company_name": "Disposable Customer"},
        headers=admin_token,
    )
    assert disposable.status_code == 201
    disposable_id = disposable.json()["id"]
    assert client.delete(f"/api/v1/customers/{disposable_id}", headers=admin_token).status_code == 204
    assert client.get(f"/api/v1/customers/{disposable_id}", headers=admin_token).status_code == 404


def test_unlinked_quotation_is_scoped_to_customer_owner_for_sales(
    client: TestClient,
) -> None:
    sales_a = _create_user(client, name="Quote Sales A", email="quote-sales-a@example.com", role="Sales")
    sales_b = _create_user(client, name="Quote Sales B", email="quote-sales-b@example.com", role="Sales")
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales_a_token = login(client, "quote-sales-a@example.com", "RolePass123!")
    sales_b_token = login(client, "quote-sales-b@example.com", "RolePass123!")

    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Sales B Quote Customer", "owner_id": sales_b["id"]},
        headers=admin_token,
    )
    assert customer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "SEC-QUOTE-001",
            "name": "Private Quote Product",
            "reference_price": "99.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer.json()["id"],
            "owner_id": sales_b["id"],
            "name": "Sales B Private Opportunity",
        },
        headers=admin_token,
    )
    assert opportunity.status_code == 201
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "opportunity_id": opportunity.json()["id"],
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "99.00",
                    "quantity": "1",
                }
            ],
        },
        headers=sales_b_token,
    )
    assert quotation.status_code == 201, quotation.text
    quotation_id = quotation.json()["id"]

    # The supported opportunity deletion flow preserves the quote but clears
    # opportunity_id, creating the exact former leakage case.
    assert client.delete(
        f"/api/v1/opportunities/{opportunity.json()['id']}", headers=admin_token
    ).status_code == 204
    retained = client.get(f"/api/v1/quotations/{quotation_id}", headers=sales_b_token)
    assert retained.status_code == 200
    assert retained.json()["opportunity_id"] is None

    sales_a_list = client.get("/api/v1/quotations", headers=sales_a_token)
    assert sales_a_list.status_code == 200
    assert quotation_id not in [item["id"] for item in sales_a_list.json()["items"]]
    assert client.get(f"/api/v1/quotations/{quotation_id}", headers=sales_a_token).status_code == 403
    assert client.put(
        f"/api/v1/quotations/{quotation_id}", json={"shipping_cost": "10.00"}, headers=sales_a_token
    ).status_code == 403
    assert client.get(f"/api/v1/quotations/{quotation_id}/pdf", headers=sales_a_token).status_code == 403
    assert client.get(f"/api/v1/quotations/{quotation_id}/excel", headers=sales_a_token).status_code == 403
    assert client.delete(f"/api/v1/quotations/{quotation_id}", headers=sales_a_token).status_code == 403

    assert client.get("/api/v1/quotations", headers=admin_token).status_code == 200
    assert client.get(f"/api/v1/quotations/{quotation_id}", headers=admin_token).status_code == 200
