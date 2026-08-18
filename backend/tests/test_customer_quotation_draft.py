from fastapi.testclient import TestClient

from test_crm_api import login


def test_customer_quote_starts_as_blank_draft_then_links_an_opportunity(
    client: TestClient,
) -> None:
    """The formal quotation editor, not the customer entry route, owns quote lines."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Draft Quote Customer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={"sku": "DRAFT-QUOTE-001", "name": "Draft Quote Product", "reference_price": "12.50"},
        headers=admin_token,
    )
    assert product.status_code == 201

    draft = client.post(
        "/api/v1/quotations",
        json={"customer_id": customer.json()["id"]},
        headers=admin_token,
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["opportunity_id"] is None
    assert draft.json()["selected_version"]["items"] == []

    saved = client.put(
        f"/api/v1/quotations/{draft.json()['id']}",
        json={
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "12.50",
                    "quantity": "2",
                }
            ]
        },
        headers=admin_token,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["opportunity_id"] is not None
    assert saved.json()["selected_version"]["total_amount"] == "25.00"

    updated = client.put(
        f"/api/v1/quotations/{draft.json()['id']}",
        json={
            "shipping_cost": "5.00",
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "15.00",
                    "quantity": "3",
                }
            ],
        },
        headers=admin_token,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["selected_version"]["total_amount"] == "50.00"
    opportunity = client.get(
        f"/api/v1/opportunities/{saved.json()['opportunity_id']}", headers=admin_token
    )
    assert opportunity.status_code == 200, opportunity.text
    assert opportunity.json()["amount"] == "50.00"
    assert [
        (item["product_id"], item["quantity"], item["target_price"])
        for item in opportunity.json()["products"]
    ] == [(product.json()["id"], "3.00", "15.00")]
