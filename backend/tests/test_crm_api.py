from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
import re

from fastapi.testclient import TestClient
from openpyxl import load_workbook


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

    default_page = client.get("/api/v1/customers", headers=sales_token)
    assert default_page.status_code == 200
    assert default_page.json()["limit"] == 10

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


def test_customer_classification_scoring_and_permissions(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    category = client.post(
        "/api/v1/customer-categories",
        json={"name": "Strategic School", "description": "High-value schools", "color": "#0f766e"},
        headers=admin_token,
    )
    assert category.status_code == 201
    category_id = category.json()["id"]
    tag = client.post(
        "/api/v1/tags",
        json={"name": "High Intent", "description": "Ready for quotation", "color": "#dc2626"},
        headers=admin_token,
    )
    assert tag.status_code == 201
    assert tag.json()["color"] == "#dc2626"

    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Scored School", "category_id": category_id, "customer_score": 85},
        headers=admin_token,
    )
    assert customer.status_code == 201
    customer_data = customer.json()
    assert customer_data["customer_score"] == 85
    assert customer_data["level"] == "A"
    customer_id = customer_data["id"]

    linked = client.post(
        f"/api/v1/customers/{customer_id}/tags/{tag.json()['id']}", headers=admin_token
    )
    assert linked.status_code == 200
    scored = client.put(
        f"/api/v1/customers/{customer_id}/score",
        json={"score": 70, "reason": "Strong product fit"},
        headers=admin_token,
    )
    assert scored.status_code == 200
    assert scored.json()["level"] == "B"
    history = client.get(f"/api/v1/customers/{customer_id}/score-history", headers=admin_token)
    assert history.status_code == 200
    assert [item["new_score"] for item in history.json()] == [70, 85]

    filtered = client.get(
        "/api/v1/customers",
        params={"category_id": category_id, "score_min": 60, "score_max": 80},
        headers=admin_token,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    viewer = client.post(
        "/api/v1/users",
        json={"name": "Read Only", "email": "viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"},
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "viewer@example.com", "ViewerPass123!")
    denied = client.put(
        f"/api/v1/customers/{customer_id}/score",
        json={"score": 90},
        headers=viewer_token,
    )
    assert denied.status_code == 403
    denied_category = client.post(
        "/api/v1/customer-categories", json={"name": "Viewer Cannot Create"}, headers=viewer_token
    )
    assert denied_category.status_code == 403


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
    from app.services.followup_reminder_service import shanghai_today

    admin_token = login(client, "admin@example.com", "AdminPass123!")
    users = client.get("/api/v1/users", headers=admin_token)
    admin_id = users.json()[0]["id"]
    today = shanghai_today()

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
    assert payload["week_followup_count"] == 4
    assert [item["customer_name"] for item in payload["today_followups"]] == [
        "Today Customer"
    ]
    assert [item["customer_name"] for item in payload["overdue_followups"]] == [
        "Overdue Customer"
    ]
    assert payload["today_followups"][0]["reminder_status"] == "today"
    assert payload["overdue_followups"][0]["reminder_status"] == "overdue"
    assert payload["due_followups"] == 3


def test_customer_followup_reminder_v1_recalculates_after_a_new_followup(
    client: TestClient,
) -> None:
    from app.services.followup_reminder_service import shanghai_today

    admin_token = login(client, "admin@example.com", "AdminPass123!")
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    today = shanghai_today()
    previous_followup_date = today - timedelta(days=2)
    customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Cadence Customer",
            "customer_acquired_at": "2026-08-12",
            "followup_stage": "已报价",
            "latest_followup_date": previous_followup_date.isoformat(),
        },
        headers=admin_token,
    )
    assert customer.status_code == 201
    assert customer.json()["suggested_followup_date"] == (
        previous_followup_date + timedelta(days=3)
    ).isoformat()

    created_followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer.json()["id"],
            "user_id": admin_id,
            "type": "Email",
            "followup_date": today.isoformat(),
            "content": "Quotation follow-up was sent.",
        },
        headers=admin_token,
    )
    assert created_followup.status_code == 201

    detail = client.get(f"/api/v1/customers/{customer.json()['id']}", headers=admin_token)
    assert detail.status_code == 200
    assert detail.json()["latest_followup_date"] == today.isoformat()
    assert detail.json()["suggested_followup_date"] == (today + timedelta(days=3)).isoformat()

    reminders = client.get("/api/v1/followup-reminders?status=upcoming", headers=admin_token)
    assert reminders.status_code == 200
    reminder = next(item for item in reminders.json()["items"] if item["id"] == customer.json()["id"])
    assert reminder["suggested_followup_date"] == (today + timedelta(days=3)).isoformat()
    assert reminder["followup_reminder"]["status"] == "upcoming"


def test_customer_followup_stage_api_normalizes_legacy_values_and_keeps_cold_automatic(
    client: TestClient,
) -> None:
    from app.services.followup_reminder_service import shanghai_today

    admin_token = login(client, "admin@example.com", "AdminPass123!")
    today = shanghai_today()
    legacy_stage = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Legacy Stage Compatibility Customer",
            "followup_stage": "新开发已回复",
            "response_status": "是",
            "followup_requirement": "需要跟进",
        },
        headers=admin_token,
    )
    assert legacy_stage.status_code == 201
    assert legacy_stage.json()["followup_stage"] == "沟通中"
    assert "response_status" not in legacy_stage.json()
    assert "followup_requirement" not in legacy_stage.json()

    cold = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Automatic Cold Customer",
            "latest_followup_date": (today - timedelta(days=31)).isoformat(),
            "automatic_stage_judgement": "原有自动阶段",
        },
        headers=admin_token,
    )
    assert cold.status_code == 201
    assert cold.json()["automatic_stage_judgement"] == "冷客户"

    exactly_thirty_days = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Thirty Day Customer",
            "latest_followup_date": (today - timedelta(days=30)).isoformat(),
            "automatic_stage_judgement": "原有自动阶段",
        },
        headers=admin_token,
    )
    assert exactly_thirty_days.status_code == 201
    assert exactly_thirty_days.json()["automatic_stage_judgement"] == "原有自动阶段"

    manual_cold = client.post(
        "/api/v1/customers",
        json={"company_name": "No Manual Cold Customer", "followup_stage": "冷客户"},
        headers=admin_token,
    )
    assert manual_cold.status_code == 422


