# ─────────────────────────────────────────────────────────────────
# ai_agent/nodes.py – LangGraph node functions
#
# 6-node pipeline:
#
#   1. input_node            – Extract raw user input, reset state
#   2. intent_node           – LLM: classify intent (6 classes)
#   3. entity_extraction_node – LLM: extract all structured entities
#   4. tool_selector_node    – Pure logic: pick tool from intent
#   5. tool_executor_node    – Run the chosen tool, store result
#   6. responder_node        – LLM: format natural-language reply
#
# Why 6 nodes instead of 4?
#   Separating intent classification from entity extraction gives
#   better accuracy — the LLM does one focused task per call.
#   The tool_executor is a dispatcher that routes to the correct
#   tool function without the graph needing one node per tool.
# ─────────────────────────────────────────────────────────────────

import json
import logging
from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, AIMessage

from app.ai_agent.state import AgentState
from app.ai_agent.groq_client import (
    extract_interaction_fields,
    chat_completion,
    get_client as get_groq_client,
)
from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for a pharmaceutical CRM system.
Classify the user message into EXACTLY ONE of these intents:

  log                   – rep is DESCRIBING / REPORTING an interaction that happened
                          (met, called, visited, spoke with, discussed — past tense narration)
                          Examples: "Met Dr Smith today", "Called Dr Patel about side effects",
                          "Visited City Hospital, discussed Cardivex", "Dr Jones was concerned"
  edit                  – rep wants to correct / update a previously logged interaction
  query_history         – rep wants to see past interactions with an HCP
  suggest_followup      – rep EXPLICITLY asks for next steps / follow-up actions / what to do next
                          (must contain explicit request words: "suggest", "what should I do",
                          "follow-up", "action items", "next steps", "recommend actions")
  product_recommendation – rep EXPLICITLY asks what product to recommend for an HCP
  chitchat              – greeting, out-of-scope, or unclear

CRITICAL RULE: If the message describes something that happened (a call, visit, meeting, discussion)
— even if the outcome was negative or the HCP had concerns — classify it as "log", NOT "suggest_followup".
Only use "suggest_followup" when the rep explicitly asks WHAT TO DO NEXT.

Reply ONLY with valid JSON — no prose, no markdown:
{
  "intent": "<one of the 6 values above>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one sentence explaining the classification>"
}"""

RESPONDER_SYSTEM_PROMPT = """\
You are a friendly, professional AI assistant for a pharmaceutical sales CRM.
Your role: convert structured tool results into a clear, concise reply for the sales rep.

