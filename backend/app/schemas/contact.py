from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContactCreate(BaseModel):
    customer_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    position: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    position: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    name: str
    position: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    whatsapp: Optional[str]
    created_at: datetime