def test_followup_reminders_exclude_legacy_and_unknown_acquisition_dates(
    client: TestClient,
) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    legacy = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Legacy Reminder Customer",
            "customer_acquired_at": "2026-08-11",
            "followup_stage": "已报价",
            "latest_followup_date": "2026-08-10",
        },
        headers=admin_token,
    )
    unknown = client.post(
        "/api/v1/customers",
        json={
            "company_name": "Unknown Acquisition Customer",
            "followup_stage": "已报价",
            "latest_followup_date": "2026-08-10",
        },
        headers=admin_token,
    )
    assert legacy.status_code == 201
    assert unknown.status_code == 201

    for customer in (legacy.json(), unknown.json()):
        assert customer["suggested_followup_date"] is None
        assert customer["calculated_followup_reminder_status"] == "not_applicable"
        assert customer["calculated_followup_reminder_label"] == "不适用"

    reminders = client.get("/api/v1/followup-reminders", headers=admin_token)
    assert reminders.status_code == 200
    assert reminders.json()["items"] == []
    assert reminders.json()["summary"] == {
        "overdue_count": 0,
        "today_count": 0,
        "upcoming_count": 0,
        "unfollowed_count": 0,
    }

    dashboard = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert dashboard.status_code == 200
    assert dashboard.json()["followup_reminder_overdue_count"] == 0
    assert dashboard.json()["followup_reminder_today_count"] == 0
    assert dashboard.json()["followup_reminder_upcoming_count"] == 0
    assert dashboard.json()["followup_reminder_unfollowed_count"] == 0


def test_alibaba_followup_channel_is_supported_and_visible_in_timeline(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    user = client.get("/api/v1/users", headers=admin_token).json()[0]
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Alibaba Follow-up Customer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer.json()["id"],
            "user_id": user["id"],
            "type": "Alibaba",
            "content": "Alibaba inquiry follow-up",
        },
        headers=admin_token,
    )
    assert followup.status_code == 201
    assert followup.json()["type"] == "Alibaba"

    timeline = client.get(
        f"/api/v1/customers/{customer.json()['id']}/timeline",
        headers=admin_token,
    )
    assert timeline.status_code == 200
    assert any(
        item["event_type"] == "followup" and item["followup_type"] == "Alibaba"
        for item in timeline.json()
    )