Guidelines:
- Be professional but warm (the user is a busy sales rep).
- Use bullet points for lists (follow-ups, recommendations, history).
- Confirm actions taken with key details (who, what, when).
- If an error occurred, explain it clearly and suggest next steps.
- Never expose raw JSON, UUIDs, or internal field names directly.
- Keep replies under 150 words unless the data requires more.
- Use ✅ for success, ⚠️ for warnings, ❌ for errors."""


# ─────────────────────────────────────────────────────────────────
# Node 1 — Input Node
# ─────────────────────────────────────────────────────────────────

async def input_node(state: AgentState) -> dict:
    """
    Extracts the latest raw user message from the message history
    and resets all processing fields for a clean pipeline run.
    """
    raw_input = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            raw_input = msg.content
            break

    logger.info("[input_node] raw_input=%r", raw_input[:80])

    return {
        "raw_user_input": raw_input,
        "intent": None,
        "intent_confidence": None,
        "entities": None,
        "hcp_context": None,
        "selected_tool": None,
        "tool_input": None,
        "tool_result": None,
        "action_taken": None,
        "confirmation_payload": None,
        "requires_confirmation": False,
        "error": None,
    }


# ─────────────────────────────────────────────────────────────────
# Node 2 — Intent Classification Node
# ─────────────────────────────────────────────────────────────────

async def intent_node(state: AgentState) -> dict:
    """
    Single-purpose LLM call: classify the intent of the user message.
    Uses a focused, low-temperature call for deterministic classification.
    On failure, defaults to 'chitchat' so the pipeline always continues.
    """
    raw_input = state.get("raw_user_input", "")

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": raw_input}],
            system=INTENT_SYSTEM_PROMPT,
            temperature=0.05,   # near-deterministic for classification
            max_tokens=128,
            json_mode=True,
        )

        parsed = json.loads(raw)
        intent = parsed.get("intent", "chitchat")
        confidence = float(parsed.get("confidence", 0.5))

        logger.info("[intent_node] intent=%s confidence=%.2f", intent, confidence)
        return {"intent": intent, "intent_confidence": confidence}

    except Exception as exc:
        logger.exception("[intent_node] error: %s", exc)
        return {
            "intent": "chitchat",
            "intent_confidence": 0.0,
            "error": f"Intent classification failed: {exc}",
        }


# ─────────────────────────────────────────────────────────────────
# Node 3 — Entity Extraction Node
# ─────────────────────────────────────────────────────────────────

async def entity_extraction_node(state: AgentState) -> dict:
    """
    Dedicated LLM call: extract all structured entities from the
    user message. Only runs for non-chitchat intents.

    Delegates to groq_client.extract_interaction_fields() which
    uses a prompt-engineered extraction prompt with today's date
    injected for relative-date resolution (e.g. "yesterday").
    """
    if state.get("intent") == "chitchat":
        return {"entities": {}}

    raw_input = state.get("raw_user_input", "")
    today_str = date.today().isoformat()

    try:
        entities = await extract_interaction_fields(raw_input, today=today_str)
        logger.info(
            "[entity_extraction_node] hcp=%s type=%s date=%s sentiment=%s topics=%s",
            entities.get("hcp_name"),
            entities.get("interaction_type"),
            entities.get("interaction_date"),
            entities.get("sentiment"),
            entities.get("topics_discussed"),
        )
        return {"entities": entities}

    except Exception as exc:
        logger.exception("[entity_extraction_node] error: %s", exc)
        return {
            "entities": {},
            "error": f"Entity extraction failed: {exc}",
        }


# ─────────────────────────────────────────────────────────────────
# Node 4 — Tool Selector Node (pure logic, no LLM)
# ─────────────────────────────────────────────────────────────────

INTENT_TO_TOOL: dict[str, str] = {
    "log":                    "log_interaction",
    "edit":                   "edit_interaction",
    "query_history":          "fetch_hcp_history",
    "suggest_followup":       "suggest_followup",
    "product_recommendation": "product_recommendation",
    "chitchat":               "none",
}


def tool_selector_node(state: AgentState) -> dict:
    """
    Maps intent → selected_tool and assembles tool_input from entities.
    Pure Python — no LLM call — so this node is fast and deterministic.
    """
    intent = state.get("intent", "chitchat")
    entities = state.get("entities") or {}
    selected_tool = INTENT_TO_TOOL.get(intent, "none")

    # ── Build tool_input specific to each tool ────────────────────
    tool_input: dict = {}

    if selected_tool == "log_interaction":
        tool_input = {
            "hcp_name":             entities.get("hcp_name", ""),
            "interaction_type":     entities.get("interaction_type", "in_person"),
            "interaction_date":     entities.get("interaction_date", ""),
            "interaction_time":     entities.get("interaction_time"),
            "topics_discussed":     entities.get("topics_discussed") or [],
            "materials_shared":     entities.get("materials_shared") or [],
            "samples_distributed":  entities.get("samples_distributed") or [],
            "sentiment":            entities.get("sentiment"),
            "outcomes":             entities.get("outcomes"),
            "raw_input":            state.get("raw_user_input"),
        }

    elif selected_tool == "edit_interaction":
        tool_input = {
            "interaction_id":       entities.get("interaction_id"),
            "hcp_name":             entities.get("hcp_name"),
            "interaction_date":     entities.get("interaction_date"),
            "new_interaction_type": entities.get("interaction_type"),
            "new_date":             entities.get("interaction_date"),
            "new_topics":           entities.get("topics_discussed"),
            "new_materials":        entities.get("materials_shared"),
            "new_sentiment":        entities.get("sentiment"),
            "new_outcomes":         entities.get("outcomes"),
        }

    elif selected_tool == "fetch_hcp_history":
        # entity_extraction is tuned for logging prompts — for query_history
        # the hcp_name is almost always in the raw input even if extraction
        # missed it. Fall back to extracting it from the raw text via LLM
        # would add latency, so instead we parse it heuristically:
        #   "show me ... with Dr. X"  →  capture "Dr. X ..."
        hcp_name_resolved = entities.get("hcp_name") or ""
        if not hcp_name_resolved:
            import re
            raw = state.get("raw_user_input", "")
            # Match "Dr./Prof./Mr./Ms. Firstname Lastname"
            m = re.search(
                r"\b(Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                raw,
            )
            if m:
                hcp_name_resolved = m.group(0).strip()
            else:
                # Last resort — anything after "with" or "for" + capital word
                m2 = re.search(r"\b(?:with|for|about)\s+([A-Z][a-zA-Z\s]{2,30})", raw)
                if m2:
                    hcp_name_resolved = m2.group(1).strip()

        tool_input = {
            "hcp_name":         hcp_name_resolved,
            "from_date":        entities.get("from_date"),
            "to_date":          entities.get("to_date"),
            "sentiment_filter": entities.get("sentiment"),
            "page":             1,
            "page_size":        5,
        }

        # If we still have no name, short-circuit now with a clear error
        # rather than letting Pydantic throw a validation error downstream
        if not tool_input["hcp_name"]:
            return {
                "selected_tool": "none",
                "tool_input": {},
                "tool_result": {
                    "success": False,
                    "error": (
                        "I couldn't identify the HCP name in your message. "
                        "Please include the doctor's name, e.g. "
                        "'Show me history for Dr. Priya Sharma'."
                    ),
                },
            }

    elif selected_tool == "suggest_followup":
        # interaction_id may come from a prior log in this session
        prior_result = state.get("tool_result") or {}
        interaction_id = (
            entities.get("interaction_id")
            or prior_result.get("interaction_id", "")
        )
        if not interaction_id:
            # No interaction_id available — the rep is describing an interaction,
            # not explicitly asking for follow-ups. Treat as a log intent.
            logger.info(
                "[tool_selector_node] suggest_followup has no interaction_id — "
                "falling back to log_interaction"
            )
            selected_tool = "log_interaction"
            tool_input = {
                "hcp_name":             entities.get("hcp_name", ""),
                "interaction_type":     entities.get("interaction_type", "in_person"),
                "interaction_date":     entities.get("interaction_date", ""),
                "interaction_time":     entities.get("interaction_time"),
                "topics_discussed":     entities.get("topics_discussed") or [],
                "materials_shared":     entities.get("materials_shared") or [],
                "samples_distributed":  entities.get("samples_distributed") or [],
                "sentiment":            entities.get("sentiment"),
                "outcomes":             entities.get("outcomes"),
                "raw_input":            state.get("raw_user_input"),
            }
        else:
            tool_input = {"interaction_id": interaction_id}

    elif selected_tool == "product_recommendation":
        tool_input = {
            "hcp_name":           entities.get("hcp_name", ""),
            "additional_context": state.get("raw_user_input"),
        }

    logger.info(
        "[tool_selector_node] intent=%s → tool=%s", intent, selected_tool
    )

    return {"selected_tool": selected_tool, "tool_input": tool_input}


# ─────────────────────────────────────────────────────────────────
# Node 5 — Tool Executor Node
# ─────────────────────────────────────────────────────────────────

async def tool_executor_node(state: AgentState) -> dict:
    """
    Dispatcher: invokes the selected tool with tool_input.
    Stores the result in tool_result and records action_taken.

    All tool calls are wrapped in a try/except so a tool failure
    doesn't crash the entire pipeline — the responder will explain
    the error gracefully.
    """
    selected_tool = state.get("selected_tool", "none")
    tool_input = state.get("tool_input") or {}

    if selected_tool == "none":
        # tool_selector may have already set a short-circuit tool_result (e.g. missing HCP name)
        pre_set_result = state.get("tool_result")
        return {"tool_result": pre_set_result, "action_taken": None}

    # ── Import and invoke the appropriate tool ─────────────────────
    try:
        if selected_tool == "log_interaction":
            from app.ai_agent.tools.log_interaction import log_interaction_tool as fn
        elif selected_tool == "edit_interaction":
            from app.ai_agent.tools.edit_interaction import edit_interaction_tool as fn
        elif selected_tool == "fetch_hcp_history":
            from app.ai_agent.tools.fetch_hcp_history import fetch_hcp_history_tool as fn
        elif selected_tool == "suggest_followup":
            from app.ai_agent.tools.suggest_followup import suggest_followup_tool as fn
        elif selected_tool == "product_recommendation":
            from app.ai_agent.tools.product_recommendation import product_recommendation_tool as fn
        else:
            return {"tool_result": None, "action_taken": None}

        logger.info("[tool_executor_node] invoking tool=%s input_keys=%s",
                    selected_tool, list(tool_input.keys()))

        result = await fn.ainvoke(tool_input)

        logger.info(
            "[tool_executor_node] tool=%s success=%s",
            selected_tool, result.get("success", "?"),
        )

        return {"tool_result": result, "action_taken": selected_tool}

    except Exception as exc:
        logger.exception("[tool_executor_node] tool=%s FAILED: %s", selected_tool, exc)
        return {
            "tool_result": {"success": False, "error": str(exc)},
            "action_taken": selected_tool,
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────
# Node 6 — Responder Node
# ─────────────────────────────────────────────────────────────────

async def responder_node(state: AgentState) -> dict:
    """
    Final node: converts the tool_result + state into a natural-language
    reply using a second Groq LLM call with a formatting-focused prompt.

    The responder never sees raw DB records — it sees the structured
    tool_result dict, which it narrates in plain English.
    """
    raw_user_input = state.get("raw_user_input", "")
    intent = state.get("intent", "chitchat")
    action_taken = state.get("action_taken")
    tool_result = state.get("tool_result") or {}
    error = state.get("error")
    entities = state.get("entities") or {}

    # ── Build a concise context summary for the LLM ───────────────
    context = {
        "user_message": raw_user_input,
        "classified_intent": intent,
        "tool_executed": action_taken,
        "tool_result": tool_result,
        "error": error,
        "hcp_name": entities.get("hcp_name"),
    }

    user_prompt = (
        f"User said: \"{raw_user_input}\"\n\n"
        f"System context:\n{json.dumps(context, default=str, indent=2)}\n\n"
        "Write a helpful reply based on the context above."
    )

    try:
        reply = await chat_completion(
            messages=[{"role": "user", "content": user_prompt}],
            system=RESPONDER_SYSTEM_PROMPT,
            temperature=0.55,
            max_tokens=300,
        )

    except Exception as exc:
        logger.exception("[responder_node] error: %s", exc)
        # Graceful fallback reply
        if tool_result.get("success"):
            reply = tool_result.get("message", "Action completed successfully.")
        elif tool_result.get("error"):
            reply = f"⚠️ {tool_result['error']}"
        else:
            reply = "I processed your request. Please check the results."

    logger.info("[responder_node] reply length=%d chars", len(reply))
    return {"messages": [AIMessage(content=reply)]}


# ─────────────────────────────────────────────────────────────────
# Router — Conditional edge after tool_selector_node
# ─────────────────────────────────────────────────────────────────

def should_run_tool(state: AgentState) -> Literal["tool_executor_node", "responder_node"]:
    """
    If a tool was selected → execute it.
    If no tool (chitchat) → skip directly to the responder.
    """
    return (
        "tool_executor_node"
        if state.get("selected_tool", "none") != "none"
        else "responder_node"
    )
