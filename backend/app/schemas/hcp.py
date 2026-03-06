# ─────────────────────────────────────────────────────────────────
# schemas/hcp.py – Pydantic v2 schemas for the HCP resource
#
# Three schema pattern (industry standard):
#   HCPCreate   – fields accepted when creating a new HCP (POST)
#   HCPUpdate   – all fields optional, used for partial update (PATCH)
#   HCPRead     – full representation returned to the client (GET)
# ─────────────────────────────────────────────────────────────────

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class HCPBase(BaseModel):
    """Shared fields used by both Create and Read schemas."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Dr. Sarah Johnson"])
    specialty: Optional[str] = Field(None, max_length=100, examples=["Cardiology"])
    hospital: Optional[str] = Field(None, max_length=255, examples=["City General Hospital"])
    email: Optional[EmailStr] = Field(None, examples=["dr.johnson@hospital.com"])
    phone: Optional[str] = Field(None, max_length=30, examples=["+1-555-0123"])
    territory: Optional[str] = Field(None, max_length=100, examples=["Northeast Region"])


class HCPCreate(HCPBase):
    """
    Request body for POST /hcp/.
    All fields from HCPBase; name is the only required field.
    """
    pass


class HCPUpdate(BaseModel):
    """
    Request body for PATCH /hcp/{id}.
    Every field is optional – only provided fields are updated.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    specialty: Optional[str] = Field(None, max_length=100)
    hospital: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    territory: Optional[str] = Field(None, max_length=100)


class HCPRead(HCPBase):
    """
    Response schema for GET endpoints.
    Includes server-generated fields (id, timestamps).
    orm_mode (from_attributes) allows construction from SQLAlchemy models.
    """
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
