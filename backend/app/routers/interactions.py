# ─────────────────────────────────────────────────────────────────
# routers/interactions.py – API routes for Interaction resource
#
# Routes:
#   POST   /interactions/log              – Log from frontend form (hcp_name)
#   POST   /interaction/log               – Log a new interaction (hcp_id)
#   PUT    /interaction/edit/{id}         – Edit an existing interaction
#   GET    /interaction/history/{hcp_id}  – Get HCP interaction history
#   GET    /interaction/{id}              – Get a single interaction
# ─────────────────────────────────────────────────────────────────

import uuid
from typing import Optional, List
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.interaction_service import InteractionService
from app.services.hcp_service import HCPService
from app.schemas.interaction import (
    InteractionCreate,
    InteractionUpdate,
    InteractionRead,
    InteractionListRead,
)
from app.schemas.hcp import HCPCreate
from app.models.interaction import InteractionTypeEnum, SentimentEnum

router = APIRouter(prefix="/interaction", tags=["Interactions"])

# ── Secondary router for /interactions (plural) ───────────────────
# The frontend form POSTs to /api/interactions/log with hcp_name.
plural_router = APIRouter(prefix="/interactions", tags=["Interactions"])


class FormInteractionPayload(BaseModel):
    """
    Payload accepted from the React frontend form.
    Uses hcp_name (string) instead of hcp_id (UUID) —
    the endpoint resolves or auto-creates the HCP internally.
    """
    hcp_name: str
    interaction_type: str = "in_person"
    interaction_date: str = ""
    interaction_time: Optional[str] = None
    attendees: Optional[str] = None
    topics_discussed: Optional[List[str]] = None
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[dict]] = None
    sentiment: Optional[str] = None
    outcomes: Optional[str] = None
    followup_actions: Optional[List[str]] = None
    extracted_by_ai: bool = False


@plural_router.post(
    "/log",
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new HCP interaction from the frontend form",
)
async def log_interaction_from_form(
    payload: FormInteractionPayload,
    db: AsyncSession = Depends(get_db),
) -> InteractionRead:
    """
    Accepts the React form payload (hcp_name as string).
    Resolves or auto-creates the HCP, then persists the interaction.
    """
    hcp_svc = HCPService(db)
    int_svc = InteractionService(db)

    # Resolve or auto-create HCP
    hcp = await hcp_svc.get_hcp_by_name(payload.hcp_name)
    if not hcp:
        hcp = await hcp_svc.create_hcp(HCPCreate(name=payload.hcp_name))

    # Parse date
    try:
        parsed_date = (
            date.fromisoformat(payload.interaction_date)
            if payload.interaction_date
            else date.today()
        )
    except ValueError:
        parsed_date = date.today()

    # Parse time
    parsed_time: Optional[time] = None
    if payload.interaction_time:
        try:
            parts = payload.interaction_time.strip().split(":")
            parsed_time = time(int(parts[0]), int(parts[1]))
        except Exception:
            pass

    # Map enums
    try:
        itype = InteractionTypeEnum(payload.interaction_type.lower())
    except ValueError:
        itype = InteractionTypeEnum.in_person

    sent: Optional[SentimentEnum] = None
    if payload.sentiment:
        try:
            sent = SentimentEnum(payload.sentiment.lower())
        except ValueError:
            pass

    create_payload = InteractionCreate(
        hcp_id=hcp.id,
        interaction_type=itype,
        interaction_date=parsed_date,
        interaction_time=parsed_time,
        topics_discussed=payload.topics_discussed or [],
        materials_shared=payload.materials_shared or [],
        samples_distributed=None,   # samples_distributed needs product UUIDs; skip for now
        sentiment=sent,
        outcomes=payload.outcomes,
        extracted_by_ai=payload.extracted_by_ai,
    )

    interaction = await int_svc.log_interaction(create_payload)
    await db.commit()
    await db.refresh(interaction)
    return interaction  # type: ignore[return-value]


# ── POST /interaction/log ─────────────────────────────────────────

@router.post(
    "/log",
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new HCP interaction",
    description=(
        "Creates a new interaction record. Accepts both structured form data "
        "and AI-extracted payloads (set extracted_by_ai=true)."
    ),
)
async def log_interaction(
    payload: InteractionCreate,
    db: AsyncSession = Depends(get_db),
) -> InteractionRead:
    """
    Persist a new interaction in the database.

    - **hcp_id**: UUID of the HCP (required, must exist in hcps table).
    - **interaction_date**: ISO date string (required).
    - **interaction_type**: Channel used (in_person / phone / email / virtual).
    - **extracted_by_ai**: Set to true when data was extracted by the AI agent.
    """
    svc = InteractionService(db)
    interaction = await svc.log_interaction(payload)
    return interaction  # type: ignore[return-value]


# ── PUT /interaction/edit/{id} ────────────────────────────────────

@router.put(
    "/edit/{interaction_id}",
    response_model=InteractionRead,
    summary="Edit an existing interaction",
    description="Partially update an interaction. Only provided fields are changed.",
)
async def edit_interaction(
    interaction_id: uuid.UUID,
    payload: InteractionUpdate,
    db: AsyncSession = Depends(get_db),
) -> InteractionRead:
    """
    Update specific fields of an interaction record.
    All body fields are optional — only set fields are written.
    """
    svc = InteractionService(db)
    updated = await svc.edit_interaction(interaction_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found.",
        )
    return updated  # type: ignore[return-value]


# ── GET /interaction/history/{hcp_id} ────────────────────────────

@router.get(
    "/history/{hcp_id}",
    response_model=InteractionListRead,
    summary="Get interaction history for an HCP",
    description="Returns paginated interaction history for a specific HCP.",
)
async def get_hcp_interaction_history(
    hcp_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page"),
    from_date: Optional[date] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> InteractionListRead:
    """
    Paginated list of all interactions for a given HCP.

    Supports optional date range filtering via query parameters.
    """
    svc = InteractionService(db)
    total, items = await svc.get_hcp_interactions(
        hcp_id=hcp_id,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
    )
    return InteractionListRead(
        total=total,
        page=page,
        page_size=page_size,
        items=items,  # type: ignore[arg-type]
    )


# ── GET /interaction/{id} ─────────────────────────────────────────

@router.get(
    "/{interaction_id}",
    response_model=InteractionRead,
    summary="Get a single interaction by ID",
)
async def get_interaction(
    interaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InteractionRead:
    """Return a single interaction record by its UUID."""
    svc = InteractionService(db)
    interaction = await svc.get_interaction_by_id(interaction_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found.",
        )
    return interaction  # type: ignore[return-value]
