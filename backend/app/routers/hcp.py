# ─────────────────────────────────────────────────────────────────
# routers/hcp.py – API routes for HCP (Healthcare Professional) resource
#
# Routes:
#   POST  /hcp/          – Create a new HCP
#   GET   /hcp/          – List HCPs (search + pagination)
#   GET   /hcp/{id}      – Get a single HCP
#   PATCH /hcp/{id}      – Update an HCP
#   DELETE /hcp/{id}     – Delete an HCP
# ─────────────────────────────────────────────────────────────────

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.hcp_service import HCPService
from app.schemas.hcp import HCPCreate, HCPUpdate, HCPRead

router = APIRouter(prefix="/hcp", tags=["HCPs"])


# ── POST /hcp/ ────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=HCPRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new HCP record",
)
async def create_hcp(
    payload: HCPCreate,
    db: AsyncSession = Depends(get_db),
) -> HCPRead:
    """
    Register a new Healthcare Professional in the system.
    The HCP's name is the only required field.
    """
    svc = HCPService(db)
    hcp = await svc.create_hcp(payload)
    return hcp  # type: ignore[return-value]


# ── GET /hcp/ ─────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[HCPRead],
    summary="List all HCPs",
    description="Returns a paginated list with optional name/hospital search and territory filter.",
)
async def list_hcps(
    search: Optional[str] = Query(None, description="Partial name or hospital search"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[HCPRead]:
    svc = HCPService(db)
    return await svc.list_hcps(search=search, territory=territory, skip=skip, limit=limit)  # type: ignore[return-value]


# ── GET /hcp/{id} ─────────────────────────────────────────────────

@router.get(
    "/{hcp_id}",
    response_model=HCPRead,
    summary="Get a single HCP by ID",
)
async def get_hcp(
    hcp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> HCPRead:
    svc = HCPService(db)
    hcp = await svc.get_hcp_by_id(hcp_id)
    if not hcp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HCP {hcp_id} not found.",
        )
    return hcp  # type: ignore[return-value]


# ── PATCH /hcp/{id} ───────────────────────────────────────────────

@router.patch(
    "/{hcp_id}",
    response_model=HCPRead,
    summary="Update an HCP record",
    description="Partially update an HCP. Only provided fields are changed.",
)
async def update_hcp(
    hcp_id: uuid.UUID,
    payload: HCPUpdate,
    db: AsyncSession = Depends(get_db),
) -> HCPRead:
    svc = HCPService(db)
    hcp = await svc.update_hcp(hcp_id, payload)
    if not hcp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HCP {hcp_id} not found.",
        )
    return hcp  # type: ignore[return-value]


# ── DELETE /hcp/{id} ──────────────────────────────────────────────

@router.delete(
    "/{hcp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an HCP and all their interactions",
)
async def delete_hcp(
    hcp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard-deletes the HCP and cascades to all child interaction records."""
    svc = HCPService(db)
    deleted = await svc.delete_hcp(hcp_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HCP {hcp_id} not found.",
        )
