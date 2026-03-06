# ─────────────────────────────────────────────────────────────────
# ai_agent/tools/suggest_followup.py  –  Tool 4: SuggestFollowUpTool
#
# Full workflow:
#   1. Load the interaction context (topics, sentiment, outcomes)
#   2. Build a rich LLM prompt grounded in the real interaction data
#   3. Parse the LLM's structured JSON output into ranked suggestions
#   4. Persist all suggestions as FollowupAction records in DB
#   5. Return ranked, prioritised follow-up actions with due-date hints
# ─────────────────────────────────────────────────────────────────

import json
import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────

class SuggestFollowUpInput(BaseModel):
    """
    The agent uses this tool when the rep says:
      "What should I do next with Dr Smith?"
      "Suggest follow-ups for my last visit"
      "Generate action items for interaction <UUID>"
    """
    interaction_id: str = Field(
        ...,
        description=(
            "UUID of the interaction to generate follow-up actions for. "
            "If the rep just logged an interaction, use the returned interaction_id."
        ),
    )


# ── Follow-up suggestion prompt ───────────────────────────────────

FOLLOWUP_SYSTEM_PROMPT = """You are an expert pharmaceutical sales CRM assistant.
A sales representative has just logged an interaction with a Healthcare Professional (HCP).
Your job is to generate specific, actionable, prioritised follow-up actions.

Rules:
- Generate between 2 and 5 follow-up actions.
- Each action must be concrete (not vague like "follow up soon").
- Include a suggested timeframe in days (e.g. 7, 14, 30).
- Prioritise: HIGH (urgent / time-sensitive), MEDIUM, LOW.
- Base suggestions on the actual topics discussed, sentiment, and outcomes.
- If sentiment is NEGATIVE → include a recovery action as HIGH priority.
- If samples were distributed → include a feedback/prescription follow-up.
- If materials were shared → include a review/feedback action.

Respond ONLY with a valid JSON array:
[
  {
    "action": "Short, imperative action description",
    "priority": "HIGH | MEDIUM | LOW",
    "due_in_days": <integer>,
    "rationale": "One sentence explaining why this action is recommended"
  }
]"""


# ── Tool implementation ───────────────────────────────────────────

@tool("suggest_followup", args_schema=SuggestFollowUpInput, return_direct=False)
async def suggest_followup_tool(interaction_id: str) -> dict:
    """
    SuggestFollowUpTool — generate AI-powered, prioritised follow-up actions.

    Uses the Groq LLM (llama-3.1-8b-instant) to reason over the interaction context
    and produce ranked, time-bound action items. All suggestions are
    persisted to the followup_actions table.

    Returns:
      success        : bool
      interaction_id : UUID string
      hcp_name       : name of the HCP
      followup_count : number of actions generated
      suggestions    : list of {action, priority, due_in_days, rationale, id}
      error          : str (only on failure)
    """
    import uuid as uuid_module
    from groq import AsyncGroq
    from datetime import date as date_type, timedelta

    from app.database import AsyncSessionLocal
    from app.services.interaction_service import InteractionService
    from app.services.hcp_service import HCPService
    from app.config import settings

    try:
        iid = uuid_module.UUID(interaction_id)
    except ValueError:
        return {"success": False, "error": f"Invalid interaction_id: '{interaction_id}'"}

    logger.info("[SuggestFollowUpTool] interaction_id=%s", interaction_id)

    async with AsyncSessionLocal() as db:
        svc = InteractionService(db)
        hcp_svc = HCPService(db)

        # ── Load interaction ──────────────────────────────────────
        interaction = await svc.get_interaction_by_id(iid)
        if not interaction:
            return {
                "success": False,
                "error": f"Interaction '{interaction_id}' not found.",
            }

        # ── Load HCP for context ──────────────────────────────────
        hcp = await hcp_svc.get_hcp_by_id(interaction.hcp_id)
        hcp_name = hcp.name if hcp else "Unknown HCP"
        hcp_specialty = hcp.specialty if hcp else "Unknown"

        # ── Build interaction context for the LLM ─────────────────
        context = {
            "hcp_name": hcp_name,
            "hcp_specialty": hcp_specialty,
            "interaction_date": interaction.interaction_date.isoformat(),
            "interaction_type": interaction.interaction_type.value,
            "topics_discussed": interaction.topics_discussed or [],
            "materials_shared": interaction.materials_shared or [],
            "samples_distributed": interaction.samples_distributed or [],
            "sentiment": interaction.sentiment.value if interaction.sentiment else "unknown",
            "outcomes": interaction.outcomes or "No outcomes recorded",
            "notes": interaction.notes or "",
        }

        user_prompt = f"""Generate follow-up actions for this HCP interaction:

{json.dumps(context, indent=2)}

Return a JSON array of follow-up actions as specified."""

        # ── Call Groq LLM ─────────────────────────────────────────
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=768,
        )

        raw = response.choices[0].message.content.strip()
        logger.debug("[SuggestFollowUpTool] LLM raw output: %s", raw[:200])

        # ── Robust JSON extraction ────────────────────────────────
        suggestions: list[dict] = []
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            suggestions = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("[SuggestFollowUpTool] JSON parse failed: %s", exc)
            # Graceful fallback: create generic actions
            suggestions = [
                {
                    "action": f"Follow up with {hcp_name} regarding discussed topics",
                    "priority": "MEDIUM",
                    "due_in_days": 14,
                    "rationale": "Standard post-interaction follow-up",
                }
            ]

        # ── Persist follow-up actions to DB ───────────────────────
        action_descriptions = [s.get("action", "") for s in suggestions if s.get("action")]
        followups = await svc.create_followup_actions(
            interaction_id=iid,
            hcp_id=interaction.hcp_id,
            action_descriptions=action_descriptions,
            suggested_by_ai=True,
        )
        await db.commit()

        # ── Enrich suggestions with DB IDs and computed due dates ─
        today = date_type.today()
        enriched = []
        for i, suggestion in enumerate(suggestions):
            due_days = suggestion.get("due_in_days", 14)
            due_date = (today + timedelta(days=due_days)).isoformat()
            enriched.append({
                "id": str(followups[i].id) if i < len(followups) else None,
                "action": suggestion.get("action", ""),
                "priority": suggestion.get("priority", "MEDIUM"),
                "due_in_days": due_days,
                "due_date": due_date,
                "rationale": suggestion.get("rationale", ""),
            })

        # Sort by priority: HIGH → MEDIUM → LOW
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        enriched.sort(key=lambda x: priority_order.get(x["priority"], 1))

    logger.info(
        "[SuggestFollowUpTool] Generated %d follow-ups for interaction %s",
        len(enriched), interaction_id,
    )

    return {
        "success": True,
        "interaction_id": interaction_id,
        "hcp_name": hcp_name,
        "followup_count": len(enriched),
        "suggestions": enriched,
        "message": (
            f"✅ Generated {len(enriched)} follow-up action(s) for {hcp_name}. "
            f"Highest priority: {enriched[0]['action'] if enriched else 'None'}."
        ),
    }
