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
    mail_folder_id: int | None
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
    html_body: str = ""
    bcc_emails: list[str] = Field(default_factory=list)
    thread_key: str | None
    sent_at: datetime | None
    has_attachments: bool
    is_read: bool
    is_starred: bool = False
    is_draft: bool = False
    is_deleted: bool = False
    tracking_enabled: bool
    first_opened_at: datetime | None
    last_opened_at: datetime | None
    open_count: int
    created_at: datetime
    attachments: list[EmailAttachmentRead] = Field(default_factory=list)

    @field_validator("to_emails", "cc_emails", "to_display", "cc_display", "bcc_emails", mode="before")
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


class IndividualSendResult(BaseModel):
    sent: list[EmailMessageRead] = Field(default_factory=list)
    failed_addresses: list[str] = Field(default_factory=list)


class MailFolderCounts(BaseModel):
    inbox: int
    sent: int
    unread: int
    drafts: int = 0
    starred: int = 0


class MailFolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    customer_id: int | None
    bound_addresses: list[str] = Field(default_factory=list)
    message_count: int = 0
    unread_count: int = 0

    @field_validator("bound_addresses", mode="before")
    @classmethod
    def decode_bound_addresses(cls, value: object) -> list[str]:
        return EmailMessageRead.decode_addresses(value)


class MailFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    customer_id: int | None = Field(default=None, gt=0)
    bound_addresses: list[str] = Field(default_factory=list, max_length=50)


class MailFolderUpdate(MailFolderCreate):
    pass
