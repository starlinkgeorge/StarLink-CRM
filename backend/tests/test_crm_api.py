from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient


def create_user(client: TestClient) -> dict:
    token = login(client, "admin@example.com", "AdminPass123!")
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Sales User",
            "email": "sales@example.com",
            "password": "SalesPass123!",
            "role": "Sales",
        },
        headers=token,
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_lifecycle_with_contacts_and_followups(client: TestClient) -> None:
    user = create_user(client)
    sales_token = login(client, "sales@example.com", "SalesPass123!")
    create_customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Dalian Montessori School",
            "country": "China",
            "email": "buyer@example.com",
            "customer_type": "Kindergarten",
            "source": "Alibaba",
            "interested_product": "Montessori shelves",
            "level": "A",
            "sales_stage": "Lead",
            "owner_id": user["id"],
        }, headers=sales_token,
    )
    assert create_customer.status_code == 201
    customer = create_customer.json()
    assert customer["customer_type"] == "Kindergarten"
    assert customer["source"] == "Alibaba"
    assert customer["interested_product"] == "Montessori shelves"
    assert customer["sales_stage"] == "Lead"
    assert customer["status"] == "Lead"
    stats = client.get("/api/v1/dashboard/stats", headers=sales_token)
    assert stats.status_code == 200
    assert stats.json()["customer_count"] == 1

    contact = client.post(
        "/api/v1/contacts",
        json={"customer_id": customer["id"], "name": "Li Mei", "position": "Buyer"}, headers=sales_token,
    )
    assert contact.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer["id"],
            "user_id": user["id"],
            "type": "Email",
            "content": "Sent the product catalogue.",
        }, headers=sales_token,
    )
    assert followup.status_code == 201
    stats_after_followup = client.get("/api/v1/dashboard/stats", headers=sales_token)
    assert stats_after_followup.json()["followup_count"] == 1

    detail = client.get(f"/api/v1/customers/{customer['id']}", headers=sales_token)
    assert detail.status_code == 200
    assert detail.json()["contacts"][0]["name"] == "Li Mei"
    assert detail.json()["followups"][0]["type"] == "Email"

    tag = client.post("/api/v1/tags", json={"name": "Alibaba High Priority"}, headers=sales_token)
    assert tag.status_code == 201
    linked = client.post(f"/api/v1/customers/{customer['id']}/tags/{tag.json()['id']}", headers=sales_token)
    assert linked.status_code == 200
    assert linked.json()["tags"][0]["name"] == "Alibaba High Priority"

    listing = client.get("/api/v1/customers", params={"q": "Montessori", "tag_id": tag.json()["id"], "limit": 10}, headers=sales_token)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    unfiltered = client.get(
        "/api/v1/customers",
        params={
            "limit": 20,
            "offset": 0,
            "q": "",
            "status": "",
            "level": "",
            "country": "",
            "source": "",
        },
        headers=sales_token,
    )
    assert unfiltered.status_code == 200
    assert unfiltered.json()["total"] == 1

    invalid_filter = client.get(
        "/api/v1/customers", params={"status": "NotAStatus"}, headers=sales_token
    )
    assert invalid_filter.status_code == 422

    update = client.put(f"/api/v1/customers/{customer['id']}", json={"status": "Contacted"}, headers=sales_token)
    assert update.status_code == 200
    assert update.json()["status"] == "Contacted"
    assert update.json()["sales_stage"] == "Contacted"

    stage_update = client.put(
        f"/api/v1/customers/{customer['id']}",
        json={"sales_stage": "Quotation"},
        headers=sales_token,
    )
    assert stage_update.status_code == 200
    assert stage_update.json()["sales_stage"] == "Quotation"
    assert stage_update.json()["status"] == "Quotation"

    timeline = client.get(
        f"/api/v1/customers/{customer['id']}/timeline", headers=sales_token
    )
    assert timeline.status_code == 200
    activities = timeline.json()
    assert {activity["event_type"] for activity in activities} == {
        "customer_created",
        "followup",
        "status_changed",
    }
    assert sum(activity["event_type"] == "status_changed" for activity in activities) == 2
    assert any(
        activity["event_type"] == "followup"
        and activity["followup_type"] == "Email"
        and activity["content"] == "Sent the product catalogue."
        for activity in activities
    )
    status_transitions = {
        (activity["old_status"], activity["new_status"])
        for activity in activities
        if activity["event_type"] == "status_changed"
    }
    assert status_transitions == {("Lead", "Contacted"), ("Contacted", "Quotation")}
    activity_times = [datetime.fromisoformat(activity["occurred_at"]) for activity in activities]
    assert activity_times == sorted(activity_times, reverse=True)

    existing_followups = client.get(
        "/api/v1/followups",
        params={"customer_id": customer["id"]},
        headers=sales_token,
    )
    assert existing_followups.status_code == 200
    assert len(existing_followups.json()) == 1

    delete = client.delete(f"/api/v1/customers/{customer['id']}", headers=sales_token)
    assert delete.status_code == 204


