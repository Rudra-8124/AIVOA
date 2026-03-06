# ─────────────────────────────────────────────────────────────────
# ai_agent/tools/edit_interaction.py  –  Tool 2: EditInteractionTool
#
# Full workflow:
#   1. Resolve the target interaction by UUID OR by HCP name + date
#   2. Accept a field-level edit or a full set of changed fields
#   3. Apply partial update via InteractionService
#   4. Return before/after diff in the result for transparent confirmation
# ─────────────────────────────────────────────────────────────────

import logging
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────

class EditInteractionInput(BaseModel):
    """
    The rep can identify the interaction to edit in two ways:
      A) By interaction_id (UUID string) — the most precise way.
      B) By hcp_name + interaction_date — useful when the rep says
         "fix the note from my Dr Smith meeting yesterday".

    Only the fields explicitly provided will be updated.
    """
    # ── Target resolution (at least one required) ─────────────────
    interaction_id: Optional[str] = Field(
        None,
        description="UUID of the specific interaction to edit (preferred).",
    )
    hcp_name: Optional[str] = Field(
        None,
        description="HCP name — used with interaction_date to find the interaction.",
    )
    interaction_date: Optional[str] = Field(
        None,
        description="Date YYYY-MM-DD — used with hcp_name to find the interaction.",
    )

    # ── Fields to update (all optional) ──────────────────────────
    new_interaction_type: Optional[str] = Field(
        None, description="New channel: in_person | phone | email | virtual"
    )
    new_date: Optional[str] = Field(
        None, description="New date YYYY-MM-DD"
    )
    new_topics: Optional[List[str]] = Field(
        None, description="Replacement topics discussed list"
    )
    new_materials: Optional[List[str]] = Field(
        None, description="Replacement materials shared list"
    )
    new_sentiment: Optional[str] = Field(
        None, description="New sentiment: positive | neutral | negative"
    )
    new_outcomes: Optional[str] = Field(
        None, description="Updated outcomes summary"
    )
    new_notes: Optional[str] = Field(
        None, description="Additional or replacement notes"
    )


# ── Tool implementation ───────────────────────────────────────────

@tool("edit_interaction", args_schema=EditInteractionInput, return_direct=False)
async def edit_interaction_tool(
    interaction_id: Optional[str] = None,
    hcp_name: Optional[str] = None,
    interaction_date: Optional[str] = None,
    new_interaction_type: Optional[str] = None,
    new_date: Optional[str] = None,
    new_topics: Optional[List[str]] = None,
    new_materials: Optional[List[str]] = None,
    new_sentiment: Optional[str] = None,
    new_outcomes: Optional[str] = None,
    new_notes: Optional[str] = None,
) -> dict:
    """
    EditInteractionTool — modify an existing HCP interaction record.

    Resolution order:
      1. If interaction_id is given → use directly.
      2. Else if hcp_name + interaction_date → find the most recent
         interaction for that HCP on that date.
      3. Else if only hcp_name → find the most recent interaction.

    Returns a dict with:
      success         : bool
      interaction_id  : UUID of the updated record
      updated_fields  : list of field names that were changed
      before          : snapshot of values before the update
      after           : snapshot of values after the update
      error           : str (only on failure)
    """
    import uuid as uuid_module
    from datetime import date as date_type
    from sqlalchemy import select, desc

    from app.database import AsyncSessionLocal
    from app.models.interaction import Interaction, InteractionTypeEnum, SentimentEnum
    from app.services.hcp_service import HCPService
    from app.services.interaction_service import InteractionService
    from app.schemas.interaction import InteractionUpdate

    logger.info(
        "[EditInteractionTool] id=%s hcp=%s date=%s",
        interaction_id, hcp_name, interaction_date,
    )

    async with AsyncSessionLocal() as db:
        svc = InteractionService(db)
        hcp_svc = HCPService(db)

        # ── Resolve the target interaction ────────────────────────
        target: Optional[Interaction] = None

        if interaction_id:
            try:
                iid = uuid_module.UUID(interaction_id)
                target = await svc.get_interaction_by_id(iid)
            except ValueError:
                return {"success": False, "error": f"Invalid UUID: '{interaction_id}'"}

        if not target and hcp_name:
            hcp = await hcp_svc.get_hcp_by_name(hcp_name)
            if not hcp:
                return {"success": False, "error": f"HCP '{hcp_name}' not found."}

            stmt = (
                select(Interaction)
                .where(Interaction.hcp_id == hcp.id)
                .order_by(desc(Interaction.created_at))
            )
            if interaction_date:
                try:
                    d = date_type.fromisoformat(interaction_date)
                    stmt = stmt.where(Interaction.interaction_date == d)
                except ValueError:
                    pass

            result = await db.execute(stmt.limit(1))
            target = result.scalar_one_or_none()

        if not target:
            return {
                "success": False,
                "error": (
                    "Could not locate the interaction. "
                    "Please provide the interaction_id, or the HCP name and date."
                ),
            }

        # ── Snapshot before values ────────────────────────────────
        before = {
            "interaction_type": target.interaction_type.value,
            "interaction_date": target.interaction_date.isoformat(),
            "topics_discussed": target.topics_discussed,
            "materials_shared": target.materials_shared,
            "sentiment": target.sentiment.value if target.sentiment else None,
            "outcomes": target.outcomes,
            "notes": target.notes,
        }

        # ── Build update payload ──────────────────────────────────
        update_kwargs: dict = {}

        if new_interaction_type:
            try:
                update_kwargs["interaction_type"] = InteractionTypeEnum(
                    new_interaction_type.lower()
                )
            except ValueError:
                logger.warning("Unknown interaction_type: %s", new_interaction_type)

        if new_date:
            try:
                update_kwargs["interaction_date"] = date_type.fromisoformat(new_date)
            except ValueError:
                pass

        if new_topics is not None:
            update_kwargs["topics_discussed"] = new_topics

        if new_materials is not None:
            update_kwargs["materials_shared"] = new_materials

        if new_sentiment:
            try:
                update_kwargs["sentiment"] = SentimentEnum(new_sentiment.lower())
            except ValueError:
                pass

        if new_outcomes is not None:
            update_kwargs["outcomes"] = new_outcomes

        if new_notes is not None:
            update_kwargs["notes"] = new_notes

        if not update_kwargs:
            return {
                "success": False,
                "error": "No fields to update were provided.",
            }

        # ── Apply the update ──────────────────────────────────────
        payload = InteractionUpdate(**update_kwargs)
        updated = await svc.edit_interaction(target.id, payload)
        await db.commit()

        # ── Snapshot after values ─────────────────────────────────
        after = {
            "interaction_type": updated.interaction_type.value,
            "interaction_date": updated.interaction_date.isoformat(),
            "topics_discussed": updated.topics_discussed,
            "materials_shared": updated.materials_shared,
            "sentiment": updated.sentiment.value if updated.sentiment else None,
            "outcomes": updated.outcomes,
            "notes": updated.notes,
        }

        updated_fields = [k for k in update_kwargs]

        logger.info(
            "[EditInteractionTool] Updated interaction %s fields=%s",
            target.id, updated_fields,
        )

        return {
            "success": True,
            "interaction_id": str(target.id),
            "hcp_id": str(target.hcp_id),
            "updated_fields": updated_fields,
            "before": before,
            "after": after,
            "message": (
                f"✅ Interaction updated. "
                f"Changed: {', '.join(updated_fields)}."
            ),
        }