def test_followup_can_link_opportunity_and_manage_attachments(client: TestClient) -> None:
    """V5 follow-up fields must work without changing the legacy create payload."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "V5 Follow-up Customer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    opportunity = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": "V5 Linked Opportunity"},
        headers=admin_token,
    )
    assert opportunity.status_code == 201

    created = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer_id,
            "user_id": admin_id,
            "opportunity_id": opportunity.json()["id"],
            "type": "WhatsApp",
            "followup_date": date.today().isoformat(),
            "content": "Sent product photos and confirmed the preferred finish.",
            "next_followup_date": (date.today() + timedelta(days=2)).isoformat(),
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    followup = created.json()
    assert followup["opportunity_id"] == opportunity.json()["id"]
    assert followup["followup_date"] == date.today().isoformat()
    assert followup["attachments"] == []

    updated = client.put(
        f"/api/v1/followups/{followup['id']}",
        json={"content": "Buyer confirmed the preferred finish.", "next_followup_date": None},
        headers=admin_token,
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "Buyer confirmed the preferred finish."
    assert updated.json()["next_followup_date"] is None

    uploaded = client.post(
        f"/api/v1/followups/{followup['id']}/attachments",
        files={"file": ("buyer-notes.txt", b"Approved by buyer", "text/plain")},
        headers=admin_token,
    )
    assert uploaded.status_code == 201
    attachment = uploaded.json()
    assert attachment["file_name"] == "buyer-notes.txt"
    customer_center = client.get(
        f"/api/v1/customers/{customer_id}/center", headers=admin_token
    )
    assert customer_center.status_code == 200
    assert customer_center.json()["followups"][0]["attachments"][0]["id"] == attachment["id"]
    downloaded = client.get(
        f"/api/v1/followups/{followup['id']}/attachments/{attachment['id']}",
        headers=admin_token,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"Approved by buyer"

    opportunity_detail = client.get(
        f"/api/v1/opportunities/{opportunity.json()['id']}", headers=admin_token
    )
    assert opportunity_detail.status_code == 200
    assert opportunity_detail.json()["followups"][0]["id"] == followup["id"]
    assert opportunity_detail.json()["followups"][0]["attachments"][0]["id"] == attachment["id"]

    deleted_attachment = client.delete(
        f"/api/v1/followups/{followup['id']}/attachments/{attachment['id']}",
        headers=admin_token,
    )
    assert deleted_attachment.status_code == 204
    deleted_followup = client.delete(
        f"/api/v1/followups/{followup['id']}", headers=admin_token
    )
    assert deleted_followup.status_code == 204
    listing = client.get(
        "/api/v1/followups", params={"customer_id": customer_id}, headers=admin_token
    )
    assert listing.status_code == 200
    assert listing.json() == []


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
    assert converted["opportunity"]["inquiry_content"] == (
        "Need a quotation for three classrooms."
    )

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


def test_opportunity_management_stage_history_and_dashboard(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Global Preschool Group", "contact_name": "Helen"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    created = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer_id,
            "name": "Campus Furniture Project",
            "interested_product": "Preschool furniture package",
            "inquiry_content": "Furniture for five classrooms.",
            "amount": "25000.00",
            "currency": "usd",
            "expected_close_date": "2026-12-31",
            "stage": "Qualified",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    opportunity = created.json()
    assert opportunity["currency"] == "USD"
    assert Decimal(opportunity["amount"]) == Decimal("25000.00")
    assert opportunity["customer_company"] == "Global Preschool Group"

    listing = client.get(
        "/api/v1/opportunities",
        params={"q": "Furniture", "stage": "Qualified", "customer_id": customer_id},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer_id,
            "user_id": admin_id,
            "type": "Meeting",
            "content": "Reviewed the classroom layout.",
        },
        headers=admin_token,
    )
    assert followup.status_code == 201

    proposal = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"stage": "Proposal"},
        headers=admin_token,
    )
    assert proposal.status_code == 200
    won = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"stage": "Won"},
        headers=admin_token,
    )
    assert won.status_code == 200
    detail = won.json()
    assert detail["stage"] == "Won"
    transitions = {
        (item["old_stage"], item["new_stage"])
        for item in detail["stage_history"]
    }
    assert transitions == {
        (None, "Qualified"),
        ("Qualified", "Proposal"),
        ("Proposal", "Won"),
    }
    assert detail["followups"][0]["content"] == "Reviewed the classroom layout."

    dashboard = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert dashboard.status_code == 200
    stats = dashboard.json()
    assert stats["opportunity_count"] == 1
    assert stats["active_opportunity_count"] == 0
    assert stats["won_opportunity_count"] == 1
    assert stats["lost_opportunity_count"] == 0
    assert Decimal(stats["opportunity_amounts"][0]["amount"]) == Decimal("25000.00")


def test_sales_opportunity_scope_and_viewer_read_only(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    sales_users = []
    for index in (1, 2):
        response = client.post(
            "/api/v1/users",
            json={
                "name": f"Opportunity Sales {index}",
                "email": f"opportunity-sales-{index}@example.com",
                "password": "SalesPass123!",
                "role": "Sales",
            },
            headers=admin_token,
        )
        assert response.status_code == 201
        sales_users.append(response.json())
    sales_one_token = login(
        client, "opportunity-sales-1@example.com", "SalesPass123!"
    )
    sales_two_token = login(
        client, "opportunity-sales-2@example.com", "SalesPass123!"
    )
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Owned Account", "owner_id": sales_users[0]["id"]},
        headers=admin_token,
    )
    opportunity = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer.json()["id"], "name": "Owned Opportunity"},
        headers=sales_one_token,
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]
    blocked_detail = client.get(
        f"/api/v1/opportunities/{opportunity_id}", headers=sales_two_token
    )
    assert blocked_detail.status_code == 403
    blocked_update = client.put(
        f"/api/v1/opportunities/{opportunity_id}",
        json={"stage": "Lost"},
        headers=sales_two_token,
    )
    assert blocked_update.status_code == 403
    scoped_list = client.get("/api/v1/opportunities", headers=sales_two_token)
    assert scoped_list.json()["total"] == 0

    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Opportunity Viewer",
            "email": "opportunity-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(
        client, "opportunity-viewer@example.com", "ViewerPass123!"
    )
    assert client.get(
        f"/api/v1/opportunities/{opportunity_id}", headers=viewer_token
    ).status_code == 200
    assert client.put(
        f"/api/v1/opportunities/{opportunity_id}",
        json={"stage": "Lost"},
        headers=viewer_token,
    ).status_code == 403


def test_admin_can_delete_opportunity_without_deleting_related_records(
    client: TestClient,
) -> None:
    """Deleting a sales project retains its customer, quote, product, and follow-up."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Opportunity Deletion School", "contact_name": "Buyer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "DELETE-OPPORTUNITY-001",
            "name": "Opportunity Deletion Table",
            "reference_price": "50.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer.json()["id"],
            "name": "Opportunity Deletion Project",
        },
        headers=admin_token,
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]
    quotation = client.post(
        "/api/v1/quotations",
        json={
            "opportunity_id": opportunity_id,
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "50.00",
                    "quantity": "1",
                }
            ],
        },
        headers=admin_token,
    )
    assert quotation.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer.json()["id"],
            "user_id": admin_id,
            "opportunity_id": opportunity_id,
            "type": "Email",
            "content": "Follow up retained after removing the sales project.",
        },
        headers=admin_token,
    )
    assert followup.status_code == 201

    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Opportunity Deletion Viewer",
            "email": "opportunity-delete-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "opportunity-delete-viewer@example.com", "ViewerPass123!")
    assert client.delete(
        f"/api/v1/opportunities/{opportunity_id}", headers=viewer_token
    ).status_code == 403

    assert client.delete(
        f"/api/v1/opportunities/{opportunity_id}", headers=admin_token
    ).status_code == 204
    assert client.get(
        f"/api/v1/opportunities/{opportunity_id}", headers=admin_token
    ).status_code == 404
    assert client.get(
        f"/api/v1/customers/{customer.json()['id']}", headers=admin_token
    ).status_code == 200
    assert client.get(
        f"/api/v1/products/{product.json()['id']}", headers=admin_token
    ).status_code == 200
    retained_quotation = client.get(
        f"/api/v1/quotations/{quotation.json()['id']}", headers=admin_token
    )
    assert retained_quotation.status_code == 200
    assert retained_quotation.json()["opportunity_id"] is None
    retained_followup = client.get(
        "/api/v1/followups",
        params={"customer_id": customer.json()["id"]},
        headers=admin_token,
    )
    assert retained_followup.status_code == 200
    assert retained_followup.json()[0]["id"] == followup.json()["id"]
    assert retained_followup.json()[0]["opportunity_id"] is None


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


