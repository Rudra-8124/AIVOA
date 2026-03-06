# ─────────────────────────────────────────────────────────────────
# schemas/followup.py – Pydantic v2 schemas for FollowupAction
# ─────────────────────────────────────────────────────────────────

import uuid
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.followup import FollowupStatusEnum


class FollowupActionRead(BaseModel):
    """Full follow-up action record returned by GET endpoints."""
    id: uuid.UUID
    interaction_id: uuid.UUID
    hcp_id: uuid.UUID
    action_description: str
    due_date: Optional[date] = None
    status: FollowupStatusEnum
    suggested_by_ai: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowupActionUpdate(BaseModel):
    """
    Request body for PATCH /followups/{id}.
    Allows the rep to change status or update due date.
    """
    status: Optional[FollowupStatusEnum] = None
    due_date: Optional[date] = None
    action_description: Optional[str] = Field(None, min_length=1)