def test_user_email_must_be_unique(client: TestClient) -> None:
    user = create_user(client)
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    users = client.get("/api/v1/users", headers=admin_token)
    assert users.status_code == 200
    assert users.json()[0]["id"] == user["id"]
    detail = client.get(f"/api/v1/users/{user['id']}", headers=admin_token)
    assert detail.status_code == 200
    assert detail.json()["email"] == "sales@example.com"
    duplicate = client.post(
        "/api/v1/users",
        json={"name": "Another", "email": "sales@example.com", "password": "AnotherPass123!"},
        headers=admin_token,
    )
    assert duplicate.status_code == 409


def test_dashboard_separates_today_and_overdue_customer_reminders(
    client: TestClient,
) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    users = client.get("/api/v1/users", headers=admin_token)
    admin_id = users.json()[0]["id"]
    today = date.today()

    customers = {}
    for company_name in ("Today Customer", "Overdue Customer", "Future Customer"):
        response = client.post(
            "/api/v1/customers",
            json={"company_name": company_name},
            headers=admin_token,
        )
        assert response.status_code == 201
        customers[company_name] = response.json()["id"]

    reminders = [
        ("Today Customer", today - timedelta(days=3), "Older reminder"),
        ("Today Customer", today, "Call today"),
        ("Overdue Customer", today - timedelta(days=1), "Overdue call"),
        ("Future Customer", today + timedelta(days=2), "Future call"),
    ]
    for company_name, reminder_date, content in reminders:
        response = client.post(
            "/api/v1/followups",
            json={
                "customer_id": customers[company_name],
                "user_id": admin_id,
                "type": "Phone",
                "content": content,
                "next_followup_date": reminder_date.isoformat(),
            },
            headers=admin_token,
        )
        assert response.status_code == 201

    stats = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["today_followup_count"] == 1
    assert payload["overdue_followup_count"] == 1
    assert [item["customer_name"] for item in payload["today_followups"]] == [
        "Today Customer"
    ]
    assert [item["customer_name"] for item in payload["overdue_followups"]] == [
        "Overdue Customer"
    ]
    assert payload["today_followups"][0]["reminder_status"] == "today"
    assert payload["overdue_followups"][0]["reminder_status"] == "overdue"
    assert payload["due_followups"] == 3