def test_alibaba_inquiry_creates_and_deduplicates_leads(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    integration_status = client.get(
        "/api/v1/integrations/alibaba/status", headers=admin_token
    )
    assert integration_status.status_code == 200
    assert integration_status.json() == {
        "provider": "Alibaba",
        "connected": False,
        "mode": "simulation",
    }

    payload = {
        "company_name": "Bright Future Preschool",
        "contact_name": "Maria Garcia",
        "country": "Spain",
        "email": "maria@brightfuture.example",
        "phone": "+34 900 100 200",
        "whatsapp": "+34 900 100 200",
        "inquiry_content": "Need classroom furniture for September.",
        "interested_product": "Preschool tables and chairs",
        "source": "Website",
    }
    received = client.post(
        "/api/v1/integrations/alibaba/inquiries",
        json=payload,
        headers=admin_token,
    )
    assert received.status_code == 200
    first = received.json()
    assert first["created"] is True
    assert first["lead"]["source"] == "Alibaba"
    assert first["lead"]["status"] == "New"

    duplicate_email = client.post(
        "/api/v1/integrations/alibaba/inquiries",
        json={
            **payload,
            "company_name": "Different Company",
            "contact_name": "Different Buyer",
            "email": " MARIA@BRIGHTFUTURE.EXAMPLE ",
        },
        headers=admin_token,
    )
    assert duplicate_email.status_code == 200
    assert duplicate_email.json()["created"] is False
    assert duplicate_email.json()["lead_id"] == first["lead_id"]

    duplicate_identity = client.post(
        "/api/v1/integrations/alibaba/inquiries",
        json={
            **payload,
            "company_name": " bright future preschool ",
            "contact_name": "MARIA GARCIA",
            "email": "another@example.com",
        },
        headers=admin_token,
    )
    assert duplicate_identity.status_code == 200
    assert duplicate_identity.json()["created"] is False
    assert duplicate_identity.json()["lead_id"] == first["lead_id"]

    leads = client.get("/api/v1/leads", headers=admin_token)
    assert leads.status_code == 200
    assert leads.json()["total"] == 1


def test_viewer_cannot_receive_alibaba_inquiry(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Integration Viewer",
            "email": "integration-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(
        client, "integration-viewer@example.com", "ViewerPass123!"
    )
    blocked = client.post(
        "/api/v1/integrations/alibaba/inquiries",
        json={"company_name": "Blocked Lead", "contact_name": "Read Only"},
        headers=viewer_token,
    )
    assert blocked.status_code == 403


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


def test_product_catalog_and_opportunity_product_lines(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    category = client.post(
        "/api/v1/product-categories",
        json={"name": "Montessori Materials", "sort_order": 10},
        headers=admin_token,
    )
    assert category.status_code == 201

    created = client.post(
        "/api/v1/products",
        json={
            "sku": " sl-pkl-001 ",
            "name": "Pink Tower",
            "category_id": category.json()["id"],
            "material": "Beech wood",
            "dimension_text": "10 graduated cubes",
            "length_mm": "100.00",
            "width_mm": "100.00",
            "height_mm": "600.00",
            "weight_kg": "4.500",
            "unit": "set",
            "moq": 5,
            "reference_price": "48.50",
            "currency_code": "usd",
            "description": "Classic Montessori sensorial material.",
            "images": [
                {"image_url": "https://example.com/pink-tower-main.jpg", "is_primary": True},
                {"image_url": "https://example.com/pink-tower-side.jpg"},
            ],
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    product = created.json()
    assert product["sku"] == "SL-PKL-001"
    assert product["currency_code"] == "USD"
    assert product["category_name"] == "Montessori Materials"
    assert len(product["images"]) == 2
    assert sum(image["is_primary"] for image in product["images"]) == 1

    listing = client.get(
        "/api/v1/products",
        params={"q": "beech", "category_id": category.json()["id"], "is_active": True},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    duplicate = client.post(
        "/api/v1/products",
        json={"sku": "SL-PKL-001", "name": "Duplicate"},
        headers=admin_token,
    )
    assert duplicate.status_code == 409

    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Sunrise Montessori School"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer.json()["id"], "name": "2026 Classroom Order"},
        headers=admin_token,
    )
    assert opportunity.status_code == 201
    linked = client.put(
        f"/api/v1/opportunities/{opportunity.json()['id']}/products",
        json={
            "items": [
                {"product_id": product["id"], "quantity": "20.00", "target_price": "45.00"}
            ]
        },
        headers=admin_token,
    )
    assert linked.status_code == 200
    assert linked.json()["products"][0]["sku"] == "SL-PKL-001"
    assert linked.json()["products"][0]["quantity"] == "20.00"
    assert linked.json()["products"][0]["target_price"] == "45.00"

    disabled = client.put(
        f"/api/v1/products/{product['id']}",
        json={"is_active": False},
        headers=admin_token,
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert client.get(
        "/api/v1/products", params={"is_active": False}, headers=admin_token
    ).json()["total"] == 1
    assert client.delete(
        f"/api/v1/products/{product['id']}", headers=admin_token
    ).status_code == 409


def test_admin_can_delete_an_unlinked_product(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    product = client.post(
        "/api/v1/products",
        json={"sku": "DELETE-001", "name": "Temporary catalog product"},
        headers=admin_token,
    )
    assert product.status_code == 201

    deleted = client.delete(f"/api/v1/products/{product.json()['id']}", headers=admin_token)
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/products/{product.json()['id']}", headers=admin_token
    ).status_code == 404


def test_quotation_catalog_search_handles_skus_and_name_phrases(
    client: TestClient,
) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    pink_tower = client.post(
        "/api/v1/products",
        json={
            "sku": "SL-P-001",
            "name": "Pink Tower",
            "reference_price": "48.50",
        },
        headers=admin_token,
    )
    brown_stair = client.post(
        "/api/v1/products",
        json={
            "sku": "SL-P-026",
            "name": "Brown Stair",
            "reference_price": "52.00",
        },
        headers=admin_token,
    )
    assert pink_tower.status_code == 201
    assert brown_stair.status_code == 201

    # Pasted SKU models are exact matches and are ranked before text matches.
    sku_search = client.get(
        "/api/v1/products/quotation-search",
        params={"q": "SL-P-026   SL-P-001"},
        headers=admin_token,
    )
    assert sku_search.status_code == 200
    assert {item["sku"] for item in sku_search.json()["items"]} == {
        "SL-P-001",
        "SL-P-026",
    }

    # Product names containing spaces remain useful phrases rather than being
    # reduced to unrelated single-word catalogue matches.
    name_search = client.get(
        "/api/v1/products/quotation-search",
        params={"q": "Pink Tower Brown Stair"},
        headers=admin_token,
    )
    assert name_search.status_code == 200
    assert {item["name"] for item in name_search.json()["items"]} == {
        "Pink Tower",
        "Brown Stair",
    }


def test_viewer_has_read_only_product_access(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Product Viewer",
            "email": "product-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={"sku": "VIEW-001", "name": "Visible Product"},
        headers=admin_token,
    )
    assert product.status_code == 201
    viewer_token = login(client, "product-viewer@example.com", "ViewerPass123!")
    assert client.get("/api/v1/products", headers=viewer_token).status_code == 200
    assert client.get(
        f"/api/v1/products/{product.json()['id']}", headers=viewer_token
    ).status_code == 200
    assert client.post(
        "/api/v1/products",
        json={"sku": "BLOCKED", "name": "Blocked"},
        headers=viewer_token,
    ).status_code == 403
    assert client.put(
        f"/api/v1/products/{product.json()['id']}",
        json={"name": "Blocked change"},
        headers=viewer_token,
    ).status_code == 403

    sales = client.post(
        "/api/v1/users",
        json={
            "name": "Product Sales",
            "email": "product-sales@example.com",
            "password": "SalesPass123!",
            "role": "Sales",
        },
        headers=admin_token,
    )
    assert sales.status_code == 201
    sales_token = login(client, "product-sales@example.com", "SalesPass123!")
    sales_product = client.post(
        "/api/v1/products",
        json={"sku": "SALES-001", "name": "Sales-created Product"},
        headers=sales_token,
    )
    assert sales_product.status_code == 201
    assert client.put(
        f"/api/v1/products/{sales_product.json()['id']}",
        json={"material": "Beech wood"},
        headers=sales_token,
    ).status_code == 200
    assert client.delete(
        f"/api/v1/products/{sales_product.json()['id']}", headers=sales_token
    ).status_code == 403


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
    blocked_center = client.get(
        f"/api/v1/customers/{customer.json()['id']}/center", headers=sales_token
    )
    assert blocked_center.status_code == 403


def test_customer_quotation_creates_or_safely_reuses_opportunity(client: TestClient) -> None:
    """Customer-first quotes create one coherent sales record without fuzzy merging."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Customer Quote School", "contact_name": "Buyer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "AUTO-QUOTE-001",
            "name": "Auto Quote Table",
            "unit": "piece",
            "reference_price": "100.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    second_product = client.post(
        "/api/v1/products",
        json={
            "sku": "AUTO-QUOTE-002",
            "name": "Auto Quote Chair",
            "unit": "piece",
            "reference_price": "20.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert second_product.status_code == 201
    customer_id = customer.json()["id"]
    product_id = product.json()["id"]
    second_product_id = second_product.json()["id"]

    invalid = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": 999999, "unit_price": "1", "quantity": "1"}],
        },
        headers=admin_token,
    )
    assert invalid.status_code == 404
    assert client.get(
        "/api/v1/opportunities", params={"customer_id": customer_id}, headers=admin_token
    ).json()["total"] == 0

    create_payload = {
        "customer_id": customer_id,
        "currency": "USD",
        "shipping_cost": "10.00",
        "items": [
            {"product_id": product_id, "unit_price": "100.00", "quantity": "2"},
            {"product_id": second_product_id, "unit_price": "20.00", "quantity": "3"},
        ],
    }
    first = client.post("/api/v1/quotations", json=create_payload, headers=admin_token)
    assert first.status_code == 201
    first_quote = first.json()
    first_opportunity_id = first_quote["opportunity_id"]
    assert first_opportunity_id is not None
    assert first_quote["customer_id"] == customer_id
    assert first_quote["selected_version"]["total_amount"] == "270.00"

    opportunity = client.get(
        f"/api/v1/opportunities/{first_opportunity_id}", headers=admin_token
    )
    assert opportunity.status_code == 200
    assert opportunity.json()["customer_id"] == customer_id
    assert opportunity.json()["sales_stage"] == "Quotation Sent"
    assert opportunity.json()["deal_stage"] == "Quoted"
    # The existing stage-to-probability rule takes precedence over a second rule.
    assert opportunity.json()["probability"] == 60
    assert opportunity.json()["amount"] == "270.00"
    assert [(item["product_id"], item["quantity"], item["target_price"]) for item in opportunity.json()["products"]] == [
        (product_id, "2.00", "100.00"),
        (second_product_id, "3.00", "20.00"),
    ]
    assert [item["id"] for item in opportunity.json()["quotations"]] == [first_quote["id"]]

    # Same customer + exact product set + same currency has one unclosed candidate,
    # so the later quote is a revision of the same sales project, not a duplicate.
    second_payload = {**create_payload, "shipping_cost": "25.00"}
    second = client.post("/api/v1/quotations", json=second_payload, headers=admin_token)
    assert second.status_code == 201
    assert second.json()["opportunity_id"] == first_opportunity_id
    updated_opportunity = client.get(
        f"/api/v1/opportunities/{first_opportunity_id}", headers=admin_token
    ).json()
    assert updated_opportunity["amount"] == "285.00"
    assert {item["id"] for item in updated_opportunity["quotations"]} == {
        first_quote["id"],
        second.json()["id"],
    }

    closed = client.put(
        f"/api/v1/opportunities/{first_opportunity_id}",
        json={"deal_stage": "Won"},
        headers=admin_token,
    )
    assert closed.status_code == 200
    third = client.post("/api/v1/quotations", json=create_payload, headers=admin_token)
    assert third.status_code == 201
    assert third.json()["opportunity_id"] != first_opportunity_id

    # The legacy opportunity-first flow remains authoritative and cannot create an
    # additional opportunity just because the quotation also has products.
    manual = client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "name": "Manual opportunity"},
        headers=admin_token,
    )
    assert manual.status_code == 201
    manual_quote = client.post(
        "/api/v1/quotations",
        json={
            "opportunity_id": manual.json()["id"],
            "items": [{"product_id": product_id, "unit_price": "90.00", "quantity": "1"}],
        },
        headers=admin_token,
    )
    assert manual_quote.status_code == 201
    assert manual_quote.json()["opportunity_id"] == manual.json()["id"]


def test_quotation_versioning_pdf_and_immutable_sent_snapshot(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "QUOTE-CHAIR-001",
            "name": "Preschool Wooden Chair",
            "reference_price": "32.50",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Happy Kids Preschool", "contact_name": "Maria"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer.json()["id"],
            "name": "Classroom Furniture Project",
            "currency": "USD",
        },
        headers=admin_token,
    )
    assert opportunity.status_code == 201
    linked = client.put(
        f"/api/v1/opportunities/{opportunity.json()['id']}/products",
        json={
            "items": [
                {
                    "product_id": product.json()["id"],
                    "quantity": "20.00",
                    "target_price": "30.00",
                }
            ]
        },
        headers=admin_token,
    )
    assert linked.status_code == 200

    created = client.post(
        "/api/v1/quotations",
        json={
            "opportunity_id": opportunity.json()["id"],
            "currency": "USD",
            "payment_term": "30% deposit, balance before shipment",
            "delivery_time": "35 days after deposit",
            "validity_days": 30,
            "shipping_cost": "150.00",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    quotation = created.json()
    quotation_id = quotation["id"]
    assert re.fullmatch(r"SLQ-\d{8}-1", quotation["quotation_number"])
    assert quotation["current_version"] == 1
    assert quotation["status"] == "Draft"
    assert quotation["selected_version"]["subtotal"] == "600.00"
    assert quotation["selected_version"]["total_amount"] == "750.00"
    assert quotation["selected_version"]["items"][0]["product_name_snapshot"] == (
        "Preschool Wooden Chair"
    )

    customer_center = client.get(
        f"/api/v1/customers/{customer.json()['id']}/center", headers=admin_token
    )
    assert customer_center.status_code == 200
    center_data = customer_center.json()
    assert center_data["id"] == customer.json()["id"]
    assert [item["id"] for item in center_data["opportunities"]] == [opportunity["id"]]
    assert [item["id"] for item in center_data["quotations"]] == [quotation_id]
    assert any(item["event_type"] == "customer_created" for item in center_data["activities"])
    filtered_listing = client.get(
        "/api/v1/quotations",
        params={"customer_id": customer.json()["id"]},
        headers=admin_token,
    )
    assert filtered_listing.status_code == 200
    assert filtered_listing.json()["total"] == 1

    changed = client.put(
        f"/api/v1/quotations/{quotation_id}",
        json={
            "shipping_cost": "200.00",
            "validity_days": 21,
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "29.00",
                    "quantity": "20.00",
                }
            ],
        },
        headers=admin_token,
    )
    assert changed.status_code == 200
    assert changed.json()["selected_version"]["subtotal"] == "580.00"
    assert changed.json()["selected_version"]["total_amount"] == "780.00"

    blank_optional_fields = client.put(
        f"/api/v1/quotations/{quotation_id}",
        json={
            "payment_term": "",
            "delivery_time": "",
            "shipping_cost": "",
            "validity_days": 0,
            "items": [
                {
                    "product_id": product.json()["id"],
                    "unit_price": "29.00",
                    "quantity": "20.00",
                }
            ],
        },
        headers=admin_token,
    )
    assert blank_optional_fields.status_code == 200
    assert blank_optional_fields.json()["selected_version"]["payment_term"] == (
        "30% deposit, balance before shipment"
    )
    assert blank_optional_fields.json()["selected_version"]["delivery_time"] == (
        "30-45 days after deposit"
    )
    assert blank_optional_fields.json()["selected_version"]["shipping_cost"] == "0.00"
    assert blank_optional_fields.json()["selected_version"]["validity_days"] == 30

    generated = client.post(
        f"/api/v1/quotations/{quotation_id}/pdf", headers=admin_token
    )
    assert generated.status_code == 200
    assert generated.json()["selected_version"]["pdf_url"] is not None
    downloaded = client.get(
        f"/api/v1/quotations/{quotation_id}/pdf", headers=admin_token
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF")
    downloaded_excel = client.get(
        f"/api/v1/quotations/{quotation_id}/excel", headers=admin_token
    )
    assert downloaded_excel.status_code == 200
    assert downloaded_excel.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(downloaded_excel.content), data_only=False)
    worksheet = workbook["Quotation"]
    assert worksheet["A1"].value == "Dalian StarLink International Trade Co., Ltd."
    assert worksheet["E10"].value == "=C10*D10"
    assert worksheet["E12"].value == "=SUM(E10:E10)"
    assert worksheet["E14"].value == "=E12+E13"
    assert worksheet["C10"].fill.fgColor.rgb == "00FFF2CC"

    sent = client.post(
        f"/api/v1/quotations/{quotation_id}/send", headers=admin_token
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "Sent"
    locked = client.put(
        f"/api/v1/quotations/{quotation_id}",
        json={"shipping_cost": "1.00"},
        headers=admin_token,
    )
    assert locked.status_code == 409

    revision = client.post(
        f"/api/v1/quotations/{quotation_id}/versions", headers=admin_token
    )
    assert revision.status_code == 200
    assert revision.json()["current_version"] == 2
    assert revision.json()["status"] == "Draft"
    assert len(revision.json()["versions"]) == 2
    historical = client.get(
        f"/api/v1/quotations/{quotation_id}",
        params={"version_no": 1},
        headers=admin_token,
    )
    assert historical.status_code == 200
    assert historical.json()["selected_version"]["total_amount"] == "780.00"
    assert historical.json()["selected_version"]["items"][0]["unit_price"] == "29.00"

    listing = client.get("/api/v1/quotations", headers=admin_token)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Quotation Viewer",
            "email": "quotation-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "quotation-viewer@example.com", "ViewerPass123!")
    assert client.get(
        f"/api/v1/quotations/{quotation_id}", headers=viewer_token
    ).status_code == 200
    assert client.put(
        f"/api/v1/quotations/{quotation_id}",
        json={"shipping_cost": "10.00"},
        headers=viewer_token,
    ).status_code == 403
    assert client.post(
        f"/api/v1/quotations/{quotation_id}/pdf", headers=viewer_token
    ).status_code == 403
    assert client.get(
        f"/api/v1/quotations/{quotation_id}/excel", headers=viewer_token
    ).status_code == 200
    assert client.delete(
        f"/api/v1/customers/{customer.json()['id']}", headers=admin_token
    ).status_code == 409


def test_admin_can_delete_quotation_without_deleting_sales_records(client: TestClient) -> None:
    """Deleting a quotation removes its snapshots, not the underlying sales records."""
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "Deletion Safety School", "contact_name": "Buyer"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "DELETE-QUOTE-001",
            "name": "Deletion Safety Chair",
            "reference_price": "25.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer.json()["id"],
            "name": "Deletion Safety Project",
            "currency": "USD",
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
                    "unit_price": "25.00",
                    "quantity": "2",
                }
            ],
        },
        headers=admin_token,
    )
    assert quotation.status_code == 201
    quotation_id = quotation.json()["id"]

    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Quotation Deletion Viewer",
            "email": "quotation-delete-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "quotation-delete-viewer@example.com", "ViewerPass123!")
    assert client.delete(
        f"/api/v1/quotations/{quotation_id}", headers=viewer_token
    ).status_code == 403

    assert client.delete(
        f"/api/v1/quotations/{quotation_id}", headers=admin_token
    ).status_code == 204
    assert client.get(
        f"/api/v1/quotations/{quotation_id}", headers=admin_token
    ).status_code == 404
    assert client.get(
        f"/api/v1/customers/{customer.json()['id']}", headers=admin_token
    ).status_code == 200
    assert client.get(
        f"/api/v1/opportunities/{opportunity.json()['id']}", headers=admin_token
    ).status_code == 200
    assert client.get(
        f"/api/v1/products/{product.json()['id']}", headers=admin_token
    ).status_code == 200
    listing = client.get(
        "/api/v1/quotations",
        params={"customer_id": customer.json()["id"]},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_v7_sales_pipeline_keeps_legacy_stage_compatible(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    customer = client.post(
        "/api/v1/customers",
        json={"company_name": "V7 Pipeline School", "contact_name": "Marie"},
        headers=admin_token,
    )
    assert customer.status_code == 201
    created = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer.json()["id"],
            "name": "V7 Furniture Pipeline",
            "amount": "4800.00",
            "currency": "USD",
            "sales_stage": "Contacted",
            "next_action": "Confirm classroom dimensions",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    opportunity = created.json()
    assert opportunity["sales_stage"] == "Contacted"
    assert opportunity["stage"] == "Qualified"
    assert opportunity["probability"] == 20

    legacy_filtered = client.get(
        "/api/v1/opportunities",
        params={"stage": "Qualified"},
        headers=admin_token,
    )
    assert legacy_filtered.status_code == 200
    assert legacy_filtered.json()["total"] == 1
    sales_filtered = client.get(
        "/api/v1/opportunities",
        params={"sales_stage": "Contacted"},
        headers=admin_token,
    )
    assert sales_filtered.status_code == 200
    assert sales_filtered.json()["total"] == 1

    updated = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={
            "sales_stage": "Quotation Sent",
            "probability": 65,
            "expected_close_date": "2026-12-31",
            "next_action": "Review quotation with buyer",
        },
        headers=admin_token,
    )
    assert updated.status_code == 200
    detail = updated.json()
    assert detail["sales_stage"] == "Quotation Sent"
    assert detail["stage"] == "Proposal"
    assert detail["probability"] == 65
    assert detail["next_action"] == "Review quotation with buyer"
    sales_transitions = {
        (item["old_sales_stage"], item["new_sales_stage"])
        for item in detail["sales_stage_history"]
    }
    assert sales_transitions == {
        (None, "Contacted"),
        ("Contacted", "Quotation Sent"),
    }

    pipeline = client.get("/api/v1/opportunities/pipeline", headers=admin_token)
    assert pipeline.status_code == 200
    quotation_column = next(
        item for item in pipeline.json()["columns"] if item["sales_stage"] == "Quotation Sent"
    )
    assert quotation_column["count"] == 1
    assert quotation_column["opportunities"][0]["id"] == opportunity["id"]

    dashboard = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert dashboard.status_code == 200
    stats = dashboard.json()
    quotation_stage = next(
        item
        for item in stats["opportunity_pipeline"]
        if item["sales_stage"] == "Quotation Sent"
    )
    assert quotation_stage["count"] == 1
    assert Decimal(stats["opportunity_total_amounts"][0]["amount"]) == Decimal("4800.00")
    assert stats["pending_followup_customer_count"] == 0


def test_v8_inquiry_lifecycle_conversion_and_dashboard(client: TestClient) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    created = client.post(
        "/api/v1/inquiries",
        json={
            "company_name": "Bright Star Kindergarten",
            "contact_name": "Alice Buyer",
            "country": "United States",
            "email": "alice@brightstar.example",
            "whatsapp": "+1 202 555 0100",
            "source": "Alibaba",
            "source_platform": "Alibaba International",
            "interested_product": "Montessori practical life furniture",
            "inquiry_content": "Please quote for a new preschool classroom.",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    inquiry = created.json()
    assert inquiry["status"] == "New"
    assert inquiry["source_platform"] == "Alibaba International"

    listing = client.get(
        "/api/v1/inquiries",
        params={"q": "Bright Star", "source": "Alibaba", "status": "New"},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    processing = client.put(
        f"/api/v1/inquiries/{inquiry['id']}",
        json={"status": "Processing"},
        headers=admin_token,
    )
    assert processing.status_code == 200
    assert processing.json()["status"] == "Processing"

    before_conversion = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert before_conversion.status_code == 200
    assert before_conversion.json()["today_inquiry_count"] == 1
    assert before_conversion.json()["pending_inquiry_count"] == 1
    assert before_conversion.json()["inquiry_source_stats"] == [
        {"source": "Alibaba", "count": 1}
    ]

    conversion = client.post(
        f"/api/v1/inquiries/{inquiry['id']}/convert", headers=admin_token
    )
    assert conversion.status_code == 201
    converted = conversion.json()
    assert converted["inquiry"]["status"] == "Converted"
    assert converted["customer"]["source"] == "Alibaba"
    assert converted["customer"]["source_platform"] == "Alibaba International"
    assert converted["customer"]["original_inquiry"] == (
        "Please quote for a new preschool classroom."
    )
    assert converted["contact"]["name"] == "Alice Buyer"
    assert converted["opportunity"]["stage"] == "Lead"
    assert converted["opportunity"]["sales_stage"] == "New Lead"
    assert converted["opportunity"]["inquiry_content"] == (
        "Please quote for a new preschool classroom."
    )

    duplicate_conversion = client.post(
        f"/api/v1/inquiries/{inquiry['id']}/convert", headers=admin_token
    )
    assert duplicate_conversion.status_code == 409

    after_conversion = client.get("/api/v1/dashboard/stats", headers=admin_token)
    assert after_conversion.status_code == 200
    assert after_conversion.json()["pending_inquiry_count"] == 0

    viewer = client.post(
        "/api/v1/users",
        json={
            "name": "Inquiry Viewer",
            "email": "inquiry-viewer@example.com",
            "password": "ViewerPass123!",
            "role": "Viewer",
        },
        headers=admin_token,
    )
    assert viewer.status_code == 201
    viewer_token = login(client, "inquiry-viewer@example.com", "ViewerPass123!")
    assert client.get("/api/v1/inquiries", headers=viewer_token).status_code == 200
    assert client.post(
        "/api/v1/inquiries",
        json={
            "company_name": "Viewer Cannot Create",
            "contact_name": "Read Only",
            "inquiry_content": "No permission.",
        },
        headers=viewer_token,
    ).status_code == 403


def test_v9_opportunity_deal_stage_workspace_and_legacy_compatibility(
    client: TestClient,
) -> None:
    admin_token = login(client, "admin@example.com", "AdminPass123!")
    admin_id = client.get("/api/v1/users", headers=admin_token).json()[0]["id"]
    customer = client.post(
        "/api/v1/customers",
        json={
            "company_name": "V9 International Preschool",
            "contact_name": "Primary Buyer",
            "country": "Canada",
            "email": "buyer@v9-preschool.example",
        },
        headers=admin_token,
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    contact = client.post(
        "/api/v1/contacts",
        json={
            "customer_id": customer_id,
            "name": "V9 Purchase Manager",
            "position": "Purchasing Manager",
            "email": "purchasing@v9-preschool.example",
        },
        headers=admin_token,
    )
    assert contact.status_code == 201

    created = client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer_id,
            "name": "V9 Classroom Furniture Order",
            "interested_product": "Solid wood classroom tables",
            "amount": "6200.00",
            "currency": "USD",
            "deal_stage": "Quoted",
            "probability": 60,
            "expected_close_date": "2026-12-31",
            "next_action": "Confirm delivery port with buyer",
        },
        headers=admin_token,
    )
    assert created.status_code == 201
    opportunity = created.json()
    assert opportunity["deal_stage"] == "Quoted"
    assert opportunity["sales_stage"] == "Quotation Sent"
    assert opportunity["stage"] == "Proposal"
    assert opportunity["amount"] == "6200.00"
    assert opportunity["probability"] == 60
    assert opportunity["expected_close_date"] == "2026-12-31"

    product = client.post(
        "/api/v1/products",
        json={
            "sku": "V9-TABLE-001",
            "name": "V9 Solid Wood Table",
            "reference_price": "120.00",
            "currency_code": "USD",
        },
        headers=admin_token,
    )
    assert product.status_code == 201
    linked = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/products",
        json={
            "items": [
                {
                    "product_id": product.json()["id"],
                    "quantity": "10.00",
                    "target_price": "115.00",
                }
            ]
        },
        headers=admin_token,
    )
    assert linked.status_code == 200

    quotation = client.post(
        "/api/v1/quotations",
        json={"opportunity_id": opportunity["id"], "currency": "USD"},
        headers=admin_token,
    )
    assert quotation.status_code == 201
    followup = client.post(
        "/api/v1/followups",
        json={
            "customer_id": customer_id,
            "user_id": admin_id,
            "opportunity_id": opportunity["id"],
            "type": "Alibaba",
            "content": "Buyer reviewed the first quotation.",
        },
        headers=admin_token,
    )
    assert followup.status_code == 201

    detail_response = client.get(
        f"/api/v1/opportunities/{opportunity['id']}", headers=admin_token
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["customer"]["id"] == customer_id
    assert [item["name"] for item in detail["contacts"]] == ["V9 Purchase Manager"]
    assert detail["products"][0]["sku"] == "V9-TABLE-001"
    assert detail["quotations"][0]["id"] == quotation.json()["id"]
    assert detail["followups"][0]["id"] == followup.json()["id"]
    assert [(item["old_deal_stage"], item["new_deal_stage"]) for item in detail["deal_stage_history"]] == [
        (None, "Quoted")
    ]

    updated = client.put(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"deal_stage": "Negotiating", "probability": 80},
        headers=admin_token,
    )
    assert updated.status_code == 200
    assert updated.json()["deal_stage"] == "Negotiating"
    assert updated.json()["sales_stage"] == "Negotiation"
    assert updated.json()["stage"] == "Negotiation"
    transitions = {
        (item["old_deal_stage"], item["new_deal_stage"])
        for item in updated.json()["deal_stage_history"]
    }
    assert transitions == {(None, "Quoted"), ("Quoted", "Negotiating")}

    listing = client.get(
        "/api/v1/opportunities",
        params={"deal_stage": "Negotiating"},
        headers=admin_token,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    pipeline = client.get("/api/v1/opportunities/deal-pipeline", headers=admin_token)
    assert pipeline.status_code == 200
    negotiating = next(
        column
        for column in pipeline.json()["columns"]
        if column["deal_stage"] == "Negotiating"
    )
    assert negotiating["count"] == 1
    assert negotiating["opportunities"][0]["id"] == opportunity["id"]
