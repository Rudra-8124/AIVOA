# ─────────────────────────────────────────────────────────────────
# schemas/agent.py – Pydantic v2 schemas for the AI Agent endpoints
#
# ChatRequest / ChatResponse  → POST /ai/chat
# ExtractRequest / ExtractResponse → POST /ai/extract (preview only)
# ─────────────────────────────────────────────────────────────────

from typing import Optional, List, Any
from pydantic import BaseModel, Field

from app.schemas.interaction import ExtractedInteractionData


# ── Chat message history item ─────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


# ── Chat endpoint ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Request body for POST /ai/chat.

    session_id  : Identifies the ongoing conversation so the agent can
                  maintain multi-turn context (stored in agent_sessions).
    message     : The rep's latest natural-language message.
    hcp_id      : Optional – pre-selects an HCP context for the agent.
    """
    session_id: str = Field(..., min_length=1, examples=["session-abc-123"])
    message: str = Field(..., min_length=1, examples=["Met Dr Smith today, discussed Product X"])
    hcp_id: Optional[str] = Field(None, description="UUID of the HCP if already known")


class ChatResponse(BaseModel):
    """
    Response body for POST /ai/chat.

    reply               : The agent's natural-language reply shown in the chat UI.
    intent              : Classified intent (log | edit | query_history | ...).
    extracted_data      : Structured fields pulled from the message (may be partial).
    extracted_fields    : Flat dict of extracted fields for frontend auto-fill.
    action_taken        : Name of the tool the agent executed, if any.
    tool_result         : Raw result returned by the tool (for debug / UI use).
    requires_confirmation : True when the agent wants the rep to confirm before saving.
    """
    session_id: str
    reply: str
    intent: Optional[str] = None
    extracted_data: Optional[ExtractedInteractionData] = None
    extracted_fields: Optional[dict] = None          # flat dict for frontend auto-fill
    action_taken: Optional[str] = None
    tool_result: Optional[Any] = None
    requires_confirmation: bool = False


# ── Extract-only endpoint (no DB write) ───────────────────────────

class ExtractRequest(BaseModel):
    """
    Request body for POST /ai/extract.
    Sends raw text to the LLM for field extraction without saving.
    Useful for the frontend preview panel before the rep confirms.
    """
    text: str = Field(..., min_length=1, examples=["Met Dr Smith today, discussed Product X efficacy"])


class ExtractResponse(BaseModel):
    """Response body for POST /ai/extract."""
    extracted_data: ExtractedInteractionData
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    raw_llm_output: Optional[str] = None