def test_lead_lifecycle_and_transactional_conversion(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    created = client.post(
        "/api/v1/leads",
        json={
            "company_name": "Sunrise Montessori Academy",
            "contact_name": "Anna Lee",
            "country": "Singapore",
            "email": "anna@example.com",
            "phone": "+65 6000 1000",
            "whatsapp": "+65 6000 1000",
            "source": "Alibaba",
            "inquiry_content": "Need a quotation for three classrooms.",
            "interested_product": "Montessori shelves and preschool tables",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    lead = created.json()
    assert lead["status"] == "New"
    assert lead["public_id"]

    listing = client.get(
        "/api/v1/leads",
        params={"q": "three classrooms", "source": "alibaba", "status": "New"},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(f"/api/v1/leads/{lead['id']}", headers=admin_token)
    assert detail.status_code == 200
    assert detail.json()["converted_customer_id"] is None

    conversion = client.post(
        f"/api/v1/leads/{lead['id']}/convert", headers=admin_token
    )
    assert conversion.status_code == 201
    converted = conversion.json()
    assert converted["lead"]["status"] == "Converted"
    assert converted["customer"]["company_name"] == "Sunrise Montessori Academy"
    assert converted["customer"]["source"] == "Alibaba"
    assert converted["customer"]["interested_product"] == (
        "Montessori shelves and preschool tables"
    )
    assert converted["contact"]["name"] == "Anna Lee"
    assert converted["opportunity"]["source_lead_id"] == lead["id"]
    assert converted["opportunity"]["stage"] == "Lead"

    customer_detail = client.get(
        f"/api/v1/customers/{converted['customer']['id']}", headers=admin_token
    )
    assert customer_detail.status_code == 200
    assert customer_detail.json()["contacts"][0]["email"] == "anna@example.com"

    converted_detail = client.get(
        f"/api/v1/leads/{lead['id']}", headers=admin_token
    )
    assert converted_detail.json()["converted_customer_id"] == converted["customer"]["id"]
    assert converted_detail.json()["converted_opportunity_id"] == converted["opportunity"]["id"]

    repeated = client.post(
        f"/api/v1/leads/{lead['id']}/convert", headers=admin_token
    )
    assert repeated.status_code == 409


def test_viewer_cannot_create_or_convert_lead(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Lead Viewer",
            "email": "lead-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    lead = client.post(
        "/api/v1/leads",
        json={"company_name": "Read Only Lead", "contact_name": "Buyer"},
        headers=admin_token,
    )
    assert lead.status_code == 201
    viewer_token = login(client, "lead-viewer@example.com", "ViewerPass123!")
    listing = client.get("/api/v1/leads", headers=viewer_token)
    assert listing.status_code == 200
    blocked_create = client.post(
        "/api/v1/leads",
        json={"company_name": "Blocked", "contact_name": "Viewer"},
        headers=viewer_token,
    )
    assert blocked_create.status_code == 403
    blocked_conversion = client.post(
        f"/api/v1/leads/{lead.json()['id']}/convert", headers=viewer_token
    )
    assert blocked_conversion.status_code == 403


def test_customer_list_supports_v3_profile_filters(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    records = [
        {
            "company_name": "Berlin Montessori Campus",
            "customer_type": "Kindergarten",
            "source": "Alibaba",
            "interested_product": "Montessori shelves and practical life materials",
            "sales_stage": "Quotation",
        },
        {
            "company_name": "Nordic Education Supply",
            "customer_type": "Distributor",
            "source": "Website",
            "interested_product": "Preschool tables and chairs",
            "sales_stage": "Contacted",
        },
    ]
    for record in records:
        response = client.post("/api/v1/customers", json=record, headers=admin_token)
        assert response.status_code == 201

    filters = [
        ({"customer_type": "kindergarten"}, "Berlin Montessori Campus"),
        ({"interested_product": "practical life"}, "Berlin Montessori Campus"),
        ({"sales_stage": "Quotation"}, "Berlin Montessori Campus"),
        ({"source": "alibaba"}, "Berlin Montessori Campus"),
        (
            {
                "customer_type": "Distributor",
                "interested_product": "tables",
                "sales_stage": "Contacted",
                "source": "Website",
            },
            "Nordic Education Supply",
        ),
        ({"status": "Contacted"}, "Nordic Education Supply"),
    ]
    for params, expected_company in filters:
        response = client.get("/api/v1/customers", params=params, headers=admin_token)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["company_name"] == expected_company

    empty_filters = client.get(
        "/api/v1/customers",
        params={
            "customer_type": "",
            "interested_product": "",
            "sales_stage": "",
            "source": "",
        },
        headers=admin_token,
    )
    assert empty_filters.status_code == 200
    assert empty_filters.json()["total"] == 2

    invalid_stage = client.get(
        "/api/v1/customers", params={"sales_stage": "Invalid"}, headers=admin_token
    )
    assert invalid_stage.status_code == 422


def test_login_rejects_invalid_password_and_protects_api(client: TestClient) -> None:
    invalid_login = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "incorrect"}
    )
    assert invalid_login.status_code == 401
    unauthenticated = client.get("/api/v1/customers")
    assert unauthenticated.status_code == 401


def test_refresh_token_rotates_and_old_token_is_rejected(client: TestClient) -> None:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "AdminPass123!"}
    )
    refresh_token = login_response.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


def test_viewer_cannot_modify_customer(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    viewer = client.post(
        "/api/v1/users",
        json={"name": "Viewer", "email": "viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"},
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "viewer@example.com", "ViewerPass123!")
    forbidden = client.post("/api/v1/customers", json={"company_name": "Blocked"}, headers=viewer_token)
    assert forbidden.status_code == 403


def test_sales_cannot_access_another_users_customer(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales = client.post(
        "/api/v1/users",
        json={"name": "Sales", "email": "sales2@example.com", "password": "SalesPass123!", "role": "Sales"},
        headers=admin_token,
    )
    assert sales.status_code == 201
    customer = client.post(
        "/api/v1/customers", json={"company_name": "Admin Account"}, headers=admin_token
    )
    assert customer.status_code == 201
    sales_token = login(client, "sales2@example.com", "SalesPass123!")
    blocked = client.get(f"/api/v1/customers/{customer.json()['id']}", headers=sales_token)
    assert blocked.status_code == 403
    blocked_timeline = client.get(
        f"/api/v1/customers/{customer.json()['id']}/timeline", headers=sales_token
    )
    assert blocked_timeline.status_code == 403
