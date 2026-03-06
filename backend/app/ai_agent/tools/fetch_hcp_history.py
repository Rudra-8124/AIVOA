# ─────────────────────────────────────────────────────────────────
# ai_agent/tools/fetch_hcp_history.py  –  Tool 3: FetchHCPHistoryTool
#
# Full workflow:
#   1. Resolve the HCP by name from DB
#   2. Query interactions with optional date range + sentiment filter
#   3. Compute aggregate stats (total, by type, by sentiment, last seen)
#   4. Return a rich summary that the responder node can narrate
# ─────────────────────────────────────────────────────────────────

import logging
from typing import Optional
from collections import Counter

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────

class FetchHCPHistoryInput(BaseModel):
    """
    Query past interactions for a specific HCP.
    The agent uses this when a rep asks:
      "What did I discuss with Dr Smith?"
      "Show me my last 3 visits with Dr Johnson"
      "Any negative interactions with Dr Lee this month?"
    """
    hcp_name: str = Field(
        ...,
        description="Full or partial name of the HCP to look up",
    )
    from_date: Optional[str] = Field(
        None,
        description="Start of date range YYYY-MM-DD (inclusive)",
    )
    to_date: Optional[str] = Field(
        None,
        description="End of date range YYYY-MM-DD (inclusive)",
    )
    sentiment_filter: Optional[str] = Field(
        None,
        description="Filter by sentiment: positive | neutral | negative",
    )
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=5, ge=1, le=20, description="Records per page")


# ── Tool implementation ───────────────────────────────────────────

@tool("fetch_hcp_history", args_schema=FetchHCPHistoryInput, return_direct=False)
async def fetch_hcp_history_tool(
    hcp_name: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sentiment_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 5,
) -> dict:
    """
    FetchHCPHistoryTool — retrieve and summarise past HCP interactions.

    Returns:
      success           : bool
      hcp_id            : UUID string
      hcp_name          : resolved HCP name
      hcp_specialty     : HCP's medical specialty
      hcp_hospital      : HCP's hospital affiliation
      total_interactions: total matching records
      stats             : aggregate counts by type and sentiment
      last_interaction  : most recent interaction summary dict
      interactions      : list of interaction summaries (current page)
      has_more          : bool — more pages available
      error             : str (only on failure)
    """
    from datetime import date as date_type
    from app.database import AsyncSessionLocal
    from app.services.hcp_service import HCPService
    from app.services.interaction_service import InteractionService
    from app.models.interaction import SentimentEnum

    logger.info("[FetchHCPHistoryTool] hcp=%s from=%s to=%s", hcp_name, from_date, to_date)

    async with AsyncSessionLocal() as db:
        hcp_svc = HCPService(db)
        int_svc = InteractionService(db)

        # ── Resolve HCP ───────────────────────────────────────────
        hcp = await hcp_svc.get_hcp_by_name(hcp_name)
        if not hcp:
            return {
                "success": False,
                "error": (
                    f"HCP '{hcp_name}' not found. "
                    "Check the spelling or search in the HCP directory."
                ),
            }

        # ── Parse date filters ────────────────────────────────────
        fd: Optional[date_type] = None
        td: Optional[date_type] = None
        try:
            if from_date:
                fd = date_type.fromisoformat(from_date)
        except ValueError:
            pass
        try:
            if to_date:
                td = date_type.fromisoformat(to_date)
        except ValueError:
            pass

        # ── Parse sentiment filter ────────────────────────────────
        sentiment: Optional[SentimentEnum] = None
        if sentiment_filter:
            try:
                sentiment = SentimentEnum(sentiment_filter.lower())
            except ValueError:
                pass

        # ── Query DB ──────────────────────────────────────────────
        total, interactions = await int_svc.get_hcp_interactions(
            hcp_id=hcp.id,
            page=page,
            page_size=page_size,
            from_date=fd,
            to_date=td,
            sentiment=sentiment,
        )

        # ── Compute aggregate stats across the current page ───────
        # (for full stats, query without pagination — done separately)
        _, all_interactions = await int_svc.get_hcp_interactions(
            hcp_id=hcp.id,
            page=1,
            page_size=500,        # reasonable cap for stats
            from_date=fd,
            to_date=td,
        )

        type_counts = Counter(i.interaction_type.value for i in all_interactions)
        sentiment_counts = Counter(
            i.sentiment.value for i in all_interactions if i.sentiment
        )

        all_topics: list[str] = []
        for i in all_interactions:
            all_topics.extend(i.topics_discussed or [])
        top_topics = [t for t, _ in Counter(all_topics).most_common(5)]

        # ── Serialise the page of interactions ───────────────────
        records = []
        for inter in interactions:
            records.append({
                "id": str(inter.id),
                "date": inter.interaction_date.isoformat(),
                "time": inter.interaction_time.strftime("%H:%M") if inter.interaction_time else None,
                "type": inter.interaction_type.value,
                "topics": inter.topics_discussed or [],
                "materials": inter.materials_shared or [],
                "sentiment": inter.sentiment.value if inter.sentiment else None,
                "outcomes": inter.outcomes,
                "notes": inter.notes,
                "extracted_by_ai": inter.extracted_by_ai,
                "created_at": inter.created_at.isoformat(),
            })

        last_interaction = records[0] if records else None

    logger.info(
        "[FetchHCPHistoryTool] Found %d interactions for %s",
        total, hcp.name,
    )

    return {
        "success": True,
        "hcp_id": str(hcp.id),
        "hcp_name": hcp.name,
        "hcp_specialty": hcp.specialty,
        "hcp_hospital": hcp.hospital,
        "hcp_territory": hcp.territory,
        "total_interactions": total,
        "stats": {
            "by_type": dict(type_counts),
            "by_sentiment": dict(sentiment_counts),
            "top_topics": top_topics,
        },
        "last_interaction": last_interaction,
        "interactions": records,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
        "filters_applied": {
            "from_date": from_date,
            "to_date": to_date,
            "sentiment": sentiment_filter,
        },
    }
