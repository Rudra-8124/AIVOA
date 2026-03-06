# ─────────────────────────────────────────────────────────────────
# ai_agent/tools/product_recommendation.py  –  Tool 5: ProductRecommendationTool
#
# Full workflow:
#   1. Resolve the HCP and their full interaction history
#   2. Extract all topics discussed across past visits
#   3. Load the full product catalogue from DB
#   4. Use Groq LLM to reason over specialty + topics → ranked products
#   5. Return products with talking points + match rationale
# ─────────────────────────────────────────────────────────────────

import json
import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────

class ProductRecommendationInput(BaseModel):
    """
    The agent uses this when the rep asks:
      "What product should I pitch to Dr Smith next time?"
      "Which products suit a cardiologist who asked about cholesterol?"
      "Recommend products for Dr Johnson based on our discussions"
    """
    hcp_name: str = Field(
        ...,
        description="Name of the HCP to generate product recommendations for",
    )
    additional_context: Optional[str] = Field(
        None,
        description=(
            "Any extra context from the current conversation, e.g. "
            "'the HCP mentioned interest in once-daily dosing'"
        ),
    )


# ── Recommendation prompt ─────────────────────────────────────────

RECOMMENDATION_SYSTEM_PROMPT = """You are a senior pharmaceutical sales strategist AI.
Your job is to recommend the most relevant products to pitch to a Healthcare Professional (HCP)
based on their specialty, past interaction topics, and available product portfolio.

Rules:
- Recommend between 1 and 3 products maximum.
- Rank them from BEST FIT to ACCEPTABLE FIT.
- For each product, provide 2-3 specific talking points tailored to this HCP.
- Explain in one sentence WHY this product fits this specific HCP.
- Consider contraindications — do NOT recommend a product for a specialty where it's irrelevant.
- If additional context is provided, factor it into the ranking.

Respond ONLY with a valid JSON array:
[
  {
    "rank": 1,
    "product_name": "exact product name from catalogue",
    "fit_score": <float 0.0-1.0>,
    "match_reason": "One sentence: why this product fits this HCP",
    "talking_points": [
      "Specific, evidence-based talking point 1",
      "Specific talking point 2"
    ],
    "key_message": "The single most important message for this HCP"
  }
]"""


# ── Tool implementation ───────────────────────────────────────────

@tool("product_recommendation", args_schema=ProductRecommendationInput, return_direct=False)
async def product_recommendation_tool(
    hcp_name: str,
    additional_context: Optional[str] = None,
) -> dict:
    """
    ProductRecommendationTool — recommend pharmaceutical products for an HCP.

    Combines:
      - HCP's medical specialty and hospital context
      - Aggregated topics from all past interactions
      - Full product catalogue (name, category, indication, key messages)
      - LLM reasoning via Groq (llama-3.1-8b-instant)

    Returns:
      success              : bool
      hcp_name             : resolved HCP name
      hcp_specialty        : HCP specialty
      products_considered  : int — total products in catalogue evaluated
      past_topics          : list of aggregated discussion topics
      recommendations      : ranked list of products with talking points
      error                : str (only on failure)
    """
    from sqlalchemy import select
    from groq import AsyncGroq

    from app.database import AsyncSessionLocal
    from app.services.hcp_service import HCPService
    from app.services.interaction_service import InteractionService
    from app.models.product import Product
    from app.config import settings

    logger.info("[ProductRecommendationTool] hcp=%s", hcp_name)

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
                    "Please check the spelling or register this HCP first."
                ),
            }

        # ── Load full product catalogue ───────────────────────────
        result = await db.execute(select(Product).order_by(Product.name))
        products = result.scalars().all()

        if not products:
            return {
                "success": False,
                "error": "No products found in the catalogue. Please seed the products table.",
            }

        product_catalogue = [
            {
                "name": p.name,
                "category": p.category or "General",
                "indication": p.indication or "Not specified",
                "key_messages": p.key_messages or [],
            }
            for p in products
        ]

        # ── Aggregate past discussion topics for this HCP ─────────
        past_topics = await int_svc.get_topics_for_hcp(hcp.id)

        # ── Also fetch recent interaction summary for richer context
        _, recent_interactions = await int_svc.get_hcp_interactions(
            hcp_id=hcp.id, page=1, page_size=5
        )
        recent_outcomes = [
            i.outcomes for i in recent_interactions if i.outcomes
        ]

    # ── Build LLM prompt ─────────────────────────────────────────
    hcp_profile = {
        "name": hcp.name,
        "specialty": hcp.specialty or "General Practice",
        "hospital": hcp.hospital or "Not specified",
        "territory": hcp.territory or "Not specified",
    }

    user_prompt = f"""HCP Profile:
{json.dumps(hcp_profile, indent=2)}

Topics discussed in past interactions (aggregated):
{json.dumps(past_topics if past_topics else ["No prior interactions recorded"], indent=2)}

Recent outcomes from past visits:
{json.dumps(recent_outcomes if recent_outcomes else ["No outcomes recorded"], indent=2)}

Additional context from current conversation:
{additional_context or "None provided"}

Available product catalogue:
{json.dumps(product_catalogue, indent=2)}

Recommend the best products for the next visit with this HCP."""

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    logger.debug("[ProductRecommendationTool] LLM raw output: %s", raw[:300])

    # ── Robust JSON extraction ────────────────────────────────────
    recommendations: list[dict] = []
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        recommendations = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("[ProductRecommendationTool] JSON parse failed: %s", exc)
        # Fallback: return first product from catalogue
        if product_catalogue:
            recommendations = [{
                "rank": 1,
                "product_name": product_catalogue[0]["name"],
                "fit_score": 0.5,
                "match_reason": "Default recommendation — unable to parse LLM output.",
                "talking_points": product_catalogue[0].get("key_messages", [])[:2],
                "key_message": product_catalogue[0].get("indication", ""),
            }]

    logger.info(
        "[ProductRecommendationTool] %d recommendations for %s",
        len(recommendations), hcp.name,
    )

    return {
        "success": True,
        "hcp_name": hcp.name,
        "hcp_specialty": hcp.specialty,
        "hcp_hospital": hcp.hospital,
        "products_considered": len(product_catalogue),
        "past_topics": past_topics,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "message": (
            f"✅ {len(recommendations)} product recommendation(s) for {hcp.name} "
            f"({hcp.specialty or 'General'}). "
            f"Top pick: {recommendations[0]['product_name'] if recommendations else 'N/A'}."
        ),
    }
