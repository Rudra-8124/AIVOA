# ─────────────────────────────────────────────────────────────────
# services/interaction_service.py – CRUD for Interaction resource
#
# Handles structured form saves AND AI-extracted saves uniformly.
# ─────────────────────────────────────────────────────────────────

import uuid
from typing import Optional, List, Tuple
from datetime import date

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction, SentimentEnum
from app.models.followup import FollowupAction, FollowupStatusEnum
from app.schemas.interaction import InteractionCreate, InteractionUpdate, ExtractedInteractionData


class InteractionService:
    """
    CRUD + query operations for Interaction records.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Create ────────────────────────────────────────────────────

    async def log_interaction(self, payload: InteractionCreate) -> Interaction:
        """
        Persist a new interaction (from structured form or AI extraction).

        If samples_distributed contains SampleDistributed objects,
        they are serialised to plain dicts for JSONB storage.
        """
        data = payload.model_dump(exclude_none=True)

        # Convert nested Pydantic objects → plain dicts for JSONB
        if "samples_distributed" in data and data["samples_distributed"]:
            data["samples_distributed"] = [
                s if isinstance(s, dict) else s
                for s in data["samples_distributed"]
            ]

        interaction = Interaction(**data)
        self.db.add(interaction)
        await self.db.flush()
        await self.db.refresh(interaction)
        return interaction

    async def log_from_extracted(
        self,
        hcp_id: uuid.UUID,
        extracted: ExtractedInteractionData,
        raw_input: str,
    ) -> Interaction:
        """
        Convenience wrapper: build an InteractionCreate from AI-extracted
        data and delegate to log_interaction.
        Used by the agent's log_interaction tool.
        """
        from datetime import date as date_type
        payload = InteractionCreate(
            hcp_id=hcp_id,
            interaction_type=extracted.interaction_type or "in_person",
            interaction_date=extracted.interaction_date or date_type.today(),
            interaction_time=extracted.interaction_time,
            topics_discussed=extracted.topics_discussed,
            materials_shared=extracted.materials_shared,
            samples_distributed=extracted.samples_distributed,  # type: ignore[arg-type]
            sentiment=extracted.sentiment,
            outcomes=extracted.outcomes,
            raw_input=raw_input,
            extracted_by_ai=True,
        )
        return await self.log_interaction(payload)

    # ── Read single ───────────────────────────────────────────────

    async def get_interaction_by_id(self, interaction_id: uuid.UUID) -> Optional[Interaction]:
        """Return a single interaction by PK, or None."""
        result = await self.db.execute(
            select(Interaction).where(Interaction.id == interaction_id)
        )
        return result.scalar_one_or_none()

    # ── Read list by HCP ──────────────────────────────────────────

    async def get_hcp_interactions(
        self,
        hcp_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        sentiment: Optional[SentimentEnum] = None,
    ) -> Tuple[int, List[Interaction]]:
        """
        Paginated interaction history for a given HCP.

        Returns
        -------
        (total_count, interactions_for_page)
        """
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size

        base_stmt = select(Interaction).where(Interaction.hcp_id == hcp_id)

        if from_date:
            base_stmt = base_stmt.where(Interaction.interaction_date >= from_date)
        if to_date:
            base_stmt = base_stmt.where(Interaction.interaction_date <= to_date)
        if sentiment:
            base_stmt = base_stmt.where(Interaction.sentiment == sentiment)

        # Count total matching rows for pagination metadata
        count_result = await self.db.execute(
            select(func.count()).select_from(base_stmt.subquery())
        )
        total = count_result.scalar_one()

        # Fetch the page
        paged_stmt = base_stmt.order_by(desc(Interaction.interaction_date)).offset(offset).limit(page_size)
        result = await self.db.execute(paged_stmt)
        items = list(result.scalars().all())

        return total, items

    # ── Update ────────────────────────────────────────────────────

    async def edit_interaction(
        self, interaction_id: uuid.UUID, payload: InteractionUpdate
    ) -> Optional[Interaction]:
        """
        Partially update an interaction.
        Only non-None fields in the payload are written to the DB.
        Returns None if the interaction is not found.
        """
        interaction = await self.get_interaction_by_id(interaction_id)
        if not interaction:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(interaction, field, value)

        await self.db.flush()
        await self.db.refresh(interaction)
        return interaction

    # ── Follow-up helpers ─────────────────────────────────────────

    async def create_followup_actions(
        self,
        interaction_id: uuid.UUID,
        hcp_id: uuid.UUID,
        action_descriptions: List[str],
        suggested_by_ai: bool = False,
    ) -> List[FollowupAction]:
        """
        Bulk-insert follow-up actions for an interaction.
        Used by the suggest_followup agent tool.
        """
        followups = []
        for desc in action_descriptions:
            fa = FollowupAction(
                interaction_id=interaction_id,
                hcp_id=hcp_id,
                action_description=desc,
                status=FollowupStatusEnum.pending,
                suggested_by_ai=suggested_by_ai,
            )
            self.db.add(fa)
            followups.append(fa)

        await self.db.flush()
        return followups

    async def get_followups_for_interaction(
        self, interaction_id: uuid.UUID
    ) -> List[FollowupAction]:
        """Return all follow-up actions for a given interaction."""
        result = await self.db.execute(
            select(FollowupAction).where(
                FollowupAction.interaction_id == interaction_id
            ).order_by(FollowupAction.created_at)
        )
        return list(result.scalars().all())

    # ── Statistics helper (used by product recommendation tool) ───

    async def get_topics_for_hcp(self, hcp_id: uuid.UUID) -> List[str]:
        """
        Aggregate all topics discussed across all interactions for an HCP.
        Returns a deduplicated flat list — feeds the product_recommendation tool.
        """
        result = await self.db.execute(
            select(Interaction.topics_discussed).where(
                Interaction.hcp_id == hcp_id,
                Interaction.topics_discussed.isnot(None),
            )
        )
        all_topics: set[str] = set()
        for row in result.scalars().all():
            if row:
                all_topics.update(row)
        return list(all_topics)
