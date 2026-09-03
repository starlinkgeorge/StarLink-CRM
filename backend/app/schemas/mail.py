from datetime import datetime

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmailAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    file_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int | None
    created_by_id: int | None
    in_reply_to_id: int | None
    forwarded_from_id: int | None
    folder: str
    direction: str
    subject: str
    from_email: str
    from_name: str | None
    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    to_display: list[str] = Field(default_factory=list)
    cc_display: list[str] = Field(default_factory=list)
    body_text: str
    sent_at: datetime | None
    has_attachments: bool
    is_read: bool
    tracking_enabled: bool
    first_opened_at: datetime | None
    last_opened_at: datetime | None
    open_count: int
    created_at: datetime
    attachments: list[EmailAttachmentRead] = Field(default_factory=list)

    @field_validator("to_emails", "cc_emails", "to_display", "cc_display", mode="before")
    @classmethod
    def decode_addresses(cls, value: object) -> list[str]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return []
        return list(value) if isinstance(value, list) else []


class EmailMessagePage(BaseModel):
    items: list[EmailMessageRead]
    total: int


class MailSyncResult(BaseModel):
    imported: int
    skipped: int
    folders: list[str]
    already_running: bool = False


class MailFolderCounts(BaseModel):
    inbox: int
    sent: int
    unread: int
