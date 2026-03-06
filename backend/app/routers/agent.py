# ─────────────────────────────────────────────────────────────────
# routers/agent.py – API routes for the LangGraph AI Agent
#
# Routes:
#   POST /ai/chat              – Send a message to the AI agent
#   POST /ai/extract           – Extract structured data (no DB write)
#   GET  /ai/session/{id}      – Get chat session history
# ─────────────────────────────────────────────────────────────────

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import HumanMessage

from app.ai_agent.graph import get_compiled_graph
from app.ai_agent.state import AgentState
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    ExtractRequest,
    ExtractResponse,
)
from app.schemas.interaction import ExtractedInteractionData
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Agent"])

# ── In-memory session store ───────────────────────────────────────
# NOTE: For production use Redis or a DB-backed session store.
# This dict maps session_id → list of {role, content, timestamp} dicts.
_session_store: dict[str, list[dict]] = {}


# ── POST /ai/chat ─────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the AI agent",
    description=(
        "Accepts a natural-language message from the sales rep and runs it "
        "through the LangGraph agent. The agent classifies intent, extracts "
        "structured fields, executes the appropriate tool, and returns a reply."
    ),
)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    Main AI chat endpoint.

    The LangGraph graph is invoked with a fresh state for each request.
    Multi-turn context is maintained via the messages list pulled from
    the in-memory session store.
    """
    # ── Load or create session history ────────────────────────────
    session_history = _session_store.get(payload.session_id, [])

    # Rebuild LangChain message objects from stored session
    history_messages = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else __import__("langchain_core.messages", fromlist=["AIMessage"]).AIMessage(content=m["content"])
        for m in session_history
    ]

    # Append the new user message
    new_user_message = HumanMessage(content=payload.message)
    all_messages = history_messages + [new_user_message]

    # ── Build initial agent state ─────────────────────────────────
    initial_state: AgentState = {
        "messages": all_messages,
        "session_id": payload.session_id,
        "raw_user_input": None,
        "intent": None,
        "intent_confidence": None,
        "entities": None,
        "hcp_context": None,
        "selected_tool": None,
        "tool_input": None,
        "tool_result": None,
        "action_taken": None,
        "confirmation_payload": None,
        "error": None,
        "requires_confirmation": False,
        "retry_count": 0,
    }

    # ── Invoke the LangGraph compiled graph ───────────────────────
    try:
        graph = get_compiled_graph()
        final_state: AgentState = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("LangGraph invocation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(exc)}",
        )

    # ── Extract the last AI reply from state messages ─────────────
    from langchain_core.messages import AIMessage
    reply_text = ""
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage):
            reply_text = msg.content
            break

    # ── Persist updated session history ───────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    session_history.append({"role": "user", "content": payload.message, "timestamp": now})
    session_history.append({"role": "assistant", "content": reply_text, "timestamp": now})
    _session_store[payload.session_id] = session_history

    # ── Parse extracted entities for response ─────────────────────
    # Use new `entities` field (v2 state); fall back to tool_result for log actions
    entities: dict = final_state.get("entities") or {}
    tool_result: dict = final_state.get("tool_result") or {}

    # Build extracted_fields for the frontend auto-fill
    extracted_fields: dict | None = None
    if entities:
        extracted_fields = {
            "hcp_name":           entities.get("hcp_name"),
            "interaction_type":   entities.get("interaction_type"),
            "interaction_date":   entities.get("interaction_date"),
            "interaction_time":   entities.get("interaction_time"),
            "topics_discussed":   entities.get("topics_discussed") or [],
            "materials_shared":   entities.get("materials_shared") or [],
            "sentiment":          entities.get("sentiment"),
            "followup_actions":   entities.get("followup_actions") or [],
            "outcomes":           entities.get("outcomes"),
            "samples_distributed": entities.get("samples_distributed") or [],
        }

    extracted_raw = entities
    extracted_schema: ExtractedInteractionData | None = None
    if extracted_raw:
        try:
            extracted_schema = ExtractedInteractionData(**extracted_raw)
        except Exception:
            pass

    return ChatResponse(
        session_id=payload.session_id,
        reply=reply_text or "I processed your request.",
        intent=final_state.get("intent"),
        extracted_data=extracted_schema,
        extracted_fields=extracted_fields,
        action_taken=final_state.get("action_taken"),
        tool_result=tool_result,
        requires_confirmation=final_state.get("requires_confirmation", False),
    )


# ── POST /ai/extract ──────────────────────────────────────────────

@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Extract structured fields from natural language (no save)",
    description=(
        "Sends text to the LLM for field extraction only. "
        "Nothing is written to the database. Use this for live preview in the UI."
    ),
)
async def extract_fields(payload: ExtractRequest) -> ExtractResponse:
    """
    Run the intent + extraction LLM step only, without saving.
    Returns the extracted structured fields for frontend preview.
    """
    import json
    from datetime import date
    from groq import AsyncGroq
    from app.ai_agent.nodes import INTENT_SYSTEM_PROMPT

    today_str = date.today().isoformat()
    user_content = f"[Today's date: {today_str}]\n\nUser message: {payload.text}"

    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        extracted_data = ExtractedInteractionData(**(parsed.get("extracted_data") or {}))
        confidence = parsed.get("confidence")
        return ExtractResponse(
            extracted_data=extracted_data,
            confidence=confidence,
            raw_llm_output=raw,
        )
    except Exception as exc:
        logger.exception("Extract endpoint error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(exc)}",
        )


# ── GET /ai/session/{session_id} ──────────────────────────────────

@router.get(
    "/session/{session_id}",
    summary="Get chat session history",
    description="Returns the full message history for a given session ID.",
)
async def get_session(session_id: str) -> dict:
    """Retrieve stored conversation messages for a session."""
    messages = _session_store.get(session_id, [])
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
    }
