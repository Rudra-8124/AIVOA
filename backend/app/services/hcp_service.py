# ─────────────────────────────────────────────────────────────────
# services/hcp_service.py – CRUD operations for the HCP resource
#
# All DB operations use the injected AsyncSession.
# Services contain pure business logic; they are called by routers.
# ─────────────────────────────────────────────────────────────────

import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hcp import HCP
from app.schemas.hcp import HCPCreate, HCPUpdate


class HCPService:
    """
    Provides create / read / update / search operations for HCPs.
    Instantiated once per request with the session from Depends(get_db).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Create ────────────────────────────────────────────────────

    async def create_hcp(self, payload: HCPCreate) -> HCP:
        """
        Insert a new HCP record.
        Returns the newly created HCP ORM object (id and timestamps populated).
        """
        hcp = HCP(**payload.model_dump())
        self.db.add(hcp)
        await self.db.flush()   # flush to get DB-generated id without committing
        await self.db.refresh(hcp)
        return hcp

    # ── Read single ───────────────────────────────────────────────

    async def get_hcp_by_id(self, hcp_id: uuid.UUID) -> Optional[HCP]:
        """Return a single HCP by primary key, or None if not found."""
        result = await self.db.execute(select(HCP).where(HCP.id == hcp_id))
        return result.scalar_one_or_none()

    async def get_hcp_by_name(self, name: str) -> Optional[HCP]:
        """
        Case-insensitive name lookup.
        Used by the AI agent to resolve 'Dr Smith' → HCP record.
        """
        result = await self.db.execute(
            select(HCP).where(func.lower(HCP.name).contains(name.lower()))
        )
        return result.scalars().first()

    # ── Read list ─────────────────────────────────────────────────

    async def list_hcps(
        self,
        search: Optional[str] = None,
        territory: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[HCP]:
        """
        Return a paginated list of HCPs with optional filters.

        Parameters
        ----------
        search    : Partial name / hospital search string (case-insensitive).
        territory : Exact territory filter.
        skip      : Pagination offset.
        limit     : Maximum records to return (capped at 100).
        """
        limit = min(limit, 100)
        stmt = select(HCP)

        if search:
            stmt = stmt.where(
                HCP.name.ilike(f"%{search}%") | HCP.hospital.ilike(f"%{search}%")
            )
        if territory:
            stmt = stmt.where(HCP.territory == territory)

        stmt = stmt.offset(skip).limit(limit).order_by(HCP.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Update ────────────────────────────────────────────────────

    async def update_hcp(self, hcp_id: uuid.UUID, payload: HCPUpdate) -> Optional[HCP]:
        """
        Partially update an HCP record.
        Only fields explicitly set in the payload (not None) are written.
        Returns None if the HCP is not found.
        """
        hcp = await self.get_hcp_by_id(hcp_id)
        if not hcp:
            return None

        # Iterate over explicitly set fields only (exclude_unset=True)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(hcp, field, value)

        await self.db.flush()
        await self.db.refresh(hcp)
        return hcp

    # ── Delete ────────────────────────────────────────────────────

    async def delete_hcp(self, hcp_id: uuid.UUID) -> bool:
        """
        Hard-delete an HCP record.
        Returns True on success, False if not found.
        (Cascade deletes all child Interactions via FK constraint.)
        """
        hcp = await self.get_hcp_by_id(hcp_id)
        if not hcp:
            return False

        await self.db.delete(hcp)
        return True
