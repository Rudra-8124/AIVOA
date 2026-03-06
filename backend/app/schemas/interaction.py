# ─────────────────────────────────────────────────────────────────
# schemas/interaction.py – Pydantic v2 schemas for Interaction
#
# Covers structured form entry AND AI-extracted data.
# ExtractedInteractionData is a standalone model shared between
# the chat endpoint and the structured POST endpoint.
# ─────────────────────────────────────────────────────────────────

import uuid
from datetime import datetime, date, time
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.models.interaction import InteractionTypeEnum, SentimentEnum


# ── Shared sub-models ─────────────────────────────────────────────

class SampleDistributed(BaseModel):
    """A single sample record inside an interaction."""
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1)


class ExtractedInteractionData(BaseModel):
    """
    Structured fields extracted from natural language by the AI agent.
    All fields are optional because partial extraction is valid.
    This schema is used both as an agent tool input/output and as
    the inner payload when confirming an AI-extracted interaction.
    """
    hcp_name: Optional[str] = None
    interaction_type: Optional[InteractionTypeEnum] = None
    interaction_date: Optional[date] = None
    interaction_time: Optional[time] = None
    topics_discussed: Optional[List[str]] = None
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[SampleDistributed]] = None
    sentiment: Optional[SentimentEnum] = None
    outcomes: Optional[str] = None
    followup_actions: Optional[List[str]] = None


# ── CRUD schemas ──────────────────────────────────────────────────

class InteractionBase(BaseModel):
    """Fields shared across create / read schemas."""
    hcp_id: uuid.UUID
    interaction_type: InteractionTypeEnum = InteractionTypeEnum.in_person
    interaction_date: date
    interaction_time: Optional[time] = None
    topics_discussed: Optional[List[str]] = Field(None, examples=[["Efficacy of Product X"]])
    materials_shared: Optional[List[str]] = Field(None, examples=[["Brochure", "Clinical study"]])
    samples_distributed: Optional[List[SampleDistributed]] = None
    sentiment: Optional[SentimentEnum] = None
    outcomes: Optional[str] = None
    notes: Optional[str] = None


class InteractionCreate(InteractionBase):
    """
    Request body for POST /interaction/log (structured form).
    Optionally carries the raw NL text and AI-extraction flag.
    """
    raw_input: Optional[str] = Field(
        None,
        description="Original natural-language text if entered via chat",
    )
    extracted_by_ai: bool = False


class InteractionUpdate(BaseModel):
    """
    Request body for PUT /interaction/edit.
    All fields optional — only non-None fields are patched.
    """
    interaction_type: Optional[InteractionTypeEnum] = None
    interaction_date: Optional[date] = None
    interaction_time: Optional[time] = None
    topics_discussed: Optional[List[str]] = None
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[SampleDistributed]] = None
    sentiment: Optional[SentimentEnum] = None
    outcomes: Optional[str] = None
    notes: Optional[str] = None


class InteractionRead(InteractionBase):
    """
    Full interaction record returned by GET endpoints.
    Includes server-generated fields and AI provenance info.
    """
    id: uuid.UUID
    raw_input: Optional[str] = None
    extracted_by_ai: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InteractionListRead(BaseModel):
    """Paginated list wrapper for GET /interaction/history/{hcp_id}."""
    total: int
    page: int
    page_size: int
    items: List[InteractionRead]
