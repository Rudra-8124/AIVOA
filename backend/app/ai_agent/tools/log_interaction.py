# ─────────────────────────────────────────────────────────────────
# ai_agent/tools/log_interaction.py  –  Tool 1: LogInteractionTool
#
# Full workflow:
#   1. Accept all entities extracted from natural language
#   2. Resolve the HCP by name (fuzzy) in the database
#   3. Validate and coerce all field types
#   4. Persist the interaction to PostgreSQL
#   5. Return a rich structured result for the responder node
# ─────────────────────────────────────────────────────────────────

import logging
from typing import Optional, List
from datetime import date as date_type, time as time_type

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────

class LogInteractionInput(BaseModel):
    """
    All entities that the LLM can extract from a rep's natural-language
    message describing an HCP interaction.

    Example input that maps to these fields:
    "Met Dr Smith today at City Hospital, discussed Product X efficacy and
     dosing, shared brochure + clinical study, distributed 5 samples,
     positive sentiment, agreed to follow up in 2 weeks."
    """
    hcp_name: str = Field(
        ...,
        description="Full or partial name of the HCP, e.g. 'Dr. Smith' or 'Dr Sarah Johnson'",
    )
    interaction_type: str = Field(
        default="in_person",
        description="Channel: in_person | phone | email | virtual",
    )
    interaction_date: str = Field(
        default="",
        description="ISO date YYYY-MM-DD. Empty string → today.",
    )
    interaction_time: Optional[str] = Field(
        None,
        description="Time of interaction HH:MM (24h), optional.",
    )
    topics_discussed: Optional[List[str]] = Field(
        None,
        description="List of topics / products discussed, e.g. ['Product X efficacy', 'dosing schedule']",
    )
    materials_shared: Optional[List[str]] = Field(
        None,
        description="Materials given to the HCP, e.g. ['brochure', 'clinical study reprint']",
    )
    samples_distributed: Optional[List[dict]] = Field(
        None,
        description="Samples given: [{'product_name': 'Product X', 'quantity': 5}]",
    )
    sentiment: Optional[str] = Field(
        None,
        description="Overall tone: positive | neutral | negative",
    )
    outcomes: Optional[str] = Field(
        None,
        description="Summary of what was achieved or agreed, e.g. 'HCP agreed to trial Product X'",
    )
    raw_input: Optional[str] = Field(
        None,
        description="The original natural-language text the rep typed (stored for audit)",
    )


# ── Tool implementation ───────────────────────────────────────────

@tool("log_interaction", args_schema=LogInteractionInput, return_direct=False)
async def log_interaction_tool(
    hcp_name: str,
    interaction_type: str = "in_person",
    interaction_date: str = "",
    interaction_time: Optional[str] = None,
    topics_discussed: Optional[List[str]] = None,
    materials_shared: Optional[List[str]] = None,
    samples_distributed: Optional[List[dict]] = None,
    sentiment: Optional[str] = None,
    outcomes: Optional[str] = None,
    raw_input: Optional[str] = None,
) -> dict:
    """
    LogInteractionTool — persist a new HCP interaction to the database.

    Steps performed:
      1. Resolve HCP by name (case-insensitive partial match).
      2. Parse and validate date/time strings.
      3. Map string enums to InteractionTypeEnum / SentimentEnum.
      4. Create the interaction record via InteractionService.
      5. Return structured confirmation with the new interaction ID.

    Returns a dict with keys:
      success        : bool
      interaction_id : str UUID of the created record
      hcp_id         : str UUID of the resolved HCP
      hcp_name       : str resolved HCP name
      interaction_date: str ISO date stored
      topics_count   : int number of topics stored
      error          : str (only present on failure)
    """
    from app.database import AsyncSessionLocal
    from app.services.hcp_service import HCPService
    from app.services.interaction_service import InteractionService
    from app.schemas.interaction import InteractionCreate
    from app.models.interaction import InteractionTypeEnum, SentimentEnum

    logger.info("[LogInteractionTool] hcp_name=%s date=%s", hcp_name, interaction_date)

    async with AsyncSessionLocal() as db:
        hcp_svc = HCPService(db)
        int_svc = InteractionService(db)

        # ── Step 1: Resolve HCP (auto-create if not found) ───────
        hcp = await hcp_svc.get_hcp_by_name(hcp_name)
        hcp_auto_created = False
        if not hcp:
            logger.info("[LogInteractionTool] HCP '%s' not found — auto-creating", hcp_name)
            from app.schemas.hcp import HCPCreate
            hcp = await hcp_svc.create_hcp(HCPCreate(name=hcp_name))
            hcp_auto_created = True
            logger.info("[LogInteractionTool] Auto-created HCP id=%s name=%s", hcp.id, hcp.name)

        # ── Step 2: Parse date ────────────────────────────────────
        try:
            parsed_date = (
                date_type.fromisoformat(interaction_date)
                if interaction_date
                else date_type.today()
            )
        except ValueError:
            logger.warning("[LogInteractionTool] Bad date '%s', using today", interaction_date)
            parsed_date = date_type.today()

        # ── Step 3: Parse optional time ───────────────────────────
        parsed_time: Optional[time_type] = None
        if interaction_time:
            try:
                parts = interaction_time.strip().split(":")
                parsed_time = time_type(int(parts[0]), int(parts[1]))
            except Exception:
                logger.debug("[LogInteractionTool] Could not parse time: %s", interaction_time)

        # ── Step 4: Map string → enum ─────────────────────────────
        try:
            itype = InteractionTypeEnum(interaction_type.lower())
        except ValueError:
            itype = InteractionTypeEnum.in_person

        sent: Optional[SentimentEnum] = None
        if sentiment:
            try:
                sent = SentimentEnum(sentiment.lower())
            except ValueError:
                pass

        # ── Step 5: Persist ───────────────────────────────────────
        payload = InteractionCreate(
            hcp_id=hcp.id,
            interaction_type=itype,
            interaction_date=parsed_date,
            interaction_time=parsed_time,
            topics_discussed=topics_discussed or [],
            materials_shared=materials_shared or [],
            samples_distributed=samples_distributed,
            sentiment=sent,
            outcomes=outcomes,
            raw_input=raw_input,
            extracted_by_ai=True,
        )

        interaction = await int_svc.log_interaction(payload)
        await db.commit()
        await db.refresh(interaction)

        logger.info(
            "[LogInteractionTool] Created interaction %s for HCP %s",
            interaction.id, hcp.id,
        )

        return {
            "success": True,
            "interaction_id": str(interaction.id),
            "hcp_id": str(hcp.id),
            "hcp_name": hcp.name,
            "hcp_specialty": hcp.specialty,
            "hcp_auto_created": hcp_auto_created,
            "interaction_type": itype.value,
            "interaction_date": parsed_date.isoformat(),
            "interaction_time": parsed_time.strftime("%H:%M") if parsed_time else None,
            "topics_count": len(topics_discussed) if topics_discussed else 0,
            "topics_discussed": topics_discussed or [],
            "materials_shared": materials_shared or [],
            "sentiment": sent.value if sent else None,
            "outcomes": outcomes,
            "extracted_by_ai": True,
            "message": (
                f"✅ Interaction logged: {hcp.name} on {parsed_date.strftime('%B %d, %Y')} "
                f"({itype.value.replace('_', ' ')}). "
                f"{len(topics_discussed or [])} topic(s) recorded."
                + (" 🆕 HCP profile auto-created." if hcp_auto_created else "")
            ),
        }
