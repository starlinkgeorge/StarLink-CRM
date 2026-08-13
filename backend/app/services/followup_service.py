from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.followup import FollowUp, FollowUpAttachment
from app.models.opportunity import Opportunity
from app.models.user import User
from app.schemas.followup import FollowUpCreate, FollowUpUpdate
from app.services.errors import ConflictError, NotFoundError
from app.services.storage_service import get_attachment_storage


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
}


def _validate_opportunity(
    session: Session, customer_id: int, opportunity_id: int | None
) -> None:
    if opportunity_id is None:
        return
    opportunity = session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise NotFoundError("Opportunity not found.")
    if opportunity.customer_id != customer_id:
        raise ConflictError("The opportunity does not belong to this customer.")


def _refresh_customer_reminder(
    session: Session, customer_id: int, *, sync_latest_followup_date: bool = False
) -> None:
    """Persist the latest follow-up's reminder on the customer summary row."""
    customer = session.get(Customer, customer_id)
    if customer is None:
        return
    latest = session.scalar(
        select(FollowUp)
        .where(FollowUp.customer_id == customer_id)
        .order_by(FollowUp.followup_date.desc(), FollowUp.created_at.desc(), FollowUp.id.desc())
        .limit(1)
    )
    customer.next_followup_date = latest.next_followup_date if latest else None
    customer.last_followup_at = (
        (latest.updated_at or latest.created_at) if latest else None
    )
    # The archive field is the source for the V1 cadence reminder.  When a
    # user records or edits a follow-up, it becomes the latest actual contact
    # date and immediately drives a newly calculated reminder.  Deletion does
    # not overwrite an imported archive date that may pre-date CRM history.
    if sync_latest_followup_date and latest is not None:
        customer.latest_followup_date = latest.followup_date


def _sync_opportunity_followup_activity(
    session: Session, opportunity_id: int | None, *, touch_activity: bool = False
) -> None:
    """Keep opportunity reminder state in sync without changing follow-up history."""
    if opportunity_id is None:
        return
    opportunity = session.get(Opportunity, opportunity_id)
    if opportunity is None:
        return
    latest = session.scalar(
        select(FollowUp)
        .where(FollowUp.opportunity_id == opportunity_id)
        .order_by(FollowUp.updated_at.desc(), FollowUp.id.desc())
        .limit(1)
    )
    opportunity.last_followup_at = (latest.updated_at or latest.created_at) if latest else None
    if touch_activity:
        opportunity.last_activity_at = datetime.now(timezone.utc)
    if (
        opportunity.quotation_sent_at is not None
        and opportunity.last_followup_at is not None
        and opportunity.last_followup_at >= opportunity.quotation_sent_at
    ):
        # A follow-up recorded after sending a quote completes that quote task.
        opportunity.quote_followup_due_date = None


def get_followup(session: Session, followup_id: int) -> FollowUp:
    followup = session.scalar(
        select(FollowUp)
        .where(FollowUp.id == followup_id)
        .options(selectinload(FollowUp.attachments))
    )
    if followup is None:
        raise NotFoundError("Follow-up record not found.")
    return followup


def create_followup(session: Session, payload: FollowUpCreate) -> FollowUp:
    if session.get(Customer, payload.customer_id) is None:
        raise NotFoundError("Customer not found.")
    if payload.user_id is None or session.get(User, payload.user_id) is None:
        raise NotFoundError("Follow-up user not found.")
    _validate_opportunity(session, payload.customer_id, payload.opportunity_id)
    followup = FollowUp(**payload.model_dump())
    session.add(followup)
    session.flush()
    _refresh_customer_reminder(
        session, followup.customer_id, sync_latest_followup_date=True
    )
    _sync_opportunity_followup_activity(
        session, followup.opportunity_id, touch_activity=True
    )
    session.commit()
    return get_followup(session, followup.id)


def update_followup(session: Session, followup_id: int, payload: FollowUpUpdate) -> FollowUp:
    followup = get_followup(session, followup_id)
    previous_opportunity_id = followup.opportunity_id
    changes = payload.model_dump(exclude_unset=True)
    for required_field in ("type", "followup_date", "content"):
        if required_field in changes and changes[required_field] is None:
            raise ConflictError(f"{required_field} cannot be null.")
    if "opportunity_id" in changes:
        _validate_opportunity(session, followup.customer_id, changes["opportunity_id"])
    for field, value in changes.items():
        setattr(followup, field, value)
    session.flush()
    _refresh_customer_reminder(
        session, followup.customer_id, sync_latest_followup_date=True
    )
    _sync_opportunity_followup_activity(session, previous_opportunity_id)
    _sync_opportunity_followup_activity(
        session, followup.opportunity_id, touch_activity=bool(changes)
    )
    session.commit()
    return get_followup(session, followup.id)


def list_customer_followups(session: Session, customer_id: int) -> list[FollowUp]:
    if session.get(Customer, customer_id) is None:
        raise NotFoundError("Customer not found.")
    statement = (
        select(FollowUp)
        .where(FollowUp.customer_id == customer_id)
        .options(selectinload(FollowUp.attachments))
        .order_by(FollowUp.followup_date.desc(), FollowUp.created_at.desc(), FollowUp.id.desc())
    )
    return list(session.scalars(statement))


async def create_attachment(
    session: Session,
    followup: FollowUp,
    file_name: str,
    content_type: str | None,
    content: bytes,
) -> FollowUpAttachment:
    safe_name = Path(file_name.replace("\\", "/")).name.strip()
    extension = Path(safe_name).suffix.lower()
    if not safe_name or extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ConflictError("Unsupported attachment type.")
    if not content or len(content) > MAX_ATTACHMENT_BYTES:
        raise ConflictError("Attachment must be between 1 byte and 10 MB.")

    stored_name = f"{uuid4().hex}{extension}"
    storage = get_attachment_storage()
    try:
        stored_name = await storage.put(stored_name, content, content_type)
        attachment = FollowUpAttachment(
            followup_id=followup.id,
            file_name=safe_name[:255],
            stored_name=stored_name,
            content_type=(content_type or None)[:100],
            size_bytes=len(content),
        )
        session.add(attachment)
        session.commit()
        session.refresh(attachment)
        return attachment
    except Exception:
        try:
            await storage.delete(stored_name)
        except Exception:
            pass
        session.rollback()
        raise


def get_attachment(session: Session, followup_id: int, attachment_id: int) -> FollowUpAttachment:
    attachment = session.scalar(
        select(FollowUpAttachment).where(
            FollowUpAttachment.id == attachment_id,
            FollowUpAttachment.followup_id == followup_id,
        )
    )
    if attachment is None:
        raise NotFoundError("Follow-up attachment not found.")
    return attachment


async def attachment_bytes(attachment: FollowUpAttachment) -> bytes:
    return await get_attachment_storage().get(attachment.stored_name)


async def delete_attachment(session: Session, attachment: FollowUpAttachment) -> None:
    stored_name = attachment.stored_name
    session.delete(attachment)
    session.commit()
    await get_attachment_storage().delete(stored_name)


async def delete_followup(session: Session, followup: FollowUp) -> None:
    attachment_storage_keys = [
        attachment.stored_name for attachment in followup.attachments
    ]
    customer_id = followup.customer_id
    opportunity_id = followup.opportunity_id
    session.delete(followup)
    session.flush()
    _refresh_customer_reminder(session, customer_id)
    _sync_opportunity_followup_activity(session, opportunity_id)
    session.commit()
    storage = get_attachment_storage()
    for key in attachment_storage_keys:
        await storage.delete(key)
